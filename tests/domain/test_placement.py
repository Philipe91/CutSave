from dataclasses import FrozenInstanceError

import pytest
from app.domain.geometry import Point2D
from app.domain.model.placement import PlacedItem, Rotation
from app.shared.errors import ValidationError


def test_placed_item_default_sem_rotacao():
    item = PlacedItem(artwork_id="a1", position=Point2D(5, 5))
    assert item.rotation is Rotation.NONE


def test_rotation_valores():
    assert [r.value for r in Rotation] == [0, 90, 180, 270]


def test_placed_item_com_rotacao():
    item = PlacedItem(artwork_id="a1", position=Point2D(0, 0), rotation=Rotation.CW90)
    assert int(item.rotation) == 90


def test_placed_item_exige_artwork_id():
    with pytest.raises(ValidationError):
        PlacedItem(artwork_id="", position=Point2D(0, 0))


def test_placed_item_imutavel():
    item = PlacedItem(artwork_id="a1", position=Point2D(0, 0))
    with pytest.raises(FrozenInstanceError):
        item.rotation = Rotation.HALF
