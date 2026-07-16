import math

import fitz
import pytest
from app.domain.cut.vector import VectorContourGenerator, select_cut_rings
from app.domain.geometry import Polygon as GeoPolygon
from app.infrastructure.importers.pdfium_vector_extractor import PdfiumVectorExtractor
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

    rings = PdfiumVectorExtractor().extract_rings(str(path))
    assert rings

    cut = VectorContourGenerator().generate(rings)
    r_mm = 100 * PT2MM
    assert GeoPolygon(cut.points).area == pytest.approx(math.pi * r_mm**2, rel=0.05)


def test_faca_magenta_vence_a_arte_maior(tmp_path):
    # Arquivo REAL de cliente: arte vetorial preenchida (grande) + faca em
    # traço magenta (menor). Antes a união pegava o MAIOR contorno (a arte);
    # a seleção por cor tem de escolher a linha magenta.
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_rect(fitz.Rect(10, 10, 390, 390), color=None, fill=(0.2, 0.4, 1))  # arte/fundo
    page.draw_circle(fitz.Point(200, 200), 80, color=(1, 0, 1), width=1.0)       # FACA magenta
    path = tmp_path / "cliente.pdf"
    doc.save(str(path))
    doc.close()

    infos = PdfiumVectorExtractor().extract_rings_info(str(path))
    rings, reason = select_cut_rings(infos)
    assert reason == "magenta"

    cut = VectorContourGenerator().generate(rings)
    r_mm = 80 * PT2MM
    assert GeoPolygon(cut.points).area == pytest.approx(math.pi * r_mm**2, rel=0.05)


def test_sem_magenta_usa_traco_sem_preenchimento(tmp_path):
    # Sem cor de faca: o traço sem preenchimento ainda vence a arte preenchida.
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_rect(fitz.Rect(10, 10, 390, 390), color=None, fill=(0, 0, 0))  # arte
    page.draw_circle(fitz.Point(200, 200), 60, color=(0, 0, 0), width=1.0)   # linha de corte preta
    path = tmp_path / "semcor.pdf"
    doc.save(str(path))
    doc.close()

    rings, reason = select_cut_rings(PdfiumVectorExtractor().extract_rings_info(str(path)))
    assert reason == "stroke"
    cut = VectorContourGenerator().generate(rings)
    r_mm = 60 * PT2MM
    assert GeoPolygon(cut.points).area == pytest.approx(math.pi * r_mm**2, rel=0.05)


def test_tudo_preenchido_cai_no_comportamento_antigo(tmp_path):
    # Nenhuma pista de faca (tudo preenchido): união geral, maior contorno.
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_rect(fitz.Rect(50, 50, 350, 350), color=None, fill=(0, 0, 0))
    path = tmp_path / "soarte.pdf"
    doc.save(str(path))
    doc.close()

    rings, reason = select_cut_rings(PdfiumVectorExtractor().extract_rings_info(str(path)))
    assert reason == "all"
    cut = VectorContourGenerator().generate(rings)
    lado_mm = 300 * PT2MM
    assert GeoPolygon(cut.points).area == pytest.approx(lado_mm**2, rel=0.05)


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(PdfImportError):
        PdfiumVectorExtractor().extract_rings(str(tmp_path / "x.pdf"))


def test_arquivo_nao_pdf(tmp_path):
    img = tmp_path / "a.png"
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), 0)
    pix.clear_with(0)
    pix.save(str(img))
    with pytest.raises(PdfImportError):
        PdfiumVectorExtractor().extract_rings(str(img))
