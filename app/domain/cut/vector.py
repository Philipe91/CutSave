from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError

Ring = Sequence[tuple[float, float]]


@dataclass(frozen=True)
class RingInfo:
    """Anel vetorial + como ele foi pintado no PDF (para achar a FACA).

    Convenção de gráfica: a linha de corte vem como TRAÇO (stroke) em magenta
    100% ou numa cor spot tipo "CutContour", sem preenchimento — a arte, ao
    contrário, é quase toda preenchida. Essas pistas separam faca de arte.
    """

    ring: Ring
    stroked: bool = False
    filled: bool = False
    stroke_rgb: tuple[int, int, int] | None = None  # None = cor não resolvida (spot)


def is_knife_color(rgb: tuple[int, int, int]) -> bool:
    """Magenta/rosa-choque, a cor universal de faca nas gráficas.

    Cobre o magenta puro (255,0,255) e o alternate típico da spot CutContour
    do Corel/Illustrator (~236,0,140), sem pegar vermelho nem azul puros."""
    r, g, b = rgb
    return r >= 180 and g <= 100 and b >= 100


def select_cut_rings(infos: Iterable[RingInfo]) -> tuple[list[Ring], str]:
    """Escolhe quais anéis do PDF são a FACA do cliente, por prioridade:

    1. "magenta"  — traço em magenta/rosa (convenção de corte);
    2. "spot"     — traço cuja cor o PDF não resolveu (tipicamente spot
                    CutContour em colorspace exótico);
    3. "stroke"   — traço sem preenchimento (linha, não arte);
    4. "all"      — tudo (comportamento antigo: união geral dos vetores).

    Retorna (anéis, motivo) — o motivo alimenta o aviso na interface.
    """
    infos = list(infos)
    tiers: list[tuple[str, list[RingInfo]]] = [
        ("magenta", [i for i in infos
                     if i.stroked and i.stroke_rgb is not None
                     and is_knife_color(i.stroke_rgb)]),
        ("spot", [i for i in infos if i.stroked and i.stroke_rgb is None]),
        ("stroke", [i for i in infos if i.stroked and not i.filled]),
        ("all", infos),
    ]
    for reason, tier in tiers:
        if tier:
            return [i.ring for i in tier], reason
    return [], "all"


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
