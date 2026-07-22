from __future__ import annotations

from dataclasses import dataclass

from app.domain.cut.shared import Segment
from app.domain.geometry import BoundingBox, Point2D
from app.shared.errors import ValidationError

DEFAULT_MARGIN_MM = 15.0
DEFAULT_SIZE_MM = 6.0
DEFAULT_THICKNESS_MM = 0.8


@dataclass(frozen=True, slots=True)
class SquareMark:
    """Marca de registro quadrada CHEIA (mm). 'center' e o centro; 'size' o lado."""

    center: Point2D
    size: float

    @property
    def half(self) -> float:
        return self.size / 2.0

    def corners(self) -> tuple[Point2D, Point2D, Point2D, Point2D]:
        """Cantos do quadrado (horario, a partir do topo-esquerdo)."""
        h, c = self.half, self.center
        return (
            Point2D(c.x - h, c.y - h), Point2D(c.x + h, c.y - h),
            Point2D(c.x + h, c.y + h), Point2D(c.x - h, c.y + h),
        )


def _frame_corners(
    cuts: BoundingBox, margin_mm: float, size_mm: float
) -> tuple[tuple[Point2D, float, float], ...]:
    """4 cantos do quadro afastado da bbox + direcao PARA FORA (sx, sy) de cada um.

    Coordenadas da chapa (origem no topo-esquerdo, y cresce para baixo).
    """
    if margin_mm < 0:
        raise ValidationError("Afastamento das marcas nao pode ser negativo (mm).")
    if size_mm <= 0:
        raise ValidationError("Tamanho das marcas deve ser positivo (mm).")
    frame = cuts.expanded(margin_mm)
    x0, y0, x1, y1 = frame.min_x, frame.min_y, frame.max_x, frame.max_y
    return (
        (Point2D(x0, y0), -1.0, -1.0),  # topo-esquerdo
        (Point2D(x1, y0), 1.0, -1.0),   # topo-direito
        (Point2D(x0, y1), -1.0, 1.0),   # inferior-esquerdo
        (Point2D(x1, y1), 1.0, 1.0),    # inferior-direito
    )


class SquareMarkGenerator:
    """4 quadrados cheios nos cantos do bbox das facas (padrao Summa/OPOS)."""

    def generate(
        self,
        cuts: BoundingBox,
        *,
        margin_mm: float = DEFAULT_MARGIN_MM,
        size_mm: float = DEFAULT_SIZE_MM,
    ) -> list[SquareMark]:
        return [
            SquareMark(corner, size_mm)
            for corner, _sx, _sy in _frame_corners(cuts, margin_mm, size_mm)
        ]


class CrossMarkGenerator:
    """4 cruzes nos cantos (padrao AOKE/iECHO): 2 segmentos centrados por canto."""

    def generate(
        self,
        cuts: BoundingBox,
        *,
        margin_mm: float = DEFAULT_MARGIN_MM,
        size_mm: float = DEFAULT_SIZE_MM,
    ) -> list[Segment]:
        segments: list[Segment] = []
        for corner, _sx, _sy in _frame_corners(cuts, margin_mm, size_mm):
            h = size_mm / 2.0
            segments.append(
                Segment(Point2D(corner.x - h, corner.y), Point2D(corner.x + h, corner.y))
            )
            segments.append(
                Segment(Point2D(corner.x, corner.y - h), Point2D(corner.x, corner.y + h))
            )
        return segments


class CornerLMarkGenerator:
    """4 marcas em L abracando os cantos (padrao Graphtec ARMS Type 1 / Roland).

    Sem quadro (difere da Mimaki): o vertice do L toca o canto do quadro
    afastado e os dois bracos abrem PARA FORA da arte.
    """

    def generate(
        self,
        cuts: BoundingBox,
        *,
        margin_mm: float = DEFAULT_MARGIN_MM,
        size_mm: float = DEFAULT_SIZE_MM,
    ) -> list[Segment]:
        segments: list[Segment] = []
        for corner, sx, sy in _frame_corners(cuts, margin_mm, size_mm):
            segments.append(
                Segment(corner, Point2D(corner.x + sx * size_mm, corner.y))
            )
            segments.append(
                Segment(corner, Point2D(corner.x, corner.y + sy * size_mm))
            )
        return segments
