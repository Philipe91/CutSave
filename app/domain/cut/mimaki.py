from __future__ import annotations

from dataclasses import dataclass

from app.domain.cut.shared import Segment
from app.domain.geometry import BoundingBox, Point2D
from app.shared.errors import ValidationError

DEFAULT_DISTANCE_MM = 15.0
DEFAULT_MARK_SIZE_MM = 15.0
DEFAULT_THICKNESS_MM = 1.0


@dataclass(frozen=True, slots=True)
class MimakiMarks:
    """Registro Mimaki: um quadro retangular em volta de tudo + marcas em L.

    - frame: retangulo (mm) afastado dos cortes; vira faca de corte.
    - segments: as marcas em L nos 4 cantos (2 segmentos por canto), impressas.
    """

    frame: BoundingBox
    segments: tuple[Segment, ...]


class MimakiMarkGenerator:
    """Gera o quadro + 4 marcas em L (uma por canto) sobre as linhas do quadro."""

    def generate(
        self,
        cuts: BoundingBox,
        *,
        distance_mm: float = DEFAULT_DISTANCE_MM,
        mark_size_mm: float = DEFAULT_MARK_SIZE_MM,
    ) -> MimakiMarks:
        if distance_mm < 0:
            raise ValidationError("Distancia do quadro nao pode ser negativa (mm).")
        if mark_size_mm <= 0:
            raise ValidationError("Tamanho da marca deve ser positivo (mm).")

        frame = cuts.expanded(distance_mm)
        x0, y0, x1, y1 = frame.min_x, frame.min_y, frame.max_x, frame.max_y
        m = mark_size_mm

        segments = (
            # canto superior-esquerdo
            Segment(Point2D(x0, y0), Point2D(x0 + m, y0)),
            Segment(Point2D(x0, y0), Point2D(x0, y0 + m)),
            # canto superior-direito
            Segment(Point2D(x1, y0), Point2D(x1 - m, y0)),
            Segment(Point2D(x1, y0), Point2D(x1, y0 + m)),
            # canto inferior-esquerdo
            Segment(Point2D(x0, y1), Point2D(x0 + m, y1)),
            Segment(Point2D(x0, y1), Point2D(x0, y1 - m)),
            # canto inferior-direito
            Segment(Point2D(x1, y1), Point2D(x1 - m, y1)),
            Segment(Point2D(x1, y1), Point2D(x1, y1 - m)),
        )
        return MimakiMarks(frame=frame, segments=segments)

    def frame_contour(self, marks: MimakiMarks):
        """Retangulo do quadro como CutContour (faca de corte)."""
        from app.domain.model.cut_contour import CutContour

        f = marks.frame
        return CutContour([
            Point2D(f.min_x, f.min_y), Point2D(f.max_x, f.min_y),
            Point2D(f.max_x, f.max_y), Point2D(f.min_x, f.max_y),
        ])
