from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.geometry.vector import Vector2D


@dataclass(frozen=True, slots=True)
class Point2D:
    """Posicao no plano em milimetros (unidade canonica do dominio)."""

    x: float
    y: float

    def translated(self, dx: float, dy: float) -> Point2D:
        return Point2D(self.x + dx, self.y + dy)

    def translated_by(self, vector: Vector2D) -> Point2D:
        return Point2D(self.x + vector.x, self.y + vector.y)

    def vector_to(self, other: Point2D) -> Vector2D:
        return Vector2D(other.x - self.x, other.y - self.y)

    def to_vector(self) -> Vector2D:
        return Vector2D(self.x, self.y)

    def distance_to(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def rotated(self, degrees: float, around: Point2D | None = None) -> Point2D:
        """Rotaciona o ponto em torno de 'around' (origem se None), anti-horario."""
        cx = around.x if around is not None else 0.0
        cy = around.y if around is not None else 0.0
        rad = math.radians(degrees)
        cos, sin = math.cos(rad), math.sin(rad)
        dx, dy = self.x - cx, self.y - cy
        return Point2D(cx + dx * cos - dy * sin, cy + dx * sin + dy * cos)

    def scaled(self, factor: float, around: Point2D | None = None) -> Point2D:
        """Escala a posicao em relacao a 'around' (origem se None)."""
        cx = around.x if around is not None else 0.0
        cy = around.y if around is not None else 0.0
        return Point2D(cx + (self.x - cx) * factor, cy + (self.y - cy) * factor)
