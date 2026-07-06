"""Curvas cubicas (Bezier) por cima da faca poligonal — saida SUAVE.

A faca nasce como polilinha (deteccao + simplificacao): em curvas grandes as
cordas retas ficam visiveis ("corte meio reto"). Aqui cada trecho vira uma
Bezier cubica com tangentes continuas — a curva passa EXATAMENTE pelos nos
(nao muda a contagem de nos da faca) e fica lisa entre eles.

Regras que preservam a intencao do corte:
- No com virada forte (> CORNER_DEG) e um CANTO de verdade: a ponta fica viva
  (cada lado segue a propria corda). Retangulos continuam retangulos exatos.
- Trecho entre dois cantos e RETA exata (controles sobre a corda).
- Viradas suaves ganham tangente media -> curva continua (estilo Corel).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.geometry import Point2D

# virada (graus) acima da qual o no e tratado como canto vivo
CORNER_DEG = 32.0
_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class BezierSegment:
    p0: Point2D
    c1: Point2D
    c2: Point2D
    p1: Point2D

    def is_line(self, tol: float = 1e-6) -> bool:
        """True se os controles estao sobre a corda (trecho reto exato)."""
        return (
            _dist_point_line(self.c1, self.p0, self.p1) <= tol
            and _dist_point_line(self.c2, self.p0, self.p1) <= tol
        )


def _dist_point_line(p: Point2D, a: Point2D, b: Point2D) -> float:
    vx, vy = b.x - a.x, b.y - a.y
    n = math.hypot(vx, vy)
    if n < _EPS:
        return math.hypot(p.x - a.x, p.y - a.y)
    return abs((p.x - a.x) * vy - (p.y - a.y) * vx) / n


def _unit(dx: float, dy: float) -> tuple[float, float]:
    n = math.hypot(dx, dy)
    return (0.0, 0.0) if n < _EPS else (dx / n, dy / n)


def _dedup(points: Sequence[Point2D]) -> list[Point2D]:
    out: list[Point2D] = []
    for p in points:
        if not out or abs(p.x - out[-1].x) > _EPS or abs(p.y - out[-1].y) > _EPS:
            out.append(p)
    if len(out) > 1 and abs(out[0].x - out[-1].x) <= _EPS and abs(out[0].y - out[-1].y) <= _EPS:
        out.pop()  # fecho repetido
    return out


def cubic_segments(
    points: Sequence[Point2D], corner_deg: float = CORNER_DEG
) -> list[BezierSegment]:
    """Converte o contorno FECHADO em trechos de Bezier cubica suaves.

    Devolve [] quando nao ha o que suavizar (menos de 3 pontos) — o chamador
    mantem a polilinha original.
    """
    pts = _dedup(points)
    n = len(pts)
    if n < 3:
        return []

    dirs = [
        _unit(pts[(i + 1) % n].x - pts[i].x, pts[(i + 1) % n].y - pts[i].y)
        for i in range(n)
    ]
    cos_corner = math.cos(math.radians(corner_deg))
    # tangente de chegada (tin) e de saida (tout) em cada no
    tin: list[tuple[float, float]] = [None] * n  # type: ignore[list-item]
    tout: list[tuple[float, float]] = [None] * n  # type: ignore[list-item]
    for i in range(n):
        a = dirs[(i - 1) % n]  # corda que CHEGA no no
        b = dirs[i]            # corda que SAI do no
        if a[0] * b[0] + a[1] * b[1] < cos_corner:
            tin[i], tout[i] = a, b  # canto vivo: cada lado segue a propria corda
        else:
            m = _unit(a[0] + b[0], a[1] + b[1])
            tin[i] = tout[i] = m if m != (0.0, 0.0) else b

    segments: list[BezierSegment] = []
    for i in range(n):
        j = (i + 1) % n
        a, b = pts[i], pts[j]
        d = math.hypot(b.x - a.x, b.y - a.y) / 3.0
        segments.append(BezierSegment(
            a,
            Point2D(a.x + tout[i][0] * d, a.y + tout[i][1] * d),
            Point2D(b.x - tin[j][0] * d, b.y - tin[j][1] * d),
            b,
        ))
    return segments


def has_curves(segments: Sequence[BezierSegment], tol: float = 1e-6) -> bool:
    """True se algum trecho e curvo de verdade (nao so retas)."""
    return any(not s.is_line(tol) for s in segments)


def flatten(segments: Sequence[BezierSegment], max_dev_mm: float = 0.05) -> list[Point2D]:
    """Amostra as Beziers numa polilinha com desvio maximo dado (p/ fallback)."""
    out: list[Point2D] = []
    for s in segments:
        # passos pela "achatura" do trecho: controle longe da corda = mais passos
        dev = max(
            _dist_point_line(s.c1, s.p0, s.p1), _dist_point_line(s.c2, s.p0, s.p1)
        )
        steps = max(1, math.ceil(math.sqrt(dev / max(max_dev_mm, 1e-4)) * 4))
        for k in range(steps):
            t = k / steps
            out.append(_bezier_point(s, t))
    return out


def _bezier_point(s: BezierSegment, t: float) -> Point2D:
    u = 1.0 - t
    x = (
        u * u * u * s.p0.x + 3 * u * u * t * s.c1.x
        + 3 * u * t * t * s.c2.x + t * t * t * s.p1.x
    )
    y = (
        u * u * u * s.p0.y + 3 * u * u * t * s.c1.y
        + 3 * u * t * t * s.c2.y + t * t * t * s.p1.y
    )
    return Point2D(x, y)
