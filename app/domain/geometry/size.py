from __future__ import annotations

from dataclasses import dataclass

from app.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class Size:
    """Dimensao em milimetros. Largura e altura devem ser positivas."""

    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValidationError("Dimensoes devem ser positivas (mm).")

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    def scaled(self, factor: float) -> Size:
        if factor <= 0:
            raise ValidationError("Fator de escala deve ser positivo.")
        return Size(self.width * factor, self.height * factor)

    def swapped(self) -> Size:
        """Troca largura por altura (equivale a rotacao de 90 graus)."""
        return Size(self.height, self.width)
