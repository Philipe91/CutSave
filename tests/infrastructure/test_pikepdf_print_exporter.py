from pathlib import Path

import fitz
import pytest
from app.application.dto.print_placement import (
    PrintCircle,
    PrintLine,
    PrintPlacement,
    PrintSheet,
)
from app.domain.geometry import Point2D, Size
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter
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
    PikePdfPrintExporter().export(
        [PrintSheet((PrintPlacement(src, 0, Point2D(0, 0), art),), art)], str(out_sem)
    )
    out_com = tmp_path / "com.pdf"
    PikePdfPrintExporter().export(
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
    PikePdfPrintExporter().export(sheets, str(out))

    doc = fitz.open(str(out))
    assert doc.page_count == 2
    assert doc[0].rect.width == pytest.approx(200 * MM2PT, abs=1)
    doc.close()


def test_posicionamento_e_escala(tmp_path):
    src = _source_pdf(tmp_path)
    out = tmp_path / "IMPRESSAO.pdf"
    art_w, art_h = 144 / MM2PT, 72 / MM2PT
    PikePdfPrintExporter().export([_sheet(src, art_w, art_h, 200)], str(out))

    doc = fitz.open(str(out))
    pix = doc[0].get_pixmap()  # 72 dpi: 1pt = 1px
    assert _is_black(pix, 50, 36)
    assert _is_white(pix, 400, 36)
    doc.close()


def test_export_image_gera_png_no_dpi(tmp_path):
    src = _source_pdf(tmp_path)
    out = tmp_path / "IMG.png"
    art_w, art_h = 144 / MM2PT, 72 / MM2PT
    paths = PikePdfPrintExporter().export_image(
        [_sheet(src, art_w, art_h, 200)], str(out), dpi=150
    )
    assert paths == [str(out)]
    assert out.exists()
    pix = fitz.Pixmap(str(out))
    # 200mm a 150 dpi ~= 1181 px de largura
    assert abs(pix.width - 200 / 25.4 * 150) < 5


def test_export_image_grava_o_dpi_no_arquivo(tmp_path):
    # Regressão 16/07 (teste real): PNG/JPEG saíam SEM o dpi gravado — o
    # RIP/Corel abria a 96dpi e a chapa de 19,7cm virava 92cm ("10x maior").
    from PIL import Image

    src = _source_pdf(tmp_path)
    art_w, art_h = 144 / MM2PT, 72 / MM2PT
    for ext, fmt in (("png", "png"), ("jpg", "jpeg")):
        out = tmp_path / f"DPI.{ext}"
        PikePdfPrintExporter().export_image(
            [_sheet(src, art_w, art_h, 200)], str(out), dpi=300, image_format=fmt
        )
        dpi = Image.open(str(out)).info.get("dpi")
        assert dpi is not None, f"{fmt}: dpi não gravado"
        assert abs(dpi[0] - 300) < 2 and abs(dpi[1] - 300) < 2


def test_export_image_varias_chapas_numera(tmp_path):
    src = _source_pdf(tmp_path)
    out = tmp_path / "IMG.png"
    art_w, art_h = 144 / MM2PT, 72 / MM2PT
    sheets = [_sheet(src, art_w, art_h, 200), _sheet(src, art_w, art_h, 200)]
    paths = PikePdfPrintExporter().export_image(sheets, str(out), dpi=72)
    assert len(paths) == 2
    assert [Path(p).name for p in paths] == ["IMG_01.png", "IMG_02.png"]
    assert all(Path(p).exists() for p in paths)


def test_export_image_jpeg(tmp_path):
    src = _source_pdf(tmp_path)
    out = tmp_path / "IMG.jpg"
    art_w, art_h = 144 / MM2PT, 72 / MM2PT
    PikePdfPrintExporter().export_image(
        [_sheet(src, art_w, art_h, 200)], str(out), dpi=72, image_format="jpeg"
    )
    assert out.exists()


def _png_source(tmp_path, w_px=120, h_px=60):
    from PIL import Image
    p = tmp_path / "art.png"
    Image.new("RGB", (w_px, h_px), (10, 10, 10)).save(p, dpi=(150, 150))
    return str(p)


def test_imagem_e_embutida_via_insert_image(tmp_path):
    src = _png_source(tmp_path)
    out = tmp_path / "IMPRESSAO.pdf"
    art = Size(120 / MM2PT, 60 / MM2PT)
    sheet = PrintSheet((PrintPlacement(src, 0, Point2D(0, 0), art),), Size(200, 60 / MM2PT))
    PikePdfPrintExporter().export([sheet], str(out))

    doc = fitz.open(str(out))
    assert doc.page_count == 1
    assert len(doc[0].get_images()) >= 1  # a imagem foi inserida na pagina
    doc.close()


def test_imagem_exporta_para_png(tmp_path):
    src = _png_source(tmp_path)
    out = tmp_path / "OUT.png"
    art = Size(120 / MM2PT, 60 / MM2PT)
    sheet = PrintSheet((PrintPlacement(src, 0, Point2D(0, 0), art),), Size(200, 60 / MM2PT))
    paths = PikePdfPrintExporter().export_image([sheet], str(out), dpi=96)
    assert paths == [str(out)]
    assert out.exists()


def test_marcas_circulos_e_linhas_sao_desenhadas(tmp_path):
    src = _source_pdf(tmp_path)
    out = tmp_path / "MARCAS.pdf"
    art = Size(144 / MM2PT, 72 / MM2PT)
    sheet = PrintSheet(
        (PrintPlacement(src, 0, Point2D(0, 0), art),),
        Size(200, 72 / MM2PT),
        circles=(PrintCircle(Point2D(5, 5), 6.0),),
        lines=(PrintLine(Point2D(10, 10), Point2D(30, 10), 1.0),),
    )
    PikePdfPrintExporter().export([sheet], str(out))
    assert out.exists()
    doc = fitz.open(str(out))
    assert doc[0].get_drawings()  # ha vetores desenhados (circulo + linha)
    doc.close()


def test_arquivo_origem_invalido_falha(tmp_path):
    out = tmp_path / "IMPRESSAO.pdf"
    sheet = PrintSheet(
        (PrintPlacement(str(tmp_path / "nao_existe.pdf"), 0, Point2D(0, 0), Size(10, 10)),),
        Size(100, 100),
    )
    with pytest.raises(PrintExportError):
        PikePdfPrintExporter().export([sheet], str(out))


@pytest.mark.parametrize("rotate", [0, 90, 180, 270])
def test_paridade_pixel_com_motor_antigo_em_todas_rotacoes(tmp_path, rotate):
    """Prova da migração de licença: a composição pikepdf reproduz o
    show_pdf_page do fitz PIXEL a PIXEL (tolerância = antialiasing de borda)
    em todas as rotações, com fonte ASSIMÉTRICA (pega espelho/giro errado).

    **Sinal invertido em 31/07/2026.** O `rotate` do fitz é ANTI-horário; o do
    PrintNest é horário, que é o sentido que o canvas mostra
    (`QTransform().rotate(+ângulo)`). Até esta data a exportação copiava o
    sentido do fitz, e por isso toda peça girada em 90 ou 270 era impressa 180
    graus virada em relação à tela — com a faca saindo correta, porque ela não
    passa por esta matriz. Foi relatado em produção com material real.

    O defeito, portanto, é ANTERIOR à migração: este teste garantia fielmente a
    paridade com um motor que já discordava da própria tela do produto. A
    paridade de renderização continua sendo verificada; o que mudou é só a
    conversão de sentido (`-rotate` na referência)."""
    src = tmp_path / "tri.pdf"
    doc = fitz.open()
    pg = doc.new_page(width=200, height=100)
    pg.draw_polyline(
        [fitz.Point(10, 90), fitz.Point(60, 10), fitz.Point(190, 90), fitz.Point(10, 90)],
        color=(0, 0.5, 0), fill=(0.2, 0.8, 0.2),
    )
    doc.save(str(src))
    doc.close()

    w_mm, h_mm = 200 / MM2PT, 100 / MM2PT
    if rotate in (90, 270):
        w_mm, h_mm = h_mm, w_mm  # footprint girado (como o nesting monta)
    sheet = PrintSheet(
        (PrintPlacement(str(src), 0, Point2D(10, 15), Size(w_mm, h_mm), rotate=rotate),),
        Size(120, 120),
    )

    # referência: composição do fitz (o comportamento consagrado)
    ref = fitz.open()
    page = ref.new_page(width=120 * MM2PT, height=120 * MM2PT)
    rect = fitz.Rect(
        10 * MM2PT, 15 * MM2PT, (10 + w_mm) * MM2PT, (15 + h_mm) * MM2PT
    )
    sd = fitz.open(str(src))
    # -rotate: o fitz gira anti-horario, o PrintNest gira horario (ver docstring)
    page.show_pdf_page(rect, sd, 0, rotate=-rotate)
    ref_pix = page.get_pixmap(dpi=96)
    sd.close()

    out = tmp_path / f"rot{rotate}.pdf"
    PikePdfPrintExporter().export([sheet], str(out))
    cand = fitz.open(str(out))
    cand_pix = cand[0].get_pixmap(dpi=96)

    assert (ref_pix.width, ref_pix.height) == (cand_pix.width, cand_pix.height)
    diverge = 0
    for x in range(0, ref_pix.width, 3):
        for y in range(0, ref_pix.height, 3):
            a, b = ref_pix.pixel(x, y), cand_pix.pixel(x, y)
            if sum(abs(a[i] - b[i]) for i in range(3)) > 30:
                diverge += 1
    total = (ref_pix.width // 3) * (ref_pix.height // 3)
    cand.close()
    ref.close()
    assert diverge / total < 0.002, f"{diverge}/{total} pixels divergem (rot={rotate})"


def test_marca_quadrada_e_desenhada_preta_e_preenchida(tmp_path):
    from app.application.dto.print_placement import PrintRect

    src = _source_pdf(tmp_path)
    out = tmp_path / "QUADRADOS.pdf"
    sheet = PrintSheet(
        (PrintPlacement(src, 0, Point2D(0, 0), Size(144 / MM2PT, 72 / MM2PT)),),
        Size(200, 100),
        rects=(PrintRect(Point2D(150, 50), 6.0),),
    )
    PikePdfPrintExporter().export([sheet], str(out))
    doc = fitz.open(str(out))
    quadrados = [
        item[1]
        for d in doc[0].get_drawings()
        if d.get("fill") is not None and max(d["fill"]) == 0.0  # preto 100%
        for item in d["items"]
        if item[0] == "re" and round(item[1].width / MM2PT, 1) == 6.0
    ]
    doc.close()
    assert quadrados  # quadrado preto solido de 6mm no PDF
    assert round(quadrados[0].height / MM2PT, 1) == 6.0
