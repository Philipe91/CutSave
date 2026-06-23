from __future__ import annotations

from dataclasses import dataclass

from app.domain.geometry import BoundingBox, Point2D
from app.shared.errors import ValidationError

DEFAULT_MARGIN_MM = 15.0
DEFAULT_DIAMETER_MM = 6.0


@dataclass(frozen=True, slots=True)
class RegistrationMark:
    """Marca de registro circular (mm). 'center' e o centro; 'diameter' o Ø."""

    center: Point2D
    diameter: float

    @property
    def radius(self) -> float:
        return self.diameter / 2.0


class RegistrationMarkGenerator:
    """Gera 5 marcas de registro num quadro afastado da bbox dos cortes.

    Coordenadas da chapa (origem no topo-esquerdo, y cresce para baixo):
    3 marcas no topo (esquerda, meio, direita) e 2 no fundo (esquerda, direita).
    O padrao assimetrico permite a camera da maquina identificar a orientacao.
    """

    def generate(
        self,
        cuts: BoundingBox,
        *,
        margin_mm: float = DEFAULT_MARGIN_MM,
        diameter_mm: float = DEFAULT_DIAMETER_MM,
    ) -> list[RegistrationMark]:
        if margin_mm < 0:
            raise ValidationError("Afastamento das marcas nao pode ser negativo (mm).")
        if diameter_mm <= 0:
            raise ValidationError("Diametro das marcas deve ser positivo (mm).")

        frame = cuts.expanded(margin_mm)
        cx = (frame.min_x + frame.max_x) / 2
        top, bottom = frame.min_y, frame.max_y
        centers = (
            Point2D(frame.min_x, top),     # topo-esquerdo
            Point2D(cx, top),              # topo-meio
            Point2D(frame.max_x, top),     # topo-direito
            Point2D(frame.min_x, bottom),  # inferior-esquerdo
            Point2D(frame.max_x, bottom),  # inferior-direito
        )
        return [RegistrationMark(c, diameter_mm) for c in centers]
