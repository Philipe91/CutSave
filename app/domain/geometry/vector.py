from __future__ import annotations

import math
from dataclasses import dataclass

from app.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class Vector2D:
    """Deslocamento/direcao no plano (mm). Distinto de Point2D (posicao)."""

    x: float
    y: float

    @property
    def magnitude(self) -> float:
        return math.hypot(self.x, self.y)

    def __add__(self, other: Vector2D) -> Vector2D:
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2D) -> Vector2D:
        return Vector2D(self.x - other.x, self.y - other.y)

    def scaled(self, factor: float) -> Vector2D:
        return Vector2D(self.x * factor, self.y * factor)

    def dot(self, other: Vector2D) -> float:
        return self.x * other.x + self.y * other.y

    def normalized(self) -> Vector2D:
        m = self.magnitude
        if m == 0:
            raise ValidationError("Vetor nulo nao pode ser normalizado.")
        return Vector2D(self.x / m, self.y / m)

    def rotated(self, degrees: float) -> Vector2D:
        """Rotaciona o vetor (sentido anti-horario, graus)."""
        rad = math.radians(degrees)
        cos, sin = math.cos(rad), math.sin(rad)
        return Vector2D(self.x * cos - self.y * sin, self.x * sin + self.y * cos)
