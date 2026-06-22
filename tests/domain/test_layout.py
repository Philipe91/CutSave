from dataclasses import FrozenInstanceError

import pytest
from app.domain.geometry import Point2D
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.shared.errors import ValidationError


def _material():
    return Material(name="Adesivo", width=1000.0)


def test_layout_item_count_e_used_area():
    items = [
        PlacedItem("a1", Point2D(0, 0)),
        PlacedItem("a2", Point2D(50, 0)),
    ]
    layout = Layout(material=_material(), items=items, used_length=200.0)
    assert layout.item_count == 2
    assert layout.used_area == 1000.0 * 200.0


def test_layout_converte_items_para_tupla():
    layout = Layout(material=_material(), items=[PlacedItem("a1", Point2D(0, 0))])
    assert isinstance(layout.items, tuple)


def test_layout_used_length_nao_negativo():
    with pytest.raises(ValidationError):
        Layout(material=_material(), items=[], used_length=-1.0)


def test_layout_imutavel():
    layout = Layout(material=_material(), items=[], used_length=0.0)
    with pytest.raises(FrozenInstanceError):
        layout.used_length = 5.0
