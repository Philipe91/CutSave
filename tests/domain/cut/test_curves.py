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


def _pilula(largura=120.0, altura=55.0, passos=24):
    """Retangulo arredondado tipo logo em pilula: duas retas longas emendadas
    em semicirculos (o caso que dava BARRIGA na faca)."""
    r = altura / 2.0
    cx0, cx1 = r, largura - r
    pts = []
    for k in range(passos + 1):  # ponta direita
        a = -math.pi / 2 + math.pi * k / passos
        pts.append(Point2D(cx1 + r * math.cos(a), r + r * math.sin(a)))
    for k in range(passos + 1):  # ponta esquerda
        a = math.pi / 2 + math.pi * k / passos
        pts.append(Point2D(cx0 + r * math.cos(a), r + r * math.sin(a)))
    return pts


def test_reta_longa_emendada_em_arco_nao_ganha_barriga():
    # A junta reta/arco NAO e canto (vira poucos graus), entao a tangente da
    # reta e puxada para o arco. Com a alca valendo corda/3, a corda longa
    # multiplicava esse errinho e a reta estufava para fora (0,5mm num logo
    # de 120mm). A alca limitada pelo vizinho curto mantem a reta reta.
    poly = flatten(cubic_segments(_pilula()), max_dev_mm=0.02)
    meio_da_reta = [p for p in poly if 35.0 < p.x < 85.0 and p.y < 5.0]
    assert meio_da_reta  # a borda de cima foi amostrada
    assert max(abs(p.y) for p in meio_da_reta) < 0.05  # antes: 0,53 mm


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
