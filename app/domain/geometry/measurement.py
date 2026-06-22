from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.shared.errors import ValidationError

_MM_PER_INCH = 25.4
_POINTS_PER_INCH = 72.0


class Unit(Enum):
    MM = "mm"
    CM = "cm"
    INCH = "inch"
    POINT = "point"


_MM_PER_UNIT = {
    Unit.MM: 1.0,
    Unit.CM: 10.0,
    Unit.INCH: _MM_PER_INCH,
    Unit.POINT: _MM_PER_INCH / _POINTS_PER_INCH,
}


@dataclass(frozen=True, slots=True)
class Measurement:
    """Medida com unidade, convertendo para milimetros (unidade canonica).

    Usada nas bordas (importacao) para normalizar pt/polegada/pixel para mm.
    """

    value: float
    unit: Unit = Unit.MM

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValidationError("Medida nao pode ser negativa.")

    @property
    def millimeters(self) -> float:
        return self.value * _MM_PER_UNIT[self.unit]

    @classmethod
    def mm(cls, value: float) -> Measurement:
        return cls(value, Unit.MM)

    @classmethod
    def cm(cls, value: float) -> Measurement:
        return cls(value, Unit.CM)

    @classmethod
    def inch(cls, value: float) -> Measurement:
        return cls(value, Unit.INCH)

    @classmethod
    def points(cls, value: float) -> Measurement:
        return cls(value, Unit.POINT)

    @classmethod
    def from_pixels(cls, pixels: float, dpi: float) -> Measurement:
        """Converte pixels para mm dado o DPI (mm = pixels / dpi * 25.4)."""
        if dpi <= 0:
            raise ValidationError("DPI deve ser positivo.")
        if pixels < 0:
            raise ValidationError("Pixels nao pode ser negativo.")
        return cls(pixels / dpi * _MM_PER_INCH, Unit.MM)
