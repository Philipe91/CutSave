import pytest
from app.domain.cut.rectangular import RectangularCutGenerator
from app.domain.geometry import BoundingBox, Point2D, Size
from app.shared.errors import ValidationError


def _area(w=100.0, h=50.0):
    return BoundingBox(0.0, 0.0, w, h)


def test_sem_offset_faca_no_limite_do_produto():
    cut = RectangularCutGenerator().generate(_area(100, 50))
    assert cut.origin == Point2D(0, 0)
    assert cut.size == Size(100, 50)
    assert len(cut.points) == 4


def test_offset_externo_cresce_para_fora():
    cut = RectangularCutGenerator().generate(_area(100, 50), offset_mm=5.0)
    assert cut.origin == Point2D(-5, -5)
    assert cut.size == Size(110, 60)


def test_offset_interno_encolhe():
    cut = RectangularCutGenerator().generate(_area(100, 50), offset_mm=-5.0)
    assert cut.origin == Point2D(5, 5)
    assert cut.size == Size(90, 40)


def test_offset_interno_excessivo_falha():
    with pytest.raises(ValidationError):
        RectangularCutGenerator().generate(_area(100, 50), offset_mm=-25.0)


def test_offset_interno_igual_ao_produto_falha():
    # altura 50, offset -25 -> 50 - 50 = 0 (invalido)
    with pytest.raises(ValidationError):
        RectangularCutGenerator().generate(_area(200, 50), offset_mm=-25.0)


def test_area_com_origem_deslocada():
    cut = RectangularCutGenerator().generate(BoundingBox(10, 20, 110, 70), offset_mm=0.0)
    assert cut.origin == Point2D(10, 20)
    assert cut.size == Size(100, 50)
