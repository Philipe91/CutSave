import pytest
from app.domain.geometry import Measurement, Unit
from app.shared.errors import ValidationError


def test_mm_identidade():
    assert Measurement.mm(123.0).millimeters == 123.0


def test_cm_para_mm():
    assert Measurement.cm(5).millimeters == 50.0


def test_inch_para_mm():
    assert Measurement.inch(1).millimeters == pytest.approx(25.4)


def test_point_para_mm():
    # 72 pt = 1 polegada = 25.4 mm
    assert Measurement.points(72).millimeters == pytest.approx(25.4)


def test_from_pixels():
    # 300 px a 300 dpi = 1 polegada = 25.4 mm
    assert Measurement.from_pixels(300, dpi=300).millimeters == pytest.approx(25.4)


def test_unit_default_mm():
    assert Measurement(10).unit is Unit.MM


def test_valor_negativo_falha():
    with pytest.raises(ValidationError):
        Measurement(-1)


def test_from_pixels_dpi_invalido():
    with pytest.raises(ValidationError):
        Measurement.from_pixels(100, dpi=0)
