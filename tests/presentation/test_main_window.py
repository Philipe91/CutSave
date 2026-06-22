import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
import fitz  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    RunProductionPipelineUseCase,
)
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pymupdf_print_exporter import PyMuPdfPrintExporter  # noqa: E402
from app.infrastructure.importers.pymupdf_importer import PyMuPdfImporter  # noqa: E402
from app.presentation.main_window import MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _two_page_pdf(tmp_path):
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=200, height=100)  # ~70.5 x 35.3 mm
        page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "fonte.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _window(tmp_path):
    store = SettingsStore(tmp_path / "config.json")
    settings = store.load_or_create()
    pipeline = RunProductionPipelineUseCase(ImportPdfUseCase(PyMuPdfImporter()))
    return MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PyMuPdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        store,
        settings,
    )


def test_fluxo_completo_da_ui(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])

    window.generate(blocking=True)  # roda o pipeline sincronamente

    assert window._result is not None
    assert sum(s.item_count for s in window._result.sheets) == 2
    # preview: 1 retangulo de material + 2 pecas
    assert len(window._scene.items()) >= 3

    pdf_out = tmp_path / "IMPRESSAO.pdf"
    window.export_pdf(str(pdf_out))
    assert pdf_out.exists()
    assert fitz.open(str(pdf_out)).page_count == 1

    dxf_out = tmp_path / "CORTE.dxf"
    window.export_dxf(str(dxf_out))
    assert dxf_out.exists()
    doc = ezdxf.readfile(str(dxf_out))
    assert len(doc.modelspace().query("LWPOLYLINE")) == 2


def test_clique_do_botao_nao_usa_o_argumento_checked(qapp, tmp_path):
    # O sinal clicked envia um bool; export_pdf(False)/export_dxf(False) NAO
    # deve tratar False como caminho. Sem result, deve apenas retornar.
    window = _window(tmp_path)
    window.export_pdf(False)  # nao deve levantar nem tentar salvar em "False"
    window.export_dxf(False)
    assert window._result is None


def test_persiste_configuracoes(qapp, tmp_path):
    window = _window(tmp_path)
    window._width.setValue(1500)
    window._height.setValue(1000)
    window._spacing.setValue(8)
    window._offset.setValue(2)
    window._save_settings()

    recarregado = SettingsStore(tmp_path / "config.json").load()
    assert recarregado.material_width == 1500
    assert recarregado.material_height == 1000
    assert recarregado.spacing == 8
    assert recarregado.offset == 2
