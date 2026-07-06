from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.geometry import BoundingBox, Point2D

_EPS = 1e-6


@dataclass(frozen=True, slots=True)
class Segment:
    """Segmento de reta (mm), aberto. Usado na faca compartilhada (grade)."""

    start: Point2D
    end: Point2D


def _merge_intervals(
    intervals: list[tuple[float, float]], eps: float = _EPS
) -> list[tuple[float, float]]:
    """Une intervalos [a, b] sobrepostos/encostados, ordenados por inicio."""
    merged: list[tuple[float, float]] = []
    for a, b in sorted(intervals):
        if merged and a <= merged[-1][1] + eps:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def _gap_midpoints(covered: list[tuple[float, float]]) -> list[float]:
    """Ponto medio de cada vao entre faixas cobertas (separadores internos)."""
    return [(covered[i][1] + covered[i + 1][0]) / 2 for i in range(len(covered) - 1)]


# Fusao automatica: bordas a menos de isto (mm) sao consideradas COLADAS e
# viram uma linha so. Espacamento normal entre pecas (>= 0.5mm) nao funde.
FUSE_TOL_MM = 0.15


def _axis_rect(points: Sequence[Point2D], tol: float) -> BoundingBox | None:
    """BoundingBox se o contorno for um retangulo alinhado aos eixos; senao None."""
    pts = list(points)
    if (
        len(pts) >= 2
        and abs(pts[0].x - pts[-1].x) <= tol
        and abs(pts[0].y - pts[-1].y) <= tol
    ):
        pts = pts[:-1]  # fecho repetido
    if len(pts) != 4:
        return None
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        if abs(a.x - b.x) > tol and abs(a.y - b.y) > tol:
            return None  # aresta inclinada: nao e retangulo reto
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    if max(xs) - min(xs) <= tol or max(ys) - min(ys) <= tol:
        return None  # degenerado
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))


def _touches(a: BoundingBox, b: BoundingBox, tol: float) -> bool:
    """Retangulos com uma borda COLADA (coincidente) e sobreposicao real."""
    if abs(a.max_x - b.min_x) <= tol or abs(b.max_x - a.min_x) <= tol:
        if min(a.max_y, b.max_y) - max(a.min_y, b.min_y) > tol:
            return True
    if abs(a.max_y - b.min_y) <= tol or abs(b.max_y - a.min_y) <= tol:
        if min(a.max_x, b.max_x) - max(a.min_x, b.min_x) > tol:
            return True
    return False


def _fuse_axis(
    edges: list[tuple[float, float, float]], tol: float
) -> list[tuple[float, float, float]]:
    """Agrupa arestas (coord, i0, i1) com coord ~igual e une os intervalos."""
    out: list[tuple[float, float, float]] = []
    group: list[tuple[float, float, float]] = []

    def flush() -> None:
        if not group:
            return
        coord = sum(e[0] for e in group) / len(group)
        for a, b in _merge_intervals([(e[1], e[2]) for e in group], eps=tol):
            out.append((coord, a, b))
        group.clear()

    for edge in sorted(edges):
        if group and edge[0] - group[-1][0] > tol:
            flush()
        group.append(edge)
    flush()
    return out


def merge_touching_rect_cuts(
    contours: Sequence[Sequence[Point2D]], tol: float = FUSE_TOL_MM
) -> tuple[set[int], list[Segment]]:
    """Funde facas retangulares COLADAS numa grade de linhas continuas.

    Cortes rentes (espacamento 0) deixam bordas coincidentes: cortar cada
    quadrado separadamente passa a faca 2x na mesma linha e "costura" o
    material. Aqui, retangulos encostados viram linhas retas fora a fora
    (estilo grade); pecas com espacamento ou contornos nao-retangulares ficam
    intactos (corte individual).

    Recebe as facas POSICIONADAS (mm absolutos, listas de pontos) e devolve
    (indices consumidos, segmentos fundidos). Vazio = nada colado.
    """
    rects: dict[int, BoundingBox] = {}
    for i, pts in enumerate(contours):
        box = _axis_rect(pts, tol)
        if box is not None:
            rects[i] = box

    ids = list(rects)
    touching: set[int] = set()
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            i, j = ids[a], ids[b]
            if _touches(rects[i], rects[j], tol):
                touching.add(i)
                touching.add(j)
    if not touching:
        return set(), []

    verticals: list[tuple[float, float, float]] = []
    horizontals: list[tuple[float, float, float]] = []
    for i in touching:
        r = rects[i]
        verticals += [(r.min_x, r.min_y, r.max_y), (r.max_x, r.min_y, r.max_y)]
        horizontals += [(r.min_y, r.min_x, r.max_x), (r.max_y, r.min_x, r.max_x)]

    segments = [
        Segment(Point2D(x, a), Point2D(x, b)) for x, a, b in _fuse_axis(verticals, tol)
    ]
    segments += [
        Segment(Point2D(a, y), Point2D(b, y)) for y, a, b in _fuse_axis(horizontals, tol)
    ]
    return touching, segments


def build_shared_grid(rects: Sequence[BoundingBox]) -> list[Segment]:
    """Faca compartilhada: grade de linhas "fora a fora" sobre os retangulos.

    A partir das facas posicionadas numa chapa, projeta os retangulos nos eixos
    para descobrir as colunas/linhas; desenha uma linha por separacao (no meio do
    vao entre pecas vizinhas) atravessando todo o bloco, mais o contorno externo.

    Pecas isoladas degradam para o proprio contorno (4 linhas).
    """
    if not rects:
        return []

    min_x = min(r.min_x for r in rects)
    min_y = min(r.min_y for r in rects)
    max_x = max(r.max_x for r in rects)
    max_y = max(r.max_y for r in rects)

    x_cover = _merge_intervals([(r.min_x, r.max_x) for r in rects])
    y_cover = _merge_intervals([(r.min_y, r.max_y) for r in rects])

    xs = [min_x, *_gap_midpoints(x_cover), max_x]
    ys = [min_y, *_gap_midpoints(y_cover), max_y]

    segments: list[Segment] = []
    for x in xs:  # verticais (de fora a fora em y)
        segments.append(Segment(Point2D(x, min_y), Point2D(x, max_y)))
    for y in ys:  # horizontais (de fora a fora em x)
        segments.append(Segment(Point2D(min_x, y), Point2D(max_x, y)))
    return segments
