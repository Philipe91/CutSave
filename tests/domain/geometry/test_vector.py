import pytest
from app.domain.geometry import Vector2D
from app.shared.errors import ValidationError


def test_magnitude():
    assert Vector2D(3, 4).magnitude == 5.0


def test_soma_e_subtracao():
    assert Vector2D(1, 2) + Vector2D(3, 4) == Vector2D(4, 6)
    assert Vector2D(5, 5) - Vector2D(1, 2) == Vector2D(4, 3)


def test_scaled():
    assert Vector2D(2, 3).scaled(2) == Vector2D(4, 6)


def test_dot():
    assert Vector2D(1, 2).dot(Vector2D(3, 4)) == 11.0


def test_normalized_tem_magnitude_unitaria():
    n = Vector2D(0, 5).normalized()
    assert n == Vector2D(0, 1)
    assert n.magnitude == pytest.approx(1.0)


def test_normalized_vetor_nulo_falha():
    with pytest.raises(ValidationError):
        Vector2D(0, 0).normalized()


def test_rotated_90():
    r = Vector2D(1, 0).rotated(90)
    assert r.x == pytest.approx(0, abs=1e-9)
    assert r.y == pytest.approx(1, abs=1e-9)
