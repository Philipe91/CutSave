import pytest
from app.domain.cut.corner_marks import (
    CornerLMarkGenerator,
    CrossMarkGenerator,
    SquareMarkGenerator,
)
from app.domain.geometry import BoundingBox
from app.shared.errors import ValidationError

# bbox das facas 100x50 em (10,20); margem 15 -> quadro (-5,5)-(125,85)
BBOX = BoundingBox(10, 20, 110, 70)
CORNERS = {(-5.0, 5.0), (125.0, 5.0), (-5.0, 85.0), (125.0, 85.0)}


def test_quadrados_nos_4_cantos_do_quadro():
    marks = SquareMarkGenerator().generate(BBOX, margin_mm=15, size_mm=4)
    assert {(m.center.x, m.center.y) for m in marks} == CORNERS
    assert all(m.size == 4 for m in marks)


def test_quadrado_corners_fechados_no_lado_certo():
    (m, *_rest) = SquareMarkGenerator().generate(BBOX, margin_mm=15, size_mm=4)
    xs = [p.x for p in m.corners()]
    ys = [p.y for p in m.corners()]
    assert (min(xs), max(xs)) == (m.center.x - 2, m.center.x + 2)
    assert (min(ys), max(ys)) == (m.center.y - 2, m.center.y + 2)


def test_cruzes_2_segmentos_centrados_por_canto():
    segs = CrossMarkGenerator().generate(BBOX, margin_mm=15, size_mm=6)
    assert len(segs) == 8  # 4 cantos x (horizontal + vertical)
    # cruz do topo-esquerdo (-5,5): braco horizontal e vertical de 6mm centrados
    horiz = [s for s in segs if s.start.y == s.end.y == 5.0 and s.start.x == -8.0]
    vert = [s for s in segs if s.start.x == s.end.x == -5.0 and s.start.y == 2.0]
    assert horiz and horiz[0].end.x == -2.0
    assert vert and vert[0].end.y == 8.0


def test_l_de_canto_abraca_o_canto_com_abertura_para_fora():
    segs = CornerLMarkGenerator().generate(BBOX, margin_mm=15, size_mm=10)
    assert len(segs) == 8  # 4 cantos x 2 bracos
    # topo-esquerdo (-5,5): bracos saem do vertice PARA FORA (esquerda e cima)
    tl = [s for s in segs if (s.start.x, s.start.y) == (-5.0, 5.0)]
    ends = {(s.end.x, s.end.y) for s in tl}
    assert ends == {(-15.0, 5.0), (-5.0, -5.0)}
    # inferior-direito (125,85): bracos para direita e para baixo
    br = [s for s in segs if (s.start.x, s.start.y) == (125.0, 85.0)]
    assert {(s.end.x, s.end.y) for s in br} == {(135.0, 85.0), (125.0, 95.0)}


@pytest.mark.parametrize(
    "gen", [SquareMarkGenerator(), CrossMarkGenerator(), CornerLMarkGenerator()]
)
def test_validacao_margem_e_tamanho(gen):
    with pytest.raises(ValidationError):
        gen.generate(BBOX, margin_mm=-1, size_mm=5)
    with pytest.raises(ValidationError):
        gen.generate(BBOX, margin_mm=10, size_mm=0)
