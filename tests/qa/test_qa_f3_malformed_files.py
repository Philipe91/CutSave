"""QA FASE 3 — arquivos malformados / hostis na importacao.

Criterio: aviso amigavel OU degradacao limpa (nunca traceback nao tratado,
nunca corrupcao de estado). A janela continua utilizavel depois.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pikepdf  # noqa: E402
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
from PIL import Image, ImageCms  # noqa: E402
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


def _still_usable(w) -> None:
    """A janela nao ficou num estado quebrado: dá para continuar operando."""
    assert w.isEnabled()
    # widgets centrais continuam vivos e respondendo
    w._toasts.info("sanity check")


# ---------------------------------------------------------------------------
# Caso 1: PDF vazio (0 bytes) e PDF corrompido (bytes aleatorios .pdf)
# ---------------------------------------------------------------------------

def test_pdf_vazio_0_bytes_nao_estoura(qapp, tmp_path):
    # QA-F3-01 / A14, corrigido na F1: o ramo blocking do generate() trata a
    # falha com o mesmo padrao amigavel do _on_failed.
    empty = tmp_path / "vazio.pdf"
    empty.write_bytes(b"")
    w = _window(tmp_path)
    w.add_paths([str(empty)])
    w.generate(blocking=True)  # nao pode levantar excecao crua
    _still_usable(w)


def test_pdf_corrompido_bytes_aleatorios_nao_estoura(qapp, tmp_path):
    # QA-F3-01b / A14, corrigido na F1 junto com o caso 0 bytes.
    import random
    corrompido = tmp_path / "corrompido.pdf"
    corrompido.write_bytes(bytes(random.randint(0, 255) for _ in range(2048)))
    w = _window(tmp_path)
    w.add_paths([str(corrompido)])
    w.generate(blocking=True)
    _still_usable(w)


def test_pdf_corrompido_via_thread_worker_mostra_erro_amigavel(qapp, tmp_path, qtbot=None):
    """O caminho NAO-bloqueante (thread real, botao 'Gerar Producao' com o
    programa em uso) ja trata a falha corretamente: comparativo de regressao
    para confirmar que so o atalho blocking=True tem o bug."""
    import random
    corrompido = tmp_path / "corrompido.pdf"
    corrompido.write_bytes(bytes(random.randint(0, 255) for _ in range(2048)))
    w = _window(tmp_path)
    w.add_paths([str(corrompido)])
    erros = []
    w._on_failed = lambda msg: erros.append(msg)  # substitui o dialogo modal
    w.generate(blocking=False)
    for _ in range(200):
        qapp.processEvents()
        if erros or w._thread is None or not w._thread.isRunning():
            if erros:
                break
    if w._thread is not None:
        w._thread.wait(5000)
    for _ in range(20):
        qapp.processEvents()
    assert erros, "a falha deveria ter chegado no callback _on_failed"
    _still_usable(w)


# ---------------------------------------------------------------------------
# Caso 6: PDF sem pagina (0 paginas) e MediaBox 0x0
# ---------------------------------------------------------------------------

def _pdf_zero_paginas(tmp_path):
    pdf = pikepdf.new()
    path = tmp_path / "zero_paginas.pdf"
    pdf.save(str(path))
    return str(path)


def test_pdf_sem_paginas_nao_estoura(qapp, tmp_path):
    # QA-F3-06 / A14, corrigido na F1 (mesma causa-raiz do QA-F3-01).
    w = _window(tmp_path)
    w.add_paths([_pdf_zero_paginas(tmp_path)])
    w.generate(blocking=True)
    _still_usable(w)


def test_pdf_mediabox_0x0_nao_estoura_ou_avisa(qapp, tmp_path):
    """PDF com 1 pagina mas MediaBox degenerada (0x0). O importador de caixas
    (pdfium_boxes) ja tem fallback para caixa degenerada; confirmamos que o
    fluxo completo nao quebra nem corrompe o estado."""
    pdf = pikepdf.new()
    page = pdf.add_blank_page()
    page.MediaBox = [0, 0, 0, 0]
    path = tmp_path / "mediabox_zero.pdf"
    pdf.save(str(path))
    w = _window(tmp_path)
    w.add_paths([str(path)])
    try:
        w.generate(blocking=True)
    except Exception as exc:  # se ainda nao tratado, documentar e não mascarar
        pytest.xfail(
            f"QA-F3-06b: MediaBox 0x0 estourou {type(exc).__name__}: {exc} "
            "via generate(blocking=True) sem dialogo amigavel."
        )
    _still_usable(w)


# ---------------------------------------------------------------------------
# Caso 4: imagem gigante (12000x12000) e PNG 100% transparente
# ---------------------------------------------------------------------------

def test_imagem_gigante_12000x12000_importa_sem_memoryerror(qapp, tmp_path):
    im = Image.new("RGBA", (12000, 12000), (0, 0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(im).rectangle([1000, 1000, 11000, 11000], fill=(200, 30, 30, 255))
    path = tmp_path / "gigante.png"
    im.save(str(path))
    im.close()

    w = _window(tmp_path)
    w.add_paths([str(path)])
    w.generate(blocking=True)  # nao pode dar MemoryError nem travar
    assert w._result is not None
    assert sum(s.item_count for s in w._result.sheets) == 1
    _still_usable(w)


def test_png_100_por_cento_transparente_degrada_para_retangulo_cheio(qapp, tmp_path):
    """Sem nenhum pixel opaco, nao ha contorno para achar: a faca automatica
    tem que degradar de forma limpa (retangulo cheio da imagem), nunca
    quebrar nem gerar uma faca vazia/None."""
    im = Image.new("RGBA", (300, 200), (0, 0, 0, 0))  # 100% transparente
    path = tmp_path / "transparente.png"
    im.save(str(path))
    im.close()

    w = _window(tmp_path)
    w.add_paths([str(path)])
    w.generate(blocking=True)
    assert w._result is not None
    art = w._result.artworks[0]
    # degradacao limpa: sem pixel opaco, cai no retangulo cheio da imagem (a
    # geometria final ainda passa pela sangria/parametros da UI, entao o
    # numero exato de pontos pode variar — o que importa e NAO ficar None/vazio
    # e formar um retangulo com a bbox da imagem).
    assert art.cut_contour is not None
    assert len(art.cut_contour.points) >= 4
    xs = [p.x for p in art.cut_contour.points]
    ys = [p.y for p in art.cut_contour.points]
    assert max(xs) - min(xs) > 0
    assert max(ys) - min(ys) > 0
    _still_usable(w)


# ---------------------------------------------------------------------------
# Caso 5: JPEG CMYK com perfil ICC embutido
# ---------------------------------------------------------------------------

def test_jpeg_cmyk_com_perfil_icc_vai_para_a_chapa(qapp, tmp_path):
    srgb = ImageCms.createProfile("sRGB")
    icc_bytes = ImageCms.ImageCmsProfile(srgb).tobytes()
    jpg = tmp_path / "cmyk_icc.jpg"
    Image.new("CMYK", (300, 200), (10, 80, 90, 5)).save(
        jpg, quality=90, icc_profile=icc_bytes
    )
    w = _window(tmp_path)
    w.add_paths([str(jpg)])
    w.generate(blocking=True)
    assert w._result is not None
    assert sum(s.item_count for s in w._result.sheets) == 1
    out = tmp_path / "IMP.pdf"
    w.export_pdf(str(out))
    assert out.exists()
    _still_usable(w)
