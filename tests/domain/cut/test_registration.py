import pytest
from app.domain.cut.registration import RegistrationMark, RegistrationMarkGenerator
from app.domain.geometry import BoundingBox
from app.shared.errors import ValidationError


def _marks(margin=15.0, diameter=6.0):
    bbox = BoundingBox(0, 0, 100, 50)
    return RegistrationMarkGenerator().generate(
        bbox, margin_mm=margin, diameter_mm=diameter
    )


def test_gera_cinco_marcas():
    assert len(_marks()) == 5


def test_quadro_afastado_15mm_das_facas():
    marks = _marks(margin=15.0)
    xs = {round(m.center.x, 3) for m in marks}
    ys = {round(m.center.y, 3) for m in marks}
    assert min(xs) == -15.0 and max(xs) == 115.0  # 100 + 15 dos dois lados
    assert min(ys) == -15.0 and max(ys) == 65.0


def test_tres_no_topo_e_duas_no_fundo():
    marks = _marks()
    top = min(m.center.y for m in marks)
    bottom = max(m.center.y for m in marks)
    no_topo = [m for m in marks if m.center.y == top]
    no_fundo = [m for m in marks if m.center.y == bottom]
    assert len(no_topo) == 3
    assert len(no_fundo) == 2
    # uma das marcas do topo fica no meio (centro x do quadro)
    cx = (min(m.center.x for m in marks) + max(m.center.x for m in marks)) / 2
    assert any(round(m.center.x, 3) == round(cx, 3) for m in no_topo)


def test_raio_e_metade_do_diametro():
    mark = _marks(diameter=6.0)[0]
    assert isinstance(mark, RegistrationMark)
    assert mark.diameter == 6.0
    assert mark.radius == 3.0


def test_diametro_invalido_falha():
    with pytest.raises(ValidationError):
        _marks(diameter=0.0)


def test_margem_negativa_falha():
    with pytest.raises(ValidationError):
        _marks(margin=-1.0)
