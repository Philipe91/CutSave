"""Achatamento de curvas compartilhado pelos importadores vetoriais (3A/3B).

Concentra as regras comuns do contrato IVectorImporter que nao podem divergir
entre formatos:
- subdivisao adaptativa por desvio da corda, com tolerancia na unidade nativa
  do arquivo (px no SVG, pt no PDF) — o chamador converte a tolerancia em mm;
- dedup de pontos consecutivos e fechamento explicito -> implicito;
- descarte de aneis degenerados (<3 pontos ou area ~0 em mm2).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from app.domain.geometry import Point2D
from app.domain.geometry.bezier import BezierSegment
from app.domain.geometry.polygon import Polygon

# Pontos consecutivos mais proximos que isso (mm) sao duplicatas de emenda.
DEDUP_EPS = 1e-6
# Folga (mm) da checagem de anel fechado da curva. Mais larga que DEDUP_EPS
# porque o pdfium devolve float de 32 bits e o arredondamento chega a alguns
# micrometros.
_RING_EPS = 1e-3
# Trava de profundidade da subdivisao adaptativa (2^16 segmentos por curva).
MAX_DEPTH = 16
# Areas menores que isso (mm2) sao residuo numerico, nao geometria real.
_AREA_EPS = 1e-4

# Avaliador parametrico de uma curva: t em [0, 1] -> ponto (x, y).
PointAt = Callable[[float], tuple[float, float]]


def flatten_curve(point_at: PointAt, tol: float, out: list[tuple[float, float]]) -> None:
    """Subdivisao adaptativa: divide enquanto o ponto medio desviar da corda
    mais que 'tol' (mesma unidade dos pontos). Comeca ja dividido ao meio —
    protege arcos simetricos onde o ponto medio cai em cima da corda.
    Anexa a 'out' os pontos SEM o inicio (t=0), que o chamador ja tem."""

    def deviation(p, a, b) -> float:
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        len2 = dx * dx + dy * dy
        if len2 <= 0:
            return ((p[0] - ax) ** 2 + (p[1] - ay) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / len2))
        qx, qy = ax + t * dx, ay + t * dy
        return ((p[0] - qx) ** 2 + (p[1] - qy) ** 2) ** 0.5

    def recurse(t0: float, p0, t1: float, p1, depth: int) -> None:
        tm = (t0 + t1) / 2
        pm = point_at(tm)
        if depth >= MAX_DEPTH or deviation(pm, p0, p1) <= tol:
            out.append(p1)
            return
        recurse(t0, p0, tm, pm, depth + 1)
        recurse(tm, pm, t1, p1, depth + 1)

    start, mid, end = point_at(0.0), point_at(0.5), point_at(1.0)
    recurse(0.0, start, 0.5, mid, 1)
    recurse(0.5, mid, 1.0, end, 1)


def to_ring(
    points: list[tuple[float, float]],
    scale: float,
    curves: Sequence[BezierSegment] = (),
) -> Polygon | None:
    """unidade do arquivo -> mm (fator 'scale'), remove duplicatas consecutivas
    e o ponto de fechamento; descarta aneis degenerados (<3 pontos ou area ~0).

    'curves' vem na unidade do arquivo e sai escalada para mm. Se a lista
    estiver vazia ou nao formar um anel fechado que comeca no primeiro vertice,
    o Polygon sai SEM curvas: a saida degrada para polilinha (o comportamento
    antigo), que e correto — o que nao pode e curva dessincronizada dos
    vertices.
    """
    pts: list[Point2D] = []
    for x_raw, y_raw in points:
        p = Point2D(x_raw * scale, y_raw * scale)
        if pts and abs(p.x - pts[-1].x) <= DEDUP_EPS and abs(p.y - pts[-1].y) <= DEDUP_EPS:
            continue
        pts.append(p)
    # ultimo ponto == primeiro: fechamento explicito vira implicito
    if len(pts) >= 2 and (
        abs(pts[-1].x - pts[0].x) <= DEDUP_EPS and abs(pts[-1].y - pts[0].y) <= DEDUP_EPS
    ):
        pts.pop()
    if len(pts) < 3:
        return None
    scaled = _scaled_curves(curves, scale)
    if not _closes(scaled, pts[0]):
        scaled = ()
    ring = Polygon(tuple(pts), scaled)
    return ring if ring.area > _AREA_EPS else None


def _scaled_curves(
    curves: Sequence[BezierSegment], scale: float
) -> tuple[BezierSegment, ...]:
    return tuple(
        BezierSegment(
            Point2D(s.p0.x * scale, s.p0.y * scale),
            Point2D(s.c1.x * scale, s.c1.y * scale),
            Point2D(s.c2.x * scale, s.c2.y * scale),
            Point2D(s.p1.x * scale, s.p1.y * scale),
        )
        for s in curves
    )


def _closes(curves: Sequence[BezierSegment], first: Point2D) -> bool:
    """A lista descreve um anel fechado que comeca no primeiro vertice?

    E a trava da regra de invalidacao: curva que nao fecha, ou que comeca em
    outro ponto que os vertices, e descartada em vez de virar corte errado.
    """
    if not curves:
        return False
    if (
        abs(curves[0].p0.x - first.x) > _RING_EPS
        or abs(curves[0].p0.y - first.y) > _RING_EPS
    ):
        return False
    for i in range(len(curves)):
        prox = curves[(i + 1) % len(curves)]
        if (
            abs(curves[i].p1.x - prox.p0.x) > _RING_EPS
            or abs(curves[i].p1.y - prox.p0.y) > _RING_EPS
        ):
            return False
    return True
