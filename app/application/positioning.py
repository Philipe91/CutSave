from __future__ import annotations

from collections.abc import Sequence

from app.application.footprint import artwork_footprint
from app.domain.cut.mimaki import MimakiMarkGenerator, MimakiMarks
from app.domain.cut.registration import RegistrationMark, RegistrationMarkGenerator
from app.domain.cut.shared import Segment, build_shared_grid
from app.domain.geometry import BoundingBox, Point2D
from app.domain.model.artwork import Artwork
from app.domain.model.cut_contour import CutContour
from app.domain.model.layout import Layout

# Espacamento horizontal entre chapas no DXF unico (mm).
SHEET_GAP_MM = 50.0

_REG_GENERATOR = RegistrationMarkGenerator()
_MIMAKI_GENERATOR = MimakiMarkGenerator()


def _contours_of(layout: Layout, by_id: dict[str, Artwork], dx: float) -> list[CutContour]:
    contours: list[CutContour] = []
    for item in layout.items:
        art = by_id.get(item.artwork_id)
        if art is None or not art.has_cut:
            continue
        faca = art.cut_contour
        footprint = artwork_footprint(art)
        # origem art-local (0,0) vai para item.position - footprint.min
        tx = item.position.x - footprint.min_x + dx
        ty = item.position.y - footprint.min_y
        contours.append(CutContour([p.translated(tx, ty) for p in faca.points]))
    return contours


def _faca_rects_of(layout: Layout, by_id: dict[str, Artwork], dx: float) -> list[BoundingBox]:
    """Retangulos envolventes das facas posicionadas na chapa (mm)."""
    rects: list[BoundingBox] = []
    for item in layout.items:
        art = by_id.get(item.artwork_id)
        if art is None or not art.has_cut:
            continue
        faca = art.cut_contour
        footprint = artwork_footprint(art)
        tx = item.position.x - footprint.min_x + dx
        ty = item.position.y - footprint.min_y
        ox = faca.origin.x + tx
        oy = faca.origin.y + ty
        rects.append(BoundingBox(ox, oy, ox + faca.size.width, oy + faca.size.height))
    return rects


def _union_bbox(rects: Sequence[BoundingBox]) -> BoundingBox | None:
    if not rects:
        return None
    return BoundingBox(
        min(r.min_x for r in rects),
        min(r.min_y for r in rects),
        max(r.max_x for r in rects),
        max(r.max_y for r in rects),
    )


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


def shared_cut_segments(layout: Layout, artworks: Sequence[Artwork]) -> list[Segment]:
    """Faca compartilhada (grade "fora a fora") de uma chapa."""
    by_id = {art.id: art for art in artworks}
    return build_shared_grid(_faca_rects_of(layout, by_id, dx=0.0))


def shared_cut_segments_sheets(
    sheets: Sequence[Layout],
    artworks: Sequence[Artwork],
    sheet_width: float,
    gap: float = SHEET_GAP_MM,
) -> list[Segment]:
    """Faca compartilhada de varias chapas, lado a lado."""
    by_id = {art.id: art for art in artworks}
    segments: list[Segment] = []
    for index, layout in enumerate(sheets):
        rects = _faca_rects_of(layout, by_id, dx=index * (sheet_width + gap))
        segments.extend(build_shared_grid(rects))
    return segments


def cuts_bounding_box(layout: Layout, artworks: Sequence[Artwork]) -> BoundingBox | None:
    """Bbox de todas as facas de uma chapa (None se nao houver faca)."""
    by_id = {art.id: art for art in artworks}
    return _union_bbox(_faca_rects_of(layout, by_id, dx=0.0))


def registration_marks(
    layout: Layout,
    artworks: Sequence[Artwork],
    *,
    margin_mm: float,
    diameter_mm: float,
) -> list[RegistrationMark]:
    """5 marcas de registro ao redor das facas de uma chapa (vazio se sem faca)."""
    bbox = cuts_bounding_box(layout, artworks)
    if bbox is None:
        return []
    return _REG_GENERATOR.generate(bbox, margin_mm=margin_mm, diameter_mm=diameter_mm)


def registration_marks_sheets(
    sheets: Sequence[Layout],
    artworks: Sequence[Artwork],
    sheet_width: float,
    *,
    margin_mm: float,
    diameter_mm: float,
    gap: float = SHEET_GAP_MM,
) -> list[RegistrationMark]:
    """Marcas de registro de varias chapas, lado a lado."""
    by_id = {art.id: art for art in artworks}
    marks: list[RegistrationMark] = []
    for index, layout in enumerate(sheets):
        rects = _faca_rects_of(layout, by_id, dx=index * (sheet_width + gap))
        bbox = _union_bbox(rects)
        if bbox is None:
            continue
        marks.extend(
            _REG_GENERATOR.generate(bbox, margin_mm=margin_mm, diameter_mm=diameter_mm)
        )
    return marks


def mimaki_marks(
    layout: Layout,
    artworks: Sequence[Artwork],
    *,
    distance_mm: float,
    mark_size_mm: float,
) -> MimakiMarks | None:
    """Quadro + marcas em L da Mimaki para uma chapa (None se sem faca)."""
    bbox = cuts_bounding_box(layout, artworks)
    if bbox is None:
        return None
    return _MIMAKI_GENERATOR.generate(
        bbox, distance_mm=distance_mm, mark_size_mm=mark_size_mm
    )


def mimaki_marks_sheets(
    sheets: Sequence[Layout],
    artworks: Sequence[Artwork],
    sheet_width: float,
    *,
    distance_mm: float,
    mark_size_mm: float,
    gap: float = SHEET_GAP_MM,
) -> list[MimakiMarks]:
    """Quadros + marcas em L de varias chapas, lado a lado."""
    by_id = {art.id: art for art in artworks}
    result: list[MimakiMarks] = []
    for index, layout in enumerate(sheets):
        rects = _faca_rects_of(layout, by_id, dx=index * (sheet_width + gap))
        bbox = _union_bbox(rects)
        if bbox is None:
            continue
        result.append(
            _MIMAKI_GENERATOR.generate(
                bbox, distance_mm=distance_mm, mark_size_mm=mark_size_mm
            )
        )
    return result


def mimaki_frame_contours(marks_list: Sequence[MimakiMarks]) -> list[CutContour]:
    """Retangulos dos quadros Mimaki como facas de corte (CutContour)."""
    contours: list[CutContour] = []
    for marks in marks_list:
        f = marks.frame
        contours.append(CutContour([
            Point2D(f.min_x, f.min_y), Point2D(f.max_x, f.min_y),
            Point2D(f.max_x, f.max_y), Point2D(f.min_x, f.max_y),
        ]))
    return contours
