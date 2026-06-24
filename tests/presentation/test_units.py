import pytest
from app.presentation import units


@pytest.fixture(autouse=True)
def _restore_unit():
    before = units.unit()
    yield
    units.set_unit(before)


def test_padrao_e_cm():
    # estado inicial do modulo: centimetros
    assert units.unit() in (units.CM, units.MM)


def test_conversao_mm_cm():
    units.set_unit(units.CM)
    assert units.from_mm(1500) == pytest.approx(150.0)
    assert units.to_mm(150) == pytest.approx(1500.0)


def test_conversao_mm_mm():
    units.set_unit(units.MM)
    assert units.from_mm(1500) == pytest.approx(1500.0)
    assert units.to_mm(1500) == pytest.approx(1500.0)


def test_fmt_len_cm():
    units.set_unit(units.CM)
    assert units.fmt_len(130) == "13.00 cm"
    assert units.fmt_len(130, with_unit=False) == "13.00"


def test_fmt_len_mm():
    units.set_unit(units.MM)
    assert units.fmt_len(130) == "130.0 mm"


def test_fmt_area_cm_e_mm():
    units.set_unit(units.CM)
    assert units.fmt_area(10000) == "100.00 cm²"  # 100 cm2
    units.set_unit(units.MM)
    assert units.fmt_area(10000) == "10000 mm²"


def test_fmt_xy():
    units.set_unit(units.CM)
    assert units.fmt_xy(100, 50) == "10.00, 5.00 cm"


def test_set_unit_invalido_ignora():
    units.set_unit(units.CM)
    units.set_unit("polegada")  # invalido: nao muda
    assert units.unit() == units.CM
