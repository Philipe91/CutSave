"""Importador de SVG -> PolygonWithHoles (Fase 3A).

Por que svgelements (MIT): ele APLICA os transforms (translate/scale/matrix)
e resolve unidades/viewBox, devolvendo coordenadas absolutas — parsers que
ignoram transform colocam as pecas no lugar errado.

Convencoes:
- svgelements entrega tudo em px CSS (96 por polegada, ja com viewBox e
  width/height fisicos resolvidos); aqui converte px -> mm.
- Eixo Y: SVG cresce Y para baixo com origem no topo-esquerda — a MESMA
  convencao do resto do sistema (ver PdfiumVectorExtractor), sem flip.
- Curvas (Bezier/arco) viram polilinha por subdivisao adaptativa com desvio
  maximo 'approximation' (mm): menos pontos = NFP mais rapido, sem achatar
  detalhe fino de fonte.
- Furos: arvore de contencao even-odd sobre TODOS os aneis fechados do
  arquivo (group_rings) — cobre tanto letra "O" num unico <path> com duas
  subcurvas quanto dois <circle> concentricos.
"""

from __future__ import annotations

import svgelements as se

from app.application.ports.vector_importer import IVectorImporter
from app.domain.geometry.polygon import Polygon
from app.domain.geometry.polygon_with_holes import PolygonWithHoles, group_rings
from app.infrastructure.importers._flatten import flatten_curve, to_ring
from app.shared.errors import VectorImportError

# px CSS (96/in) -> mm. svgelements usa DEFAULT_PPI = 96.
_PX2MM = 25.4 / 96.0


class SvgVectorImporter(IVectorImporter):
    """Le um SVG e devolve as formas fechadas com furos, em mm."""

    def __init__(self, approximation: float = 0.1) -> None:
        if approximation <= 0:
            raise VectorImportError("approximation deve ser positiva (mm).")
        self._approximation = approximation

    def load(self, path: str) -> list[PolygonWithHoles]:
        try:
            svg = se.SVG.parse(path, reify=True)
        except OSError as exc:
            raise VectorImportError(f"Nao foi possivel abrir o SVG: {exc}") from exc
        except Exception as exc:  # svgelements lanca ParseError/ValueError variados
            raise VectorImportError(f"SVG invalido ({path}): {exc}") from exc
        rings: list[Polygon] = []
        for element in svg.elements():
            if not isinstance(element, se.Shape):
                continue  # grupos, texto nao convertido, imagens etc.
            rings.extend(self._element_rings(element))
        return group_rings(rings)

    # -- internas ---------------------------------------------------------------

    def _element_rings(self, shape: se.Shape) -> list[Polygon]:
        """Cada subcurva fechada do elemento vira um anel (Polygon) em mm."""
        path = abs(se.Path(shape))  # abs() garante o transform aplicado
        rings: list[Polygon] = []
        for subpath in path.as_subpaths():
            pts_px = self._flatten_subpath(subpath)
            ring = to_ring(pts_px, _PX2MM)
            if ring is not None:
                rings.append(ring)
        return rings

    def _flatten_subpath(self, subpath) -> list[tuple[float, float]]:
        """Subcurva -> lista de pontos em px. Fechamento fica implicito
        (Polygon fecha sozinho); o Close so confirma o retorno ao inicio."""
        tol_px = self._approximation / _PX2MM
        points: list[tuple[float, float]] = []
        for seg in subpath:
            if isinstance(seg, (se.Move, se.Line, se.Close)):
                if seg.end is not None:
                    points.append((seg.end.x, seg.end.y))
            elif isinstance(seg, se.Curve):
                flatten_curve(self._point_at(seg), tol_px, points)
        return points

    @staticmethod
    def _point_at(seg):
        """Avaliador t -> (x, y) de um segmento curvo do svgelements."""

        def at(t: float) -> tuple[float, float]:
            p = seg.point(t)
            return (p.x, p.y)

        return at
