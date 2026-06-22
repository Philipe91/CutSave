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


def test_arquivo_inexistente_falha(tmp_path):
    with pytest.raises(PdfImportError):
        PyMuPdfPageRenderer().render_png(str(tmp_path / "nao_existe.pdf"))
