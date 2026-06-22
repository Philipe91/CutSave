import pytest
from app.domain.geometry import BoundingBox, Point2D, Size
from app.shared.errors import ValidationError


def test_propriedades_basicas():
    bb = BoundingBox(0, 0, 40, 20)
    assert bb.width == 40
    assert bb.height == 20
    assert bb.area == 800
    assert bb.center == Point2D(20, 10)
    assert bb.size == Size(40, 20)


def test_from_points():
    pts = [Point2D(10, 5), Point2D(-2, 30), Point2D(7, 7)]
    bb = BoundingBox.from_points(pts)
    assert (bb.min_x, bb.min_y, bb.max_x, bb.max_y) == (-2, 5, 10, 30)


def test_from_points_vazio_falha():
    with pytest.raises(ValidationError):
        BoundingBox.from_points([])


def test_union():
    a = BoundingBox(0, 0, 10, 10)
    b = BoundingBox(5, 5, 20, 8)
    assert a.union(b) == BoundingBox(0, 0, 20, 10)


def test_expanded():
    assert BoundingBox(10, 10, 20, 20).expanded(5) == BoundingBox(5, 5, 25, 25)


def test_contains():
    bb = BoundingBox(0, 0, 10, 10)
    assert bb.contains(Point2D(5, 5))
    assert bb.contains(Point2D(0, 0))  # borda inclusiva
    assert not bb.contains(Point2D(11, 5))


def test_invalido_max_menor_que_min():
    with pytest.raises(ValidationError):
        BoundingBox(10, 0, 5, 5)
