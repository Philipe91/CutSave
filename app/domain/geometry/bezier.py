"""Bezier cubica como dado de primeira classe da geometria.

Mora em 'geometry' (a camada de baixo) porque 'Polygon' precisa carregar a
curva ORIGINAL do arquivo importado ao lado dos vertices achatados: o encaixe
usa os vertices, a exportacao usa a curva. Se este tipo ficasse em
'domain/cut', a camada de baixo dependeria da de cima.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.geometry.bounding_box import BoundingBox
from app.domain.geometry.point import Point2D
from app.shared.errors import ValidationError

_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class BezierSegment:
    """Trecho de Bezier cubica: dois extremos (p0, p1) e dois controles."""

    p0: Point2D
    c1: Point2D
    c2: Point2D
    p1: Point2D

    def is_line(self, tol: float = 1e-6) -> bool:
        """True se os controles estao sobre a corda (trecho reto exato).

        Serve para o exportador escrever LINHA em vez de curva: reta gravada
        como reta deixa o arquivo limpo e o corte previsivel.
        """
        return (
            _dist_point_line(self.c1, self.p0, self.p1) <= tol
            and _dist_point_line(self.c2, self.p0, self.p1) <= tol
        )

    def reversed(self) -> BezierSegment:
        """Mesmo trecho percorrido ao contrario.

        Inverter um anel exige inverter cada trecho TAMBEM por dentro: so
        virar a lista deixaria cada curva apontando para o lado errado.
        """
        return BezierSegment(self.p1, self.c2, self.c1, self.p0)

    def translated(self, dx: float, dy: float) -> BezierSegment:
        return BezierSegment(
            self.p0.translated(dx, dy),
            self.c1.translated(dx, dy),
            self.c2.translated(dx, dy),
            self.p1.translated(dx, dy),
        )

    def rotated(self, degrees: float, around: Point2D | None = None) -> BezierSegment:
        """Gira os quatro pontos. Giro e translacao NAO deformam Bezier — e por
        isso que a curva original sobrevive ao encaixe sem perder nada."""
        return BezierSegment(
            self.p0.rotated(degrees, around),
            self.c1.rotated(degrees, around),
            self.c2.rotated(degrees, around),
            self.p1.rotated(degrees, around),
        )

    def scaled(self, factor: float, around: Point2D | None = None) -> BezierSegment:
        """Escala uniforme tambem preserva a forma da curva."""
        return BezierSegment(
            self.p0.scaled(factor, around),
            self.c1.scaled(factor, around),
            self.c2.scaled(factor, around),
            self.p1.scaled(factor, around),
        )

    def point_at(self, t: float) -> Point2D:
        u = 1.0 - t
        x = (
            u * u * u * self.p0.x + 3 * u * u * t * self.c1.x
            + 3 * u * t * t * self.c2.x + t * t * t * self.p1.x
        )
        y = (
            u * u * u * self.p0.y + 3 * u * u * t * self.c1.y
            + 3 * u * t * t * self.c2.y + t * t * t * self.p1.y
        )
        return Point2D(x, y)

    def extrema_x(self) -> list[float]:
        """Valores de x nos extremos EXATOS do trecho (pontas + raizes de dx/dt)."""
        return self._extrema(self.p0.x, self.c1.x, self.c2.x, self.p1.x, axis_x=True)

    def extrema_y(self) -> list[float]:
        """Valores de y nos extremos EXATOS do trecho (pontas + raizes de dy/dt)."""
        return self._extrema(self.p0.y, self.c1.y, self.c2.y, self.p1.y, axis_x=False)

    def _extrema(
        self, a0: float, a1: float, a2: float, a3: float, *, axis_x: bool
    ) -> list[float]:
        """Pontas mais as raizes de a*t^2 + b*t + c = 0 dentro de (0, 1).

        A derivada de uma cubica e uma quadratica; resolver exato evita a casca
        de controle, que em curvatura alta superestima muito a caixa e faria a
        peca reservar espaco que ela nao ocupa.
        """
        values = [a0, a3]
        a = -a0 + 3 * a1 - 3 * a2 + a3
        b = 2 * (a0 - 2 * a1 + a2)
        c = a1 - a0
        for t in _quadratic_roots(a, b, c):
            if 0.0 < t < 1.0:
                p = self.point_at(t)
                values.append(p.x if axis_x else p.y)
        return values


def line_segment(a: Point2D, b: Point2D) -> BezierSegment:
    """Reta como Bezier: controles em 1/3 e 2/3 da corda.

    Assim um contorno com trechos retos e curvos vira UMA lista homogenea, e
    is_line() reconhece de volta quem era reto na hora de gravar.
    """
    return BezierSegment(
        a,
        Point2D(a.x + (b.x - a.x) / 3.0, a.y + (b.y - a.y) / 3.0),
        Point2D(b.x - (b.x - a.x) / 3.0, b.y - (b.y - a.y) / 3.0),
        b,
    )


def bezier_bounds(segments: Sequence[BezierSegment]) -> BoundingBox:
    """Caixa envolvente EXATA da curva (nao da casca de controle)."""
    xs: list[float] = []
    ys: list[float] = []
    for s in segments:
        xs.extend(s.extrema_x())
        ys.extend(s.extrema_y())
    if not xs:
        raise ValidationError("bezier_bounds requer ao menos um segmento.")
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))


def _quadratic_roots(a: float, b: float, c: float) -> list[float]:
    if abs(a) < _EPS:  # degenera em linear
        return [] if abs(b) < _EPS else [-c / b]
    disc = b * b - 4 * a * c
    if disc < 0:
        return []
    root = math.sqrt(disc)
    return [(-b + root) / (2 * a), (-b - root) / (2 * a)]


def _dist_point_line(p: Point2D, a: Point2D, b: Point2D) -> float:
    vx, vy = b.x - a.x, b.y - a.y
    n = math.hypot(vx, vy)
    if n < _EPS:
        return math.hypot(p.x - a.x, p.y - a.y)
    return abs((p.x - a.x) * vy - (p.y - a.y) * vx) / n
