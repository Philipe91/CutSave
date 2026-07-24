"""QA F1 — A1: recorte de página não pode falhar em SILÊNCIO.

Quando o bake do recorte (_bake_cropped_pdf/_bake_cropped_image) falha, a
produção sai com o arquivo ORIGINAL inteiro — o operador precisa ser avisado
de que o recorte não foi aplicado (antes o aviso não existia e o toast de
sucesso já tinha aparecido antes do processamento real).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase  # noqa: E402
from app.application.use_cases.import_image import ImportImageUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    RunProductionPipelineUseCase,
)
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter  # noqa: E402
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter  # noqa: E402
from app.infrastructure.importers.pdfium_importer import PdfiumImporter  # noqa: E402
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer  # noqa: E402
from app.presentation.main_window import MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


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


def _small_pdf(tmp_path, name="peca.pdf", w_mm=30.0, h_mm=30.0):
    pt = 72.0 / 25.4
    doc = fitz.open()
    page = doc.new_page(width=w_mm * pt, height=h_mm * pt)
    page.draw_rect(
        fitz.Rect(0, 0, w_mm * pt, h_mm * pt), color=(0, 0, 0), fill=(0, 0, 0)
    )
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


def _still_usable(w) -> None:
    assert w.isEnabled()
    w._toasts.info("sanity check")


def test_bake_do_recorte_falha_avisa_e_usa_o_original(qapp, tmp_path, monkeypatch):
    """Bake falhando (PDF exótico, %TEMP% sem espaço…): a produção CAI no
    arquivo original — comportamento aceito — mas tem que AVISAR o operador."""
    src = _small_pdf(tmp_path)
    w = _window(tmp_path)
    w.add_paths([src])
    w.generate(blocking=True)
    assert w._result is not None

    # recorte configurado + bake forçado a falhar (como um PDF exótico faria)
    w._page_crops[src] = {0: (5.0, 5.0, 5.0, 5.0)}
    w._invalidate_crop_cache(src)
    monkeypatch.setattr(MainWindow, "_bake_cropped_pdf", lambda self, *a, **k: None)
    avisos = []
    monkeypatch.setattr(w._toasts, "warning", lambda msg: avisos.append(msg))

    w.generate(blocking=True)

    assert w._result is not None
    # a produção usou o arquivo ORIGINAL (fallback), não um recortado de cache
    assert all(key[0] == src for key in set(w._result.sources.values()))
    # ...e o operador foi avisado de que o recorte não entrou
    assert any("não pôde ser aplicado" in m for m in avisos), (
        f"bake falhou sem nenhum aviso ao operador (toasts: {avisos})"
    )
    _still_usable(w)


def test_bake_ok_nao_dispara_o_aviso_de_recorte(qapp, tmp_path, monkeypatch):
    """Contraprova: com o bake funcionando, o aviso de 'não pôde ser aplicado'
    NUNCA aparece e a produção usa o PDF recortado do cache."""
    src = _small_pdf(tmp_path)
    w = _window(tmp_path)
    w.add_paths([src])
    w.generate(blocking=True)

    w._page_crops[src] = {0: (5.0, 5.0, 5.0, 5.0)}
    w._invalidate_crop_cache(src)
    avisos = []
    monkeypatch.setattr(w._toasts, "warning", lambda msg: avisos.append(msg))

    w.generate(blocking=True)

    assert w._result is not None
    assert not any("não pôde ser aplicado" in m for m in avisos)
    # o caminho efetivo é o recortado (bake em cache), não o original
    assert w._effective_path(src) != src
    _still_usable(w)
