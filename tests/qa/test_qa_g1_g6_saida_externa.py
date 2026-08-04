"""G1/G6 digital: arte, faca e DXF concordam em leitores independentes.

Usa somente a pilha atual do projeto: pikepdf para criar/inspecionar PDF,
PDFium para renderizar e ezdxf para abrir o corte. A peca assimetrica torna
giro ou espelhamento acidental observavel. Impressao e regua seguem manuais.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2  # noqa: E402
import ezdxf  # noqa: E402
import numpy as np  # noqa: E402
import pikepdf  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase  # noqa: E402
from app.application.use_cases.import_image import ImportImageUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    RunProductionPipelineUseCase,
)
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pikepdf_print_exporter import (  # noqa: E402
    PikePdfPrintExporter,
)
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter  # noqa: E402
from app.infrastructure.importers.pdfium_importer import PdfiumImporter  # noqa: E402
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer  # noqa: E402
from app.presentation.main_window import MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

PT_POR_MM = 72.0 / 25.4


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _window(tmp_path):
    store = SettingsStore(tmp_path / "config.json")
    settings = store.load_or_create()
    pipeline = RunProductionPipelineUseCase(
        ImportPdfUseCase(PdfiumImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(cache_dir=tmp_path / "imgcache")),
    )
    return MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PikePdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PdfiumPageRenderer(),
        store,
        settings,
    )


def _pdf_assimetrico(tmp_path):
    path = tmp_path / "arte_faca_assimetrica.pdf"
    points = [(10, 10), (70, 10), (70, 25), (40, 25), (40, 65), (10, 65)]

    def path_ops():
        first, *rest = points
        return [f"{first[0] * PT_POR_MM:.6f} {first[1] * PT_POR_MM:.6f} m"] + [
            f"{x * PT_POR_MM:.6f} {y * PT_POR_MM:.6f} l" for x, y in rest
        ] + ["h"]

    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(120 * PT_POR_MM, 80 * PT_POR_MM))
    operators = [
        "q",
        "0.1 0.4 0.8 rg",
        *path_ops(),
        "f",
        "1 0 1 RG",
        "0.5 w",
        *path_ops(),
        "S",
        "Q",
    ]
    page.Contents = pdf.make_stream(("\n".join(operators) + "\n").encode("ascii"))
    pdf.save(path)
    pdf.close()
    return path


def _mask(path):
    document = pdfium.PdfDocument(path)
    try:
        image = document[0].render(scale=1).to_pil().convert("RGB").copy()
    finally:
        document.close()
    return np.any(np.asarray(image) < 240, axis=2)


def _bbox(mask):
    ys, xs = np.nonzero(mask)
    assert len(xs), "PDF exportado em branco"
    return np.array((xs.min(), ys.min(), xs.max(), ys.max()))


def _sem_repetidos(points):
    result = []
    for point in points:
        xy = (float(point[0]), float(point[1]))
        if not result or xy != result[-1]:
            result.append(xy)
    return result


def test_arte_faca_e_dxf_preservam_escala_posicao_e_orientacao(qapp, tmp_path):
    source = _pdf_assimetrico(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(500)
    window._height.setValue(500)
    window._offset.setValue(0)
    window.add_paths([str(source)])
    window.generate(blocking=True)

    assert window._faca_notice is not None
    assert "MAGENTA" in window._faca_notice[1]

    print_pdf = tmp_path / "IMPRESSAO.pdf"
    knife_pdf = tmp_path / "FACA.pdf"
    dxf_path = tmp_path / "CORTE.dxf"
    window.export_pdf(str(print_pdf))
    window.export_faca_pdf(str(knife_pdf))
    window.export_dxf(str(dxf_path))

    with pikepdf.open(print_pdf) as art_doc, pikepdf.open(knife_pdf) as knife_doc:
        assert list(knife_doc.pages[0].MediaBox) == list(art_doc.pages[0].MediaBox)

    art_mask = _mask(print_pdf)
    knife_mask = _mask(knife_pdf)
    assert _bbox(knife_mask) == pytest.approx(_bbox(art_mask), abs=1)

    interior = art_mask.copy()
    interior[1:-1, 1:-1] &= (
        art_mask[:-2, 1:-1]
        & art_mask[2:, 1:-1]
        & art_mask[1:-1, :-2]
        & art_mask[1:-1, 2:]
    )
    boundary = art_mask & ~interior
    distance = cv2.distanceTransform((~boundary).astype(np.uint8), cv2.DIST_L2, 3)
    assert float(distance[knife_mask].max()) < 1.5

    dxf = ezdxf.readfile(dxf_path)
    assert dxf.header["$INSUNITS"] == 4  # milimetros
    polylines = list(dxf.modelspace().query("LWPOLYLINE"))
    assert len(polylines) == 1
    points = _sem_repetidos(polylines[0].get_points("xy"))
    min_x = min(x for x, _ in points)
    min_y = min(y for _, y in points)
    normalized = [(x - min_x, y - min_y) for x, y in points]
    expected = [(0, 0), (60, 0), (60, 15), (30, 15), (30, 55), (0, 55)]
    assert len(normalized) == len(expected)
    for actual, target in zip(normalized, expected):
        assert actual == pytest.approx(target, abs=0.01)

    window._dirty = False
    window.close()
