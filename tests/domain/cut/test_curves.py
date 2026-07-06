"""Curvas Bezier da faca (cubic_segments): suaviza curvas SEM estragar retas."""

import math

from app.domain.cut.curves import BezierSegment, cubic_segments, flatten, has_curves
from app.domain.geometry import Point2D


def _square():
    return [Point2D(0, 0), Point2D(50, 0), Point2D(50, 50), Point2D(0, 50)]


def _polygon_circle(n=24, r=15.0):
    return [
        Point2D(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def test_retangulo_continua_reto_e_com_cantos_vivos():
    segs = cubic_segments(_square())
    assert len(segs) == 4
    assert all(s.is_line() for s in segs)  # controles sobre a corda = reta exata
    assert not has_curves(segs)  # exportadores mantem polyline


def test_circulo_vira_curva_passando_pelos_nos():
    pts = _polygon_circle()
    segs = cubic_segments(pts)
    assert has_curves(segs)
    assert len(segs) == len(pts)  # a contagem de NOS nao muda
    for s, a in zip(segs, pts):
        assert (s.p0.x, s.p0.y) == (a.x, a.y)  # a curva passa EXATO pelos nos


def test_circulo_suavizado_fica_mais_perto_do_circulo_ideal():
    # o meio de cada corda reta afunda ~sagitta; a Bezier deve recuperar boa
    # parte disso (curva "enche" onde a corda cortava caminho)
    pts = _polygon_circle(n=16, r=15.0)
    segs = cubic_segments(pts)
    corda_dev = []
    bezier_dev = []
    for s in segs:
        mx, my = (s.p0.x + s.p1.x) / 2, (s.p0.y + s.p1.y) / 2
        corda_dev.append(abs(math.hypot(mx, my) - 15.0))
        # ponto medio da Bezier (t=0.5)
        bx = (s.p0.x + 3 * s.c1.x + 3 * s.c2.x + s.p1.x) / 8
        by = (s.p0.y + 3 * s.c1.y + 3 * s.c2.y + s.p1.y) / 8
        bezier_dev.append(abs(math.hypot(bx, by) - 15.0))
    assert max(bezier_dev) < max(corda_dev) / 4  # >=4x mais fiel que a corda


def test_canto_em_L_preservado_no_meio_da_curva():
    # meia-lua com um canto reto: o canto (0,0) nao pode ser arredondado
    pts = [Point2D(0, 0), Point2D(30, 0)] + [
        Point2D(15 + 15 * math.cos(a), 15 * math.sin(a))
        for a in [math.pi / 6 * k for k in range(1, 6)]
    ]
    segs = cubic_segments(pts)
    seg_saida = segs[0]  # (0,0) -> (30,0): reta da base
    assert seg_saida.is_line(tol=1e-6)


def test_flatten_respeita_o_desvio():
    segs = cubic_segments(_polygon_circle())
    dense = flatten(segs, max_dev_mm=0.05)
    assert len(dense) > len(segs)  # amostrou mais fino nas curvas


def test_degenerado_devolve_vazio():
    assert cubic_segments([Point2D(0, 0), Point2D(1, 1)]) == []
    assert cubic_segments([]) == []


def test_is_line_detecta_controles_fora_da_corda():
    reto = BezierSegment(Point2D(0, 0), Point2D(1, 0), Point2D(2, 0), Point2D(3, 0))
    curvo = BezierSegment(Point2D(0, 0), Point2D(1, 2), Point2D(2, 2), Point2D(3, 0))
    assert reto.is_line() and not curvo.is_line()
