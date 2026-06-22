import math

import pytest
from app.domain.cut.vector import VectorContourGenerator
from app.domain.geometry import Polygon as GeoPolygon
from app.shared.errors import ValidationError


def _circle(cx, cy, r, n=64):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def _ellipse(cx, cy, a, b, n=64):
    return [(cx + a * math.cos(2 * math.pi * i / n), cy + b * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def _square(x0, y0, side):
    return [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)]


def _area(cut):
    return GeoPolygon(cut.points).area


def test_circulo():
    cut = VectorContourGenerator().generate([_circle(0, 0, 50)])
    assert _area(cut) == pytest.approx(math.pi * 50**2, rel=0.02)


def test_elipse():
    cut = VectorContourGenerator().generate([_ellipse(0, 0, 60, 30)])
    assert _area(cut) == pytest.approx(math.pi * 60 * 30, rel=0.02)


def test_poligono_simples():
    cut = VectorContourGenerator().generate([_square(0, 0, 100)])
    assert _area(cut) == pytest.approx(10000)


def test_geometria_composta_uniao():
    # dois quadrados sobrepostos: 100x100 + 100x100 - 50x100 = 15000
    cut = VectorContourGenerator().generate([_square(0, 0, 100), _square(50, 0, 100)])
    assert _area(cut) == pytest.approx(15000, rel=0.001)


def test_elementos_internos_sao_ignorados():
    # quadrado grande + quadradinho dentro -> contorno = quadrado grande
    cut = VectorContourGenerator().generate([_square(0, 0, 100), _square(40, 40, 20)])
    assert _area(cut) == pytest.approx(10000)


def test_marcas_separadas_sao_descartadas():
    # circulo grande + marca pequena longe -> mantem o maior componente
    cut = VectorContourGenerator().generate([_circle(0, 0, 50), _square(500, 500, 2)])
    assert _area(cut) == pytest.approx(math.pi * 50**2, rel=0.02)


def test_corrige_anel_auto_intersectante():
    # "gravata borboleta" (bowtie): invalido -> buffer(0) corrige
    bowtie = [(0, 0), (10, 10), (10, 0), (0, 10)]
    cut = VectorContourGenerator().generate([bowtie])
    assert _area(cut) > 0


def test_ignora_anel_de_area_zero():
    # pontos colineares (area zero) sao descartados; quadrado valido prevalece
    colinear = [(0, 0), (5, 0), (10, 0)]
    cut = VectorContourGenerator().generate([colinear, _square(0, 0, 20)])
    assert _area(cut) == pytest.approx(400)


def test_sem_geometria_utilizavel_falha():
    with pytest.raises(ValidationError):
        VectorContourGenerator().generate([])


def test_aneis_degenerados_sao_ignorados():
    with pytest.raises(ValidationError):
        VectorContourGenerator().generate([[(0, 0), (1, 1)]])  # < 3 pontos


def test_contorno_e_fechado_sem_ponto_duplicado():
    cut = VectorContourGenerator().generate([_square(0, 0, 10)])
    assert cut.points[0] != cut.points[-1]  # fechamento implicito, sem duplicar
