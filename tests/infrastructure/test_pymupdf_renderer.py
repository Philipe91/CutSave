import fitz
import pytest
from app.infrastructure.rendering.pymupdf_renderer import PyMuPdfPageRenderer
from app.shared.errors import PdfImportError


def _pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "x.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_render_retorna_png(tmp_path):
    data = PyMuPdfPageRenderer().render_png(_pdf(tmp_path))
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # assinatura PNG


def test_apara_recorta_no_trimbox(tmp_path):
    # pagina 200x100 com TrimBox menor (50,25..150,75) -> 100x50
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    doc.xref_set_key(page.xref, "TrimBox", "[50 25 150 75]")
    path = tmp_path / "trim.pdf"
    doc.save(str(path))
    doc.close()

    renderer = PyMuPdfPageRenderer()
    media_png = renderer.render_png(str(path), box="media")
    trim_png = renderer.render_png(str(path), box="trim")
    # a renderizacao da apara e menor (so o miolo do TrimBox)
    media_img = fitz.open("png", media_png)[0].rect
    trim_img = fitz.open("png", trim_png)[0].rect
    assert trim_img.width < media_img.width
    assert trim_img.height < media_img.height


def test_arquivo_inexistente_falha(tmp_path):
    with pytest.raises(PdfImportError):
        PyMuPdfPageRenderer().render_png(str(tmp_path / "nao_existe.pdf"))
