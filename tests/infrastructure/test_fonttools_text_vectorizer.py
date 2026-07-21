import os

import pytest
from app.infrastructure.text.fonttools_text_vectorizer import FontToolsTextVectorizer
from app.shared.errors import TextVectorizeError
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

_ARIAL = "C:/Windows/Fonts/arial.ttf"

# Mini-TTF deterministico: unitsPerEm=1000, entao com size_mm=100 cada
# unidade da fonte vale 0.1mm — as assercoes leem direto.
_UPM = 1000
_ADV_A = 700   # advance de A, O e i (i usa 400)
_ADV_SPACE = 500


def _square(pen: TTGlyphPen, x0: int, y0: int, x1: int, y1: int, reverse: bool = False) -> None:
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if reverse:
        pts.reverse()
    pen.moveTo(pts[0])
    for p in pts[1:]:
        pen.lineTo(p)
    pen.closePath()


@pytest.fixture
def mini_font(tmp_path):
    fb = FontBuilder(_UPM, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A", "O", "i", "space"])
    fb.setupCharacterMap({ord("A"): "A", ord("O"): "O", ord("i"): "i", ord(" "): "space"})

    glyphs = {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph()}
    pen = TTGlyphPen(None)                      # "A": quadrado cheio 500x700
    _square(pen, 100, 0, 600, 700)
    glyphs["A"] = pen.glyph()
    pen = TTGlyphPen(None)                      # "O": quadrado com furo quadrado
    _square(pen, 100, 0, 600, 700)
    _square(pen, 200, 100, 500, 600, reverse=True)
    glyphs["O"] = pen.glyph()
    pen = TTGlyphPen(None)                      # "i": haste embaixo + pingo em cima
    _square(pen, 100, 0, 300, 500)
    _square(pen, 100, 600, 300, 800)
    glyphs["i"] = pen.glyph()
    fb.setupGlyf(glyphs)

    fb.setupHorizontalMetrics({
        ".notdef": (500, 0),
        "A": (_ADV_A, 100),
        "O": (_ADV_A, 100),
        "i": (400, 100),
        "space": (_ADV_SPACE, 0),
    })
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Mini", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    path = tmp_path / "mini.ttf"
    fb.save(str(path))
    return str(path)


def test_escala_size_mm_e_o_corpo_em(mini_font):
    shapes = FontToolsTextVectorizer().vectorize("A", mini_font, 100)
    assert len(shapes) == 1
    assert shapes[0].char == "A"
    assert len(shapes[0].shapes) == 1
    bb = shapes[0].shapes[0].bounding_box
    # quadrado de 500x700 unidades a 0.1mm/unidade
    assert bb.width == pytest.approx(50, abs=0.01)
    assert bb.height == pytest.approx(70, abs=0.01)


def test_furo_do_o_resolvido_por_glifo(mini_font):
    shapes = FontToolsTextVectorizer().vectorize("O", mini_font, 100)
    assert len(shapes) == 1
    assert len(shapes[0].shapes) == 1
    o = shapes[0].shapes[0]
    assert len(o.holes) == 1
    assert o.area_liquida == pytest.approx(50 * 70 - 30 * 50, abs=0.01)


def test_i_tem_dois_corpos_no_mesmo_glyphshapes(mini_font):
    shapes = FontToolsTextVectorizer().vectorize("i", mini_font, 100)
    assert len(shapes) == 1
    assert len(shapes[0].shapes) == 2
    assert all(s.holes == () for s in shapes[0].shapes)


def test_posicao_pelo_advance_do_hmtx(mini_font):
    shapes = FontToolsTextVectorizer().vectorize("AA", mini_font, 100)
    assert [g.char for g in shapes] == ["A", "A"]
    first, second = (g.shapes[0].bounding_box for g in shapes)
    assert second.min_x - first.min_x == pytest.approx(_ADV_A * 0.1, abs=0.01)


def test_flip_y_e_normalizacao_em_zero_zero(mini_font):
    shapes = FontToolsTextVectorizer().vectorize("i", mini_font, 100)
    boxes = [s.bounding_box for s in shapes[0].shapes]
    # bbox global do resultado comeca em (0, 0)
    assert min(b.min_x for b in boxes) == pytest.approx(0, abs=0.01)
    assert min(b.min_y for b in boxes) == pytest.approx(0, abs=0.01)
    # Y para BAIXO: o pingo (corpo menor, topo da letra) sai com y MENOR
    pingo, haste = sorted(boxes, key=lambda b: b.width * b.height)
    assert pingo.max_y < haste.min_y
    assert pingo.min_y == pytest.approx(0, abs=0.01)


def test_espaco_anda_o_cursor_sem_gerar_shapes(mini_font):
    shapes = FontToolsTextVectorizer().vectorize("A A", mini_font, 100)
    assert [g.char for g in shapes] == ["A", "A"]
    first, second = (g.shapes[0].bounding_box for g in shapes)
    assert second.min_x - first.min_x == pytest.approx((_ADV_A + _ADV_SPACE) * 0.1, abs=0.01)


def test_caractere_sem_glifo_lanca_erro_listando(mini_font):
    with pytest.raises(TextVectorizeError) as exc_info:
        FontToolsTextVectorizer().vectorize("ABi", mini_font, 100)
    assert "B" in str(exc_info.value)


def test_fonte_inexistente_lanca_erro(tmp_path):
    with pytest.raises(TextVectorizeError):
        FontToolsTextVectorizer().vectorize("A", str(tmp_path / "nao_existe.ttf"), 100)


def test_approximation_invalida_lanca_erro():
    with pytest.raises(TextVectorizeError):
        FontToolsTextVectorizer(approximation=0)


@pytest.mark.skipif(not os.path.exists(_ARIAL), reason="arial.ttf indisponivel")
def test_integracao_arial_oba_com_furos_e_curvas():
    fino = FontToolsTextVectorizer(approximation=0.05).vectorize("OBA", _ARIAL, 50)
    assert [g.char for g in fino] == ["O", "B", "A"]
    holes = {g.char: sum(len(s.holes) for s in g.shapes) for g in fino}
    assert holes == {"O": 1, "B": 2, "A": 1}
    assert all(s.area_liquida > 0 for g in fino for s in g.shapes)

    def vertices(result) -> int:
        return sum(
            len(s.outer.vertices) + sum(len(h.vertices) for h in s.holes)
            for g in result
            for s in g.shapes
        )

    grosso = FontToolsTextVectorizer(approximation=1.0).vectorize("OBA", _ARIAL, 50)
    assert vertices(grosso) < vertices(fino)
