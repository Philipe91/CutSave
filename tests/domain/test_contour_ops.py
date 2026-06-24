import pytest
from app.domain.cut.contour_ops import offset_contour, smooth_contour
from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


def _square(side):
    return CutContour([
        Point2D(0, 0), Point2D(side, 0), Point2D(side, side), Point2D(0, side)
    ])


def test_offset_zero_devolve_o_mesmo_contorno():
    c = _square(10)
    assert offset_contour(c, 0) is c


def test_offset_positivo_cresce():
    out = offset_contour(_square(10), 2)
    assert out.size.width == pytest.approx(14, abs=0.01)
    assert out.size.height == pytest.approx(14, abs=0.01)


def test_offset_negativo_encolhe():
    out = offset_contour(_square(10), -2)
    assert out.size.width == pytest.approx(6, abs=0.01)


def test_encolher_demais_levanta():
    with pytest.raises(ValidationError):
        offset_contour(_square(10), -10)


def test_suavizar_zero_nao_altera():
    c = _square(10)
    assert smooth_contour(c, 0) is c


def test_suavizar_arredonda_cantos_e_aumenta_pontos():
    out = smooth_contour(_square(10), 1)
    # Chaikin: cada iteracao dobra os pontos (4 -> 8)
    assert len(out.points) == 8
    # nenhum ponto fica no canto original (0,0): os cantos foram cortados
    assert all(not (p.x == 0 and p.y == 0) for p in out.points)


def test_suavizar_mais_iteracoes_mais_pontos():
    p1 = len(smooth_contour(_square(10), 1).points)
    p2 = len(smooth_contour(_square(10), 2).points)
    assert p2 > p1


def test_suavizar_mantem_dentro_da_caixa_original():
    out = smooth_contour(_square(10), 3)
    xs = [p.x for p in out.points]
    ys = [p.y for p in out.points]
    assert min(xs) >= -0.001 and max(xs) <= 10.001
    assert min(ys) >= -0.001 and max(ys) <= 10.001
