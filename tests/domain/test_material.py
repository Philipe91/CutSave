from dataclasses import FrozenInstanceError

import pytest
from app.domain.model.material import Material
from app.shared.errors import ValidationError


def test_material_valido_e_usable_width():
    m = Material(name="Adesivo", width=1000.0, margin=10.0, spacing=3.0, default_offset=2.0)
    assert m.usable_width == 980.0


def test_material_imutavel():
    m = Material(name="Lona", width=1500.0)
    with pytest.raises(FrozenInstanceError):
        m.width = 999.0


def test_material_exige_nome():
    with pytest.raises(ValidationError):
        Material(name="  ", width=1000.0)


@pytest.mark.parametrize("width", [0.0, -10.0])
def test_material_largura_positiva(width):
    with pytest.raises(ValidationError):
        Material(name="PVC", width=width)


def test_material_rejeita_margem_negativa():
    with pytest.raises(ValidationError):
        Material(name="ACM", width=1000.0, margin=-1.0)


def test_material_margem_nao_consome_largura():
    with pytest.raises(ValidationError):
        Material(name="PS", width=100.0, margin=50.0)
