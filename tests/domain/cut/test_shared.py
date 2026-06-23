from app.domain.cut.shared import Segment, build_shared_grid
from app.domain.geometry import BoundingBox, Point2D


def test_vazio_retorna_lista_vazia():
    assert build_shared_grid([]) == []


def test_peca_unica_degrada_para_contorno():
    segs = build_shared_grid([BoundingBox(0, 0, 10, 10)])
    # 2 verticais (x=0, x=10) + 2 horizontais (y=0, y=10)
    assert len(segs) == 4
    assert Segment(Point2D(0, 0), Point2D(0, 10)) in segs
    assert Segment(Point2D(0, 10), Point2D(10, 10)) in segs


def test_grade_2x2_compartilha_linha_no_meio_do_vao():
    cells = [
        BoundingBox(0, 0, 10, 10),
        BoundingBox(12, 0, 22, 10),
        BoundingBox(0, 12, 10, 22),
        BoundingBox(12, 12, 22, 22),
    ]
    segs = build_shared_grid(cells)
    # 3 verticais (0, 11, 22) + 3 horizontais (0, 11, 22)
    assert len(segs) == 6
    # separador interno no meio do vao (gap de 10 a 12 -> 11), de fora a fora
    assert Segment(Point2D(11, 0), Point2D(11, 22)) in segs
    assert Segment(Point2D(0, 11), Point2D(22, 11)) in segs


def test_linha_horizontal_vai_de_fora_a_fora():
    cells = [BoundingBox(0, 0, 10, 50), BoundingBox(110, 0, 120, 50)]
    segs = build_shared_grid(cells)
    horizontais = [s for s in segs if s.start.y == s.end.y]
    for s in horizontais:
        assert s.start.x == 0 and s.end.x == 120
