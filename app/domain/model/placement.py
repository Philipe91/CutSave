from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from app.domain.geometry import Point2D
from app.shared.errors import ValidationError


class Rotation(IntEnum):
    NONE = 0
    CW90 = 90
    HALF = 180
    CCW270 = 270


@dataclass(frozen=True, slots=True)
class PlacedItem:
    """Instancia de uma arte posicionada num layout.

    Referencia a arte por id (flyweight): muitas copias compartilham um Artwork.
    'position' e a origem da peca em mm.
    """

    artwork_id: str
    position: Point2D
    rotation: Rotation = Rotation.NONE

    def __post_init__(self) -> None:
        if not self.artwork_id:
            raise ValidationError("PlacedItem requer artwork_id.")
