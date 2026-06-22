from __future__ import annotations

from dataclasses import dataclass

from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class Layout:
    """Resultado imutavel de um nesting: pecas posicionadas sobre um material.

    'used_length' e o comprimento de material consumido (mm), no eixo aberto.
    """

    material: Material
    items: tuple[PlacedItem, ...]
    used_length: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        if self.used_length < 0:
            raise ValidationError("used_length nao pode ser negativo (mm).")

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def used_area(self) -> float:
        """Area de material consumida: largura total x comprimento usado (mm2)."""
        return self.material.width * self.used_length
