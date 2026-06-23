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


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Une intervalos [a, b] sobrepostos/encostados, ordenados por inicio."""
    merged: list[tuple[float, float]] = []
    for a, b in sorted(intervals):
        if merged and a <= merged[-1][1] + _EPS:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def _gap_midpoints(covered: list[tuple[float, float]]) -> list[float]:
    """Ponto medio de cada vao entre faixas cobertas (separadores internos)."""
    return [(covered[i][1] + covered[i + 1][0]) / 2 for i in range(len(covered) - 1)]


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
