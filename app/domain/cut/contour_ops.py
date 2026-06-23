from __future__ import annotations

from shapely.geometry import Polygon as ShapelyPolygon

from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


def _largest_polygon(geometry):
    candidates = getattr(geometry, "geoms", None)
    if candidates is not None:
        polygons = [g for g in candidates if g.geom_type == "Polygon" and g.area > 0]
    elif geometry.geom_type == "Polygon" and geometry.area > 0:
        polygons = [geometry]
    else:
        polygons = []
    if not polygons:
        return None
    return max(polygons, key=lambda g: g.area)


def offset_contour(contour: CutContour, offset_mm: float) -> CutContour:
    """Aplica um offset (mm) ao contorno: positivo cresce, negativo encolhe.

    Usa o anel externo do resultado (ignora furos). Offset zero devolve o
    contorno original. Encolher demais (poligono vazio) levanta ValidationError.
    """
    if offset_mm == 0:
        return contour
    poly = ShapelyPolygon([(p.x, p.y) for p in contour.points])
    if not poly.is_valid:
        poly = poly.buffer(0)
    grown = poly.buffer(offset_mm, join_style=2)  # join_style=2 (mitre) mantem cantos
    product = _largest_polygon(grown)
    if product is None or product.is_empty:
        raise ValidationError("Offset interno maior que o contorno da imagem.")
    coords = list(product.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return CutContour([Point2D(x, y) for x, y in coords])
