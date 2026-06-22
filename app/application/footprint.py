from __future__ import annotations

from app.domain.geometry import BoundingBox
from app.domain.model.artwork import Artwork


def artwork_footprint(art: Artwork) -> BoundingBox:
    """Area que a peca ocupa na chapa (art-local): uniao da arte com a faca.

    Garante footprint correto mesmo quando a faca e menor que a arte (recuo
    de seguranca): nesse caso vale a arte, evitando sobreposicao no nesting.
    """
    min_x, min_y = 0.0, 0.0
    max_x, max_y = art.size.width, art.size.height
    if art.has_cut:
        faca = art.cut_contour
        ox, oy = faca.origin.x, faca.origin.y
        min_x = min(min_x, ox)
        min_y = min(min_y, oy)
        max_x = max(max_x, ox + faca.size.width)
        max_y = max(max_y, oy + faca.size.height)
    return BoundingBox(min_x, min_y, max_x, max_y)
