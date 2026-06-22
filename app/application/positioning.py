from __future__ import annotations

from collections.abc import Sequence

from app.domain.model.artwork import Artwork
from app.domain.model.cut_contour import CutContour
from app.domain.model.layout import Layout

# Espacamento horizontal entre chapas no DXF unico (mm).
SHEET_GAP_MM = 50.0


def _contours_of(layout: Layout, by_id: dict[str, Artwork], dx: float) -> list[CutContour]:
    contours: list[CutContour] = []
    for item in layout.items:
        art = by_id.get(item.artwork_id)
        if art is None or not art.has_cut:
            continue
        faca = art.cut_contour
        tx = item.position.x - faca.origin.x + dx
        ty = item.position.y - faca.origin.y
        contours.append(CutContour([p.translated(tx, ty) for p in faca.points]))
    return contours


def positioned_cut_contours(layout: Layout, artworks: Sequence[Artwork]) -> list[CutContour]:
    """Posiciona a faca de cada peca de uma chapa conforme o nesting."""
    by_id = {art.id: art for art in artworks}
    return _contours_of(layout, by_id, dx=0.0)


def positioned_cut_contours_sheets(
    sheets: Sequence[Layout],
    artworks: Sequence[Artwork],
    sheet_width: float,
    gap: float = SHEET_GAP_MM,
) -> list[CutContour]:
    """Junta as facas de varias chapas num unico conjunto, lado a lado.

    Cada chapa e deslocada em x por indice * (largura + gap).
    """
    by_id = {art.id: art for art in artworks}
    contours: list[CutContour] = []
    for index, layout in enumerate(sheets):
        contours.extend(_contours_of(layout, by_id, dx=index * (sheet_width + gap)))
    return contours
