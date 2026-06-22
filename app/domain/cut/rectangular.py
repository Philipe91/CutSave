from __future__ import annotations

from app.domain.geometry import BoundingBox, Point2D, Rectangle, Size
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


class RectangularCutGenerator:
    """Gera uma faca retangular a partir da area do produto (BoundingBox).

    Offset assinado, em milimetros:
      - positivo  -> faca externa (cresce para fora);
      - negativo  -> faca interna (encolhe para dentro);
      - zero      -> faca no limite do produto.

    Usa apenas a camada geometrica (sem Shapely).
    """

    def generate(self, area: BoundingBox, offset_mm: float = 0.0) -> CutContour:
        width = area.width + 2 * offset_mm
        height = area.height + 2 * offset_mm
        if width <= 0 or height <= 0:
            raise ValidationError(
                "Offset interno maior ou igual ao tamanho do produto."
            )
        origin = Point2D(area.min_x - offset_mm, area.min_y - offset_mm)
        rectangle = Rectangle(origin, Size(width, height))
        return CutContour(rectangle.corners)
