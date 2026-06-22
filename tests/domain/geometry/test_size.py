import pytest
from app.domain.geometry import Size
from app.shared.errors import ValidationError


def test_area_e_aspect_ratio():
    s = Size(40, 20)
    assert s.area == 800
    assert s.aspect_ratio == 2.0


def test_scaled():
    assert Size(10, 5).scaled(2) == Size(20, 10)


def test_swapped():
    assert Size(40, 20).swapped() == Size(20, 40)


@pytest.mark.parametrize("w,h", [(0, 5), (5, 0), (-1, 5)])
def test_rejeita_nao_positivo(w, h):
    with pytest.raises(ValidationError):
        Size(w, h)


def test_scaled_fator_invalido():
    with pytest.raises(ValidationError):
        Size(10, 10).scaled(0)
