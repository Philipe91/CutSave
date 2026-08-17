import math

import pytest

from app.domain.geometry import Point2D
from app.domain.geometry.bezier import (
    BezierSegment,
    bezier_bounds,
    line_segment,
)


def _quarter_circle(r: float = 10.0) -> BezierSegment:
    """Arco de 90 graus de (r, 0) a (0, r), a aproximacao classica de Bezier."""
    k = 4.0 / 3.0 * (math.sqrt(2.0) - 1.0) * r
    return BezierSegment(
        Point2D(r, 0.0), Point2D(r, k), Point2D(k, r), Point2D(0.0, r)
    )


def test_line_segment_tem_controles_sobre_a_corda():
    seg = line_segment(Point2D(0.0, 0.0), Point2D(9.0, 0.0))
    assert seg.is_line()


def test_arco_nao_e_reta():
    assert not _quarter_circle().is_line()


def test_reversed_troca_extremos_e_controles():
    seg = _quarter_circle()
    rev = seg.reversed()
    assert rev.p0 == seg.p1
    assert rev.c1 == seg.c2
    assert rev.c2 == seg.c1
    assert rev.p1 == seg.p0


def test_reversed_percorre_a_mesma_curva_ao_contrario():
    seg = _quarter_circle()
    rev = seg.reversed()
    for k in range(11):
        t = k / 10
        a = seg.point_at(t)
        b = rev.point_at(1.0 - t)
        assert a.x == pytest.approx(b.x, abs=1e-12)
        assert a.y == pytest.approx(b.y, abs=1e-12)


def test_translated_desloca_os_quatro_pontos():
    seg = _quarter_circle().translated(3.0, -2.0)
    base = _quarter_circle()
    assert seg.p0.x == pytest.approx(base.p0.x + 3.0)
    assert seg.c1.y == pytest.approx(base.c1.y - 2.0)
    assert seg.c2.x == pytest.approx(base.c2.x + 3.0)
    assert seg.p1.y == pytest.approx(base.p1.y - 2.0)


def test_rotated_360_em_quatro_giros_volta_ao_original():
    seg = _quarter_circle()
    girado = seg
    for _ in range(4):
        girado = girado.rotated(90.0, around=Point2D(0.0, 0.0))
    for a, b in zip(
        (girado.p0, girado.c1, girado.c2, girado.p1),
        (seg.p0, seg.c1, seg.c2, seg.p1),
        strict=True,
    ):
        assert a.x == pytest.approx(b.x, abs=1e-9)
        assert a.y == pytest.approx(b.y, abs=1e-9)


def test_bezier_bounds_e_exata_nao_a_casca_de_controle():
    """O arco de 90 graus de raio 10 vai de (10,0) a (0,10) e NAO passa por
    (10,10) — a casca de controle daria o canto errado; os extremos exatos dao
    a caixa justa do arco."""
    box = bezier_bounds([_quarter_circle(10.0)])
    assert box.min_x == pytest.approx(0.0, abs=1e-9)
    assert box.min_y == pytest.approx(0.0, abs=1e-9)
    assert box.max_x == pytest.approx(10.0, abs=1e-9)
    assert box.max_y == pytest.approx(10.0, abs=1e-9)


def test_bezier_bounds_de_arco_que_estufa_alem_dos_extremos():
    """Meia-volta: de (10,0) a (-10,0) passando por cima. O topo real fica em
    0.75 da altura dos controles, entao a caixa NAO e a dos extremos."""
    seg = BezierSegment(
        Point2D(10.0, 0.0), Point2D(10.0, 8.0), Point2D(-10.0, 8.0), Point2D(-10.0, 0.0)
    )
    box = bezier_bounds([seg])
    assert box.max_y == pytest.approx(6.0, abs=1e-9)  # 0.75 * 8
    assert box.min_y == pytest.approx(0.0, abs=1e-9)


def test_bezier_bounds_vazio_recusa():
    from app.shared.errors import ValidationError

    with pytest.raises(ValidationError):
        bezier_bounds([])
