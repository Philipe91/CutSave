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


@pytest.mark.parametrize("box", ["media", "trim", "auto"])
def test_render_imagem_em_qualquer_caixa_nao_quebra(tmp_path, box):
    # imagem (nao-PDF) com box de apara NAO pode acessar page.xref (falha nativa):
    # box_clip_rect deve devolver a pagina inteira. Regressao do crash em producao.
    from PIL import Image
    p = tmp_path / "img.png"
    Image.new("RGBA", (120, 80), (10, 10, 10, 255)).save(p, dpi=(150, 150))
    data = PyMuPdfPageRenderer().render_png(str(p), box=box)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
