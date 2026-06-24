"""Calculo de medidas para o painel contextual e a barra de status.

Logica PURA (sem Qt): recebe objetos de dominio e devolve numeros prontos para
exibir. Reaproveita o que o dominio ja oferece (Polygon.area/perimeter,
Size.area, artwork_footprint, Layout.used_length).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.footprint import artwork_footprint
from app.domain.geometry import Polygon
from app.domain.model.artwork import Artwork
from app.domain.model.layout import Layout
from app.domain.model.placement import PlacedItem


@dataclass(frozen=True)
class PieceMetrics:
    width: float       # mm
    height: float      # mm
    area: float        # mm2 (do contorno da faca, ou retangulo da arte)
    perimeter: float   # mm


@dataclass(frozen=True)
class GroupMetrics:
    width: float       # mm (caixa que envolve o grupo)
    height: float      # mm
    count: int


@dataclass(frozen=True)
class SheetMetrics:
    width: float       # mm
    length: float      # mm (comprimento consumido)
    sheet_area: float  # mm2
    used_area: float   # mm2 ocupada pelas pecas
    used_pct: float    # 0-100
    free_area: float   # mm2


def piece_metrics(art: Artwork) -> PieceMetrics:
    """Medidas de uma peca: usa o contorno da faca quando houver, senao a arte."""
    if art.has_cut:
        contour = art.cut_contour
        poly = Polygon(contour.points)
        size = contour.size
        return PieceMetrics(size.width, size.height, poly.area, poly.perimeter)
    w, h = art.size.width, art.size.height
    return PieceMetrics(w, h, w * h, 2 * (w + h))


def group_metrics(boxes: Sequence[tuple[float, float, float, float]]) -> GroupMetrics:
    """Medidas de um grupo a partir de caixas (x, y, w, h) em mm de cada peca."""
    if not boxes:
        return GroupMetrics(0.0, 0.0, 0)
    min_x = min(x for x, _y, _w, _h in boxes)
    min_y = min(y for _x, y, _w, _h in boxes)
    max_x = max(x + w for x, _y, w, _h in boxes)
    max_y = max(y + h for _x, y, _w, h in boxes)
    return GroupMetrics(max_x - min_x, max_y - min_y, len(boxes))


def sheet_metrics(layout: Layout, artworks: Sequence[Artwork]) -> SheetMetrics:
    """Medidas de uma chapa: tamanho, area ocupada pelas pecas e % de uso."""
    by_id = {a.id: a for a in artworks}
    width = layout.material.width
    length = layout.used_length
    sheet_area = width * length
    used = 0.0
    for item in layout.items:
        art = by_id.get(_item_id(item))
        if art is not None:
            used += artwork_footprint(art).area
    pct = (used / sheet_area * 100.0) if sheet_area > 0 else 0.0
    return SheetMetrics(width, length, sheet_area, used, pct, max(0.0, sheet_area - used))


def _item_id(item: PlacedItem) -> str:
    return item.artwork_id
