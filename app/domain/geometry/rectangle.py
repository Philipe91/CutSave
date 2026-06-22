from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.geometry.bounding_box import BoundingBox
from app.domain.geometry.point import Point2D
from app.domain.geometry.size import Size

if TYPE_CHECKING:
    from app.domain.geometry.polygon import Polygon


@dataclass(frozen=True, slots=True)
class Rectangle:
    """Retangulo alinhado aos eixos. 'origin' e o canto (min x, min y), em mm."""

    origin: Point2D
    size: Size

    @property
    def width(self) -> float:
        return self.size.width

    @property
    def height(self) -> float:
        return self.size.height

    @property
    def area(self) -> float:
        return self.size.area

    @property
    def min_x(self) -> float:
        return self.origin.x

    @property
    def min_y(self) -> float:
        return self.origin.y

    @property
    def max_x(self) -> float:
        return self.origin.x + self.size.width

    @property
    def max_y(self) -> float:
        return self.origin.y + self.size.height

    @property
    def center(self) -> Point2D:
        return Point2D(self.origin.x + self.width / 2, self.origin.y + self.height / 2)

    @property
    def corners(self) -> tuple[Point2D, Point2D, Point2D, Point2D]:
        return (
            Point2D(self.min_x, self.min_y),
            Point2D(self.max_x, self.min_y),
            Point2D(self.max_x, self.max_y),
            Point2D(self.min_x, self.max_y),
        )

    @property
    def bounding_box(self) -> BoundingBox:
        return BoundingBox(self.min_x, self.min_y, self.max_x, self.max_y)

    def translated(self, dx: float, dy: float) -> Rectangle:
        return Rectangle(self.origin.translated(dx, dy), self.size)

    def scaled(self, factor: float) -> Rectangle:
        """Escala as dimensoes mantendo a origem fixa."""
        return Rectangle(self.origin, self.size.scaled(factor))

    def contains(self, point: Point2D) -> bool:
        return self.min_x <= point.x <= self.max_x and self.min_y <= point.y <= self.max_y

    def intersects(self, other: Rectangle) -> bool:
        return not (
            self.max_x < other.min_x
            or other.max_x < self.min_x
            or self.max_y < other.min_y
            or other.max_y < self.min_y
        )

    def to_polygon(self) -> Polygon:
        from app.domain.geometry.polygon import Polygon

        return Polygon(self.corners)
