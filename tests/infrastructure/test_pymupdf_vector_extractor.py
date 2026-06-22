import math

import fitz
import pytest
from app.domain.cut.vector import VectorContourGenerator
from app.domain.geometry import Polygon as GeoPolygon
from app.infrastructure.importers.pymupdf_vector_extractor import PyMuPdfVectorExtractor
from app.shared.errors import PdfImportError

PT2MM = 25.4 / 72.0


def test_extrai_circulo_e_gera_contorno(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_circle(fitz.Point(200, 200), 100, color=(0, 0, 0), fill=(0, 0, 0))
    # uma linha e um retangulo extras exercitam outros tipos de item
    page.draw_line(fitz.Point(10, 10), fitz.Point(20, 10))
    page.draw_rect(fitz.Rect(5, 5, 25, 25), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "circ.pdf"
    doc.save(str(path))
    doc.close()

    rings = PyMuPdfVectorExtractor().extract_rings(str(path))
    assert rings

    cut = VectorContourGenerator().generate(rings)
    r_mm = 100 * PT2MM
    assert GeoPolygon(cut.points).area == pytest.approx(math.pi * r_mm**2, rel=0.05)


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(PdfImportError):
        PyMuPdfVectorExtractor().extract_rings(str(tmp_path / "x.pdf"))


def test_arquivo_nao_pdf(tmp_path):
    img = tmp_path / "a.png"
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), 0)
    pix.clear_with(0)
    pix.save(str(img))
    with pytest.raises(PdfImportError):
        PyMuPdfVectorExtractor().extract_rings(str(img))
