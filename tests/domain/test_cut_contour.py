import pytest
from app.domain.geometry import Point2D, Size
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


def _retangulo():
    return CutContour(
        [Point2D(0, 0), Point2D(40, 0), Point2D(40, 20), Point2D(0, 20)]
    )


def test_lista_e_convertida_para_tupla():
    c = _retangulo()
    assert isinstance(c.points, tuple)


def test_bounding_box_origin_e_size():
    c = CutContour(
        [Point2D(10, 5), Point2D(50, 5), Point2D(50, 25), Point2D(10, 25)]
    )
    assert c.origin == Point2D(10, 5)
    assert c.size == Size(40, 20)


def test_minimo_de_tres_pontos():
    with pytest.raises(ValidationError):
        CutContour([Point2D(0, 0), Point2D(1, 1)])


def test_contour_igualdade():
    assert _retangulo() == _retangulo()
