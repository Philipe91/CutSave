import pytest
from app.domain.cut.contour_ops import offset_contour
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
