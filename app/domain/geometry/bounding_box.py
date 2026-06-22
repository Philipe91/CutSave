from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.geometry.point import Point2D
from app.domain.geometry.size import Size
from app.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Retangulo envolvente alinhado aos eixos (mm), definido por min/max."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        if self.max_x < self.min_x or self.max_y < self.min_y:
            raise ValidationError("BoundingBox invalido: max menor que min.")

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point2D:
        return Point2D((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)

    @classmethod
    def from_points(cls, points: Iterable[Point2D]) -> BoundingBox:
        pts = list(points)
        if not pts:
            raise ValidationError("BoundingBox requer ao menos um ponto.")
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        return cls(min(xs), min(ys), max(xs), max(ys))

    def union(self, other: BoundingBox) -> BoundingBox:
        return BoundingBox(
            min(self.min_x, other.min_x),
            min(self.min_y, other.min_y),
            max(self.max_x, other.max_x),
            max(self.max_y, other.max_y),
        )

    def expanded(self, margin: float) -> BoundingBox:
        return BoundingBox(
            self.min_x - margin,
            self.min_y - margin,
            self.max_x + margin,
            self.max_y + margin,
        )

    def contains(self, point: Point2D) -> bool:
        return self.min_x <= point.x <= self.max_x and self.min_y <= point.y <= self.max_y
