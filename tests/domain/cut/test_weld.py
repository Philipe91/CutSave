"""Solda de facas que se invadem (weld_contours, estilo Contorno do Corel)."""

import math

from app.domain.cut.contour_ops import weld_contours
from app.domain.model.cut_contour import CutContour
from app.domain.geometry import Point2D
from shapely.geometry import Polygon


def _circle(cx, cy, r=10.0, n=36):
    return CutContour([
        Point2D(cx + r * math.cos(2 * math.pi * i / n),
                cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ])


def _area(contour):
    return Polygon([(p.x, p.y) for p in contour.points]).area


def test_facas_que_se_invadem_viram_uma_so():
    a, b = _circle(0, 0), _circle(12, 0)  # raio 10, centros a 12mm: se invadem
    out = weld_contours([a, b])
    assert len(out) == 1  # soldou
    # a uniao e maior que cada uma e menor que a soma (tem sobreposicao)
    assert _area(out[0]) > _area(a)
    assert _area(out[0]) < _area(a) + _area(b)


def test_facas_separadas_ficam_intactas():
    a, b = _circle(0, 0), _circle(50, 0)  # longe: nada muda
    out = weld_contours([a, b])
    assert len(out) == 2
    assert out[0].points == a.points or out[0].points == b.points  # mesmos nos


def test_misto_solda_so_quem_se_choca():
    a, b = _circle(0, 0), _circle(12, 0)      # dupla que se invade
    c = _circle(100, 0)                        # isolada
    out = weld_contours([a, b, c])
    assert len(out) == 2
    assert _area(out[0]) > _area(out[1])       # maior primeiro (uniao)
    assert abs(_area(out[1]) - _area(c)) < 1e-6  # isolada intacta


def test_encostar_sem_invadir_nao_solda():
    a, b = _circle(0, 0, r=10), _circle(20, 0, r=10)  # tangentes (tocam num ponto)
    out = weld_contours([a, b])
    assert len(out) == 2


def test_entrada_unica_passa_direto():
    a = _circle(0, 0)
    assert weld_contours([a]) == [a]
    assert weld_contours([]) == []
