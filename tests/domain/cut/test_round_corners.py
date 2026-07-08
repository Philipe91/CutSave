"""Cantos arredondados da faca (round_corners) — fillet estilo Corel."""

import math

from app.domain.cut.contour_ops import round_corners
from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from shapely.geometry import Polygon


def _square(side=50.0):
    return CutContour([
        Point2D(0, 0), Point2D(side, 0), Point2D(side, side), Point2D(0, side)
    ])


def test_quadrado_ganha_cantos_redondos():
    out = round_corners(_square(), 5.0)
    assert len(out.points) > 4  # arcos criados
    # nenhum ponto fica NO canto vivo original (0,0): o mais perto e ~r*(1-1/sqrt2)
    menor = min(math.hypot(p.x, p.y) for p in out.points)
    assert menor > 1.0
    # a area diminui só o recorte dos 4 cantos (aprox. 4 * r^2 * (1 - pi/4))
    area = Polygon([(p.x, p.y) for p in out.points]).area
    esperado = 50.0 * 50.0 - 4 * 25.0 * (1 - math.pi / 4)
    assert abs(area - esperado) < 6.0


def test_raio_zero_nao_mexe():
    sq = _square()
    assert round_corners(sq, 0.0) is sq


def test_raio_grande_demais_e_ignorado_com_seguranca():
    sq = _square(side=50.0)
    out = round_corners(sq, 30.0)  # erosao de 30mm sumiria com a peca
    assert out.points == sq.points  # devolve o original, nao explode


def test_circulo_ja_liso_quase_nao_muda():
    n, r = 48, 20.0
    circ = CutContour([
        Point2D(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ])
    out = round_corners(circ, 2.0)
    a0 = Polygon([(p.x, p.y) for p in circ.points]).area
    a1 = Polygon([(p.x, p.y) for p in out.points]).area
    assert abs(a1 - a0) / a0 < 0.02  # variacao < 2%
