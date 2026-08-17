from __future__ import annotations

from dataclasses import dataclass

from app.domain.geometry import Point2D, Size
from app.domain.geometry.bezier import BezierSegment
from app.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class CutContour:
    """Contorno de corte fechado (anel de pontos em mm).

    O fechamento e implicito: o ultimo ponto conecta ao primeiro.

    'curves' guarda a Bezier ORIGINAL do arquivo, quando o contorno veio de um
    importador vetorial: os exportadores gravam a curva de verdade em vez de
    reconstruir uma por cima dos pontos. Vazio = contorno so de retas (ou
    contorno que passou por operacao que invalida a curva), e a saida usa
    'points', como antes.
    """

    points: tuple[Point2D, ...]
    curves: tuple[BezierSegment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "curves", tuple(self.curves))
        if len(self.points) < 3:
            raise ValidationError("CutContour requer ao menos 3 pontos.")

    @property
    def origin(self) -> Point2D:
        """Canto inferior-esquerdo do retangulo envolvente (min x, min y)."""
        return Point2D(min(p.x for p in self.points), min(p.y for p in self.points))

    @property
    def size(self) -> Size:
        """Dimensao do retangulo envolvente do contorno."""
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return Size(max(xs) - min(xs), max(ys) - min(ys))
