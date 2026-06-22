import fitz
import pytest
from app.infrastructure.importers.pymupdf_inspector import PyMuPdfInspector
from app.shared.errors import PdfInspectionError

# A4 em points (1 pt = 1/72")
A4_W_PT, A4_H_PT = 595.0, 842.0
A4_W_MM, A4_H_MM = 209.90, 297.04


def _build_pdf(path):
    """Cria um PDF de 2 paginas A4: pagina 1 so vetor, pagina 2 so raster."""
    doc = fitz.open()

    vector_page = doc.new_page(width=A4_W_PT, height=A4_H_PT)
    vector_page.draw_rect(fitz.Rect(50, 50, 200, 200), color=(0, 0, 0))

    raster_page = doc.new_page(width=A4_W_PT, height=A4_H_PT)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 16, 16), 0)
    pix.clear_with(128)
    raster_page.insert_image(fitz.Rect(100, 100, 300, 300), pixmap=pix)

    doc.save(str(path))
    doc.close()


@pytest.fixture
def pdf_path(tmp_path):
    path = tmp_path / "amostra.pdf"
    _build_pdf(path)
    return str(path)


def test_conta_paginas(pdf_path):
    report = PyMuPdfInspector().inspect(pdf_path)
    assert report.page_count == 2
    assert len(report.pages) == 2


def test_dimensao_em_milimetros(pdf_path):
    page = PyMuPdfInspector().inspect(pdf_path).pages[0]
    assert page.width_pt == pytest.approx(A4_W_PT)
    assert page.size_mm.width == pytest.approx(A4_W_MM, abs=0.05)
    assert page.size_mm.height == pytest.approx(A4_H_MM, abs=0.05)


def test_detecta_vetor_na_primeira_pagina(pdf_path):
    report = PyMuPdfInspector().inspect(pdf_path)
    assert report.pages[0].has_vector is True
    assert report.has_vector is True


def test_detecta_raster_na_segunda_pagina(pdf_path):
    report = PyMuPdfInspector().inspect(pdf_path)
    assert report.pages[1].has_raster is True
    assert report.has_raster is True


def test_pagina_de_vetor_nao_tem_raster(pdf_path):
    report = PyMuPdfInspector().inspect(pdf_path)
    assert report.pages[0].has_raster is False


def test_arquivo_inexistente_levanta_erro(tmp_path):
    with pytest.raises(PdfInspectionError):
        PyMuPdfInspector().inspect(str(tmp_path / "nao_existe.pdf"))


def test_arquivo_nao_pdf_levanta_erro(tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_text("isto nao e um pdf", encoding="utf-8")
    with pytest.raises(PdfInspectionError):
        PyMuPdfInspector().inspect(str(fake))
