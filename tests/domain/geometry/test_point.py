import math

import pytest
from app.domain.geometry import Point2D, Vector2D


def test_translated():
    assert Point2D(1, 2).translated(3, -1) == Point2D(4, 1)


def test_translated_by_vector():
    assert Point2D(1, 1).translated_by(Vector2D(2, 3)) == Point2D(3, 4)


def test_vector_to():
    assert Point2D(1, 1).vector_to(Point2D(4, 5)) == Vector2D(3, 4)


def test_distance_to():
    assert Point2D(0, 0).distance_to(Point2D(3, 4)) == 5.0


def test_rotated_90_em_torno_da_origem():
    r = Point2D(1, 0).rotated(90)
    assert r.x == pytest.approx(0, abs=1e-9)
    assert r.y == pytest.approx(1, abs=1e-9)


def test_rotated_em_torno_de_centro():
    r = Point2D(2, 1).rotated(180, around=Point2D(1, 1))
    assert r.x == pytest.approx(0, abs=1e-9)
    assert r.y == pytest.approx(1, abs=1e-9)


def test_scaled_em_torno_da_origem():
    assert Point2D(2, 3).scaled(2) == Point2D(4, 6)


def test_scaled_em_torno_de_centro():
    assert Point2D(2, 2).scaled(2, around=Point2D(1, 1)) == Point2D(3, 3)


def test_imutavel():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        Point2D(0, 0).x = 1


def test_rotacao_preserva_distancia():
    origem = Point2D(0, 0)
    p = Point2D(3, 4)
    assert p.rotated(37).distance_to(origem) == pytest.approx(p.distance_to(origem))


def test_full_turn_volta_ao_inicio():
    p = Point2D(5, 7)
    r = p.rotated(360)
    assert r.x == pytest.approx(5)
    assert r.y == pytest.approx(7)
    assert math.isclose(r.distance_to(p), 0, abs_tol=1e-9)
