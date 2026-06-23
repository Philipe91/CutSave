import fitz
import pytest
from app.application.dto.print_placement import PrintPlacement, PrintSheet
from app.domain.geometry import Point2D, Size
from app.infrastructure.exporters.pymupdf_print_exporter import PyMuPdfPrintExporter
from app.shared.errors import PrintExportError

MM2PT = 72.0 / 25.4


def _source_pdf(tmp_path, w_pt=144.0, h_pt=72.0):
    """PDF de origem: pagina preenchida de preto (bloco solido)."""
    doc = fitz.open()
    page = doc.new_page(width=w_pt, height=h_pt)
    page.draw_rect(fitz.Rect(0, 0, w_pt, h_pt), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "src.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _is_black(pix, x, y):
    r, g, b = pix.pixel(x, y)[:3]
    return r < 40 and g < 40 and b < 40


def _is_white(pix, x, y):
    r, g, b = pix.pixel(x, y)[:3]
    return r > 215 and g > 215 and b > 215


def _sheet(src, w_mm, h_mm, sheet_w_mm):
    art = Size(w_mm, h_mm)
    return PrintSheet((PrintPlacement(src, 0, Point2D(0, 0), art),), Size(sheet_w_mm, h_mm))


def _bordered_pdf(tmp_path):
    """Pagina 100x100 pt: borda branca, centro preto (25..75)."""
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.draw_rect(fitz.Rect(0, 0, 100, 100), color=(1, 1, 1), fill=(1, 1, 1))
    page.draw_rect(fitz.Rect(25, 25, 75, 75), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "borda.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_crop_remove_a_borda_branca(tmp_path):
    src = _bordered_pdf(tmp_path)
    art = Size(100 / MM2PT, 100 / MM2PT)
    crop = 25 / MM2PT  # recorta a borda branca -> centro preto preenche a folha

    out_sem = tmp_path / "sem.pdf"
    PyMuPdfPrintExporter().export(
        [PrintSheet((PrintPlacement(src, 0, Point2D(0, 0), art),), art)], str(out_sem)
    )
    out_com = tmp_path / "com.pdf"
    PyMuPdfPrintExporter().export(
        [PrintSheet((PrintPlacement(src, 0, Point2D(0, 0), art, crop),), art)], str(out_com)
    )

    pix_sem = fitz.open(str(out_sem))[0].get_pixmap()
    pix_com = fitz.open(str(out_com))[0].get_pixmap()
    # sem recorte: canto branco; com recorte: canto preto
    assert _is_white(pix_sem, 5, 5)
    assert _is_black(pix_com, 5, 5)


def test_gera_pdf_com_uma_pagina_por_chapa(tmp_path):
    src = _source_pdf(tmp_path)
    out = tmp_path / "IMPRESSAO.pdf"
    art_w, art_h = 144 / MM2PT, 72 / MM2PT
    sheets = [_sheet(src, art_w, art_h, 200), _sheet(src, art_w, art_h, 200)]
    PyMuPdfPrintExporter().export(sheets, str(out))

    doc = fitz.open(str(out))
    assert doc.page_count == 2
    assert doc[0].rect.width == pytest.approx(200 * MM2PT, abs=1)
    doc.close()


def test_posicionamento_e_escala(tmp_path):
    src = _source_pdf(tmp_path)
    out = tmp_path / "IMPRESSAO.pdf"
    art_w, art_h = 144 / MM2PT, 72 / MM2PT
    PyMuPdfPrintExporter().export([_sheet(src, art_w, art_h, 200)], str(out))

    doc = fitz.open(str(out))
    pix = doc[0].get_pixmap()  # 72 dpi: 1pt = 1px
    assert _is_black(pix, 50, 36)
    assert _is_white(pix, 400, 36)
    doc.close()


def test_arquivo_origem_invalido_falha(tmp_path):
    out = tmp_path / "IMPRESSAO.pdf"
    sheet = PrintSheet(
        (PrintPlacement(str(tmp_path / "nao_existe.pdf"), 0, Point2D(0, 0), Size(10, 10)),),
        Size(100, 100),
    )
    with pytest.raises(PrintExportError):
        PyMuPdfPrintExporter().export([sheet], str(out))
