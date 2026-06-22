from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.geometry.bounding_box import BoundingBox
from app.domain.geometry.point import Point2D
from app.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class Polygon:
    """Poligono fechado (anel de vertices em mm). Fechamento implicito."""

    vertices: tuple[Point2D, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertices", tuple(self.vertices))
        if len(self.vertices) < 3:
            raise ValidationError("Polygon requer ao menos 3 vertices.")

    @property
    def signed_area(self) -> float:
        """Area com sinal (shoelace). Positiva = anti-horario."""
        total = 0.0
        n = len(self.vertices)
        for i in range(n):
            a = self.vertices[i]
            b = self.vertices[(i + 1) % n]
            total += a.x * b.y - b.x * a.y
        return total / 2

    @property
    def area(self) -> float:
        return abs(self.signed_area)

    @property
    def is_clockwise(self) -> bool:
        return self.signed_area < 0

    @property
    def perimeter(self) -> float:
        n = len(self.vertices)
        return sum(self.vertices[i].distance_to(self.vertices[(i + 1) % n]) for i in range(n))

    @property
    def centroid(self) -> Point2D:
        a = self.signed_area
        if a == 0:
            cx = sum(p.x for p in self.vertices) / len(self.vertices)
            cy = sum(p.y for p in self.vertices) / len(self.vertices)
            return Point2D(cx, cy)
        cx = cy = 0.0
        n = len(self.vertices)
        for i in range(n):
            p = self.vertices[i]
            q = self.vertices[(i + 1) % n]
            cross = p.x * q.y - q.x * p.y
            cx += (p.x + q.x) * cross
            cy += (p.y + q.y) * cross
        return Point2D(cx / (6 * a), cy / (6 * a))

    @property
    def bounding_box(self) -> BoundingBox:
        return BoundingBox.from_points(self.vertices)

    def translated(self, dx: float, dy: float) -> Polygon:
        return Polygon(tuple(p.translated(dx, dy) for p in self.vertices))

    def rotated(self, degrees: float, around: Point2D | None = None) -> Polygon:
        center = around if around is not None else self.centroid
        return Polygon(tuple(p.rotated(degrees, center) for p in self.vertices))

    def scaled(self, factor: float, around: Point2D | None = None) -> Polygon:
        center = around if around is not None else self.centroid
        return Polygon(tuple(p.scaled(factor, center) for p in self.vertices))

    def contains(self, point: Point2D) -> bool:
        """Teste ponto-dentro-do-poligono por ray casting (borda nao garantida)."""
        x, y = point.x, point.y
        inside = False
        n = len(self.vertices)
        j = n - 1
        for i in range(n):
            xi, yi = self.vertices[i].x, self.vertices[i].y
            xj, yj = self.vertices[j].x, self.vertices[j].y
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    @classmethod
    def from_points(cls, points: Iterable[Point2D]) -> Polygon:
        return cls(tuple(points))
