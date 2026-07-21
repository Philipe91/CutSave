"""Forma fechada com furos (letra "O", "A", "8"): um contorno externo + zero ou
mais contornos internos. E o tipo que os importadores vetoriais (Fase 3)
entregam e que a exportacao (Fase 4) consome — a maquina corta o furo tambem.

Convencao de coordenadas: mm, origem topo-esquerda, Y cresce para BAIXO (a
mesma do resto do sistema — ver PdfiumVectorExtractor).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.geometry.bounding_box import BoundingBox
from app.domain.geometry.polygon import Polygon

# Areas menores que isso (mm2) sao residuo numerico, nao geometria real.
_AREA_EPS = 1e-4
# Folga (mm) nos testes de bounding box da arvore de contencao.
_EPS = 1e-6


def _ccw(polygon: Polygon) -> Polygon:
    """Anel com area assinada POSITIVA (anti-horario no sentido do shoelace)."""
    return Polygon(tuple(reversed(polygon.vertices))) if polygon.is_clockwise else polygon


def _cw(polygon: Polygon) -> Polygon:
    """Anel com area assinada NEGATIVA (horario no sentido do shoelace)."""
    return polygon if polygon.is_clockwise else Polygon(tuple(reversed(polygon.vertices)))


@dataclass(frozen=True, slots=True)
class PolygonWithHoles:
    """Contorno externo + furos, com orientacao canonica.

    Canonico: outer com area assinada positiva (anti-horario), furos com area
    assinada negativa (horario) — normalizado na construcao, o chamador pode
    passar aneis em qualquer orientacao.
    """

    outer: Polygon                       # contorno externo (anel unico)
    holes: tuple[Polygon, ...] = ()      # furos (vazio = sem furo)

    def __post_init__(self) -> None:
        object.__setattr__(self, "outer", _ccw(self.outer))
        object.__setattr__(self, "holes", tuple(_cw(h) for h in self.holes))

    @property
    def bounding_box(self) -> BoundingBox:
        return self.outer.bounding_box

    @property
    def area_liquida(self) -> float:
        """Area do material de verdade: outer menos os furos."""
        return self.outer.area - sum(h.area for h in self.holes)


def _ring_contains(outer: Polygon, inner: Polygon) -> bool:
    """True se 'inner' esta dentro de 'outer' (bbox primeiro, depois um ponto
    representativo por ray casting). Assume aneis que nao se cruzam — e o caso
    de arquivos vetoriais bem formados; borda coincidente nao e garantida."""
    a, b = outer.bounding_box, inner.bounding_box
    if (
        b.min_x < a.min_x - _EPS
        or b.min_y < a.min_y - _EPS
        or b.max_x > a.max_x + _EPS
        or b.max_y > a.max_y + _EPS
    ):
        return False
    return outer.contains(inner.vertices[0])


def group_rings(rings: Iterable[Polygon]) -> list[PolygonWithHoles]:
    """Arvore de contencao -> formas com furos (regra even-odd da Fase 3).

    Profundidade de um anel = quantos outros aneis o contem. Profundidade PAR
    = corpo (outer); IMPAR = furo do corpo que o contem diretamente (o menor
    anel contentor). Ilha dentro de furo (profundidade 2) vira um novo outer
    separado — a regra even-odd resolve sozinha.

    Aneis degenerados (area ~0) sao descartados. O(n^2) em aneis: ok para
    arquivos de corte reais (dezenas/centenas de aneis).
    """
    valid = [r for r in rings if r.area > _AREA_EPS]
    n = len(valid)
    parents: list[list[int]] = [
        [j for j in range(n) if j != i and _ring_contains(valid[j], valid[i])]
        for i in range(n)
    ]
    depths = [len(p) for p in parents]

    shapes: dict[int, list[Polygon]] = {i: [] for i in range(n) if depths[i] % 2 == 0}
    for i in range(n):
        if depths[i] % 2 == 0:
            continue
        # pai direto do furo = o MENOR anel que o contem (sempre um corpo:
        # profundidade do pai direto = depths[i] - 1, que e par).
        parent = min(parents[i], key=lambda j: valid[j].area)
        shapes[parent].append(valid[i])
    return [PolygonWithHoles(valid[i], tuple(holes)) for i, holes in shapes.items()]
