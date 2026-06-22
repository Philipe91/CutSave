from __future__ import annotations

from collections.abc import Iterable, Sequence

from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError

Ring = Sequence[tuple[float, float]]


class VectorContourGenerator:
    """Gera a faca pelo contorno externo da uniao das geometrias vetoriais.

    - Une todos os aneis (corrige auto-intersecoes com buffer(0));
    - escolhe o maior componente conectado como "produto"
      (descarta crop marks e elementos fora da area principal);
    - retorna o anel externo (ignora furos/elementos internos) como CutContour.

    Usa Shapely. Coordenadas em milimetros.
    """

    def generate(self, rings: Iterable[Ring]) -> CutContour:
        polygons = []
        for ring in rings:
            points = list(ring)
            if len(points) < 3:
                continue
            polygon = ShapelyPolygon(points)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty or polygon.area <= 0:
                continue
            polygons.append(polygon)

        if not polygons:
            raise ValidationError("Nenhuma geometria vetorial utilizavel para gerar faca.")

        product = self._largest_polygon(unary_union(polygons))
        coords = list(product.exterior.coords)
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]
        return CutContour([Point2D(x, y) for x, y in coords])

    @staticmethod
    def _largest_polygon(geometry):
        candidates = getattr(geometry, "geoms", None)
        if candidates is not None:
            polygons = [g for g in candidates if g.geom_type == "Polygon" and g.area > 0]
        elif geometry.geom_type == "Polygon" and geometry.area > 0:
            polygons = [geometry]
        else:
            polygons = []
        if not polygons:
            raise ValidationError("Geometria resultante nao possui area utilizavel.")
        return max(polygons, key=lambda g: g.area)
