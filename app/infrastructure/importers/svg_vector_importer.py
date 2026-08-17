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
  detalhe fino de fonte. A Bezier ORIGINAL tambem e guardada (Polygon.curves)
  para a exportacao gravar curva de verdade; arco (se.Arc) nao tem cubica
  exata e por isso o anel dele sai sem curvas, degradando para polilinha.
- Furos: arvore de contencao even-odd sobre TODOS os aneis fechados do
  arquivo (group_rings) — cobre tanto letra "O" num unico <path> com duas
  subcurvas quanto dois <circle> concentricos.
"""

from __future__ import annotations

import svgelements as se

from app.application.ports.vector_importer import IVectorImporter
from app.domain.geometry import Point2D
from app.domain.geometry.bezier import BezierSegment, line_segment
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
            pts_px, curves_px = self._flatten_subpath(subpath)
            ring = to_ring(pts_px, _PX2MM, curves_px)
            if ring is not None:
                rings.append(ring)
        return rings

    def _flatten_subpath(
        self, subpath
    ) -> tuple[list[tuple[float, float]], list[BezierSegment]]:
        """Subcurva -> (pontos em px, curvas originais em px).

        Fechamento fica implicito (Polygon fecha sozinho); o Close so confirma
        o retorno ao inicio. A lista de curvas sai VAZIA se aparecer qualquer
        segmento sem cubica exata (se.Arc): melhor degradar para polilinha do
        que gravar uma aproximacao que o operador nao pediu.
        """
        tol_px = self._approximation / _PX2MM
        points: list[tuple[float, float]] = []
        curves: list[BezierSegment] = []
        exato = True
        for seg in subpath:
            if isinstance(seg, se.Move):
                if seg.end is not None:
                    points.append((seg.end.x, seg.end.y))
            elif isinstance(seg, (se.Line, se.Close)):
                if seg.end is None:
                    continue
                if points:
                    curves.append(
                        line_segment(_pt(points[-1]), _pt((seg.end.x, seg.end.y)))
                    )
                points.append((seg.end.x, seg.end.y))
            elif isinstance(seg, se.CubicBezier):
                curves.append(
                    BezierSegment(
                        _pt((seg.start.x, seg.start.y)),
                        _pt((seg.control1.x, seg.control1.y)),
                        _pt((seg.control2.x, seg.control2.y)),
                        _pt((seg.end.x, seg.end.y)),
                    )
                )
                flatten_curve(self._point_at(seg), tol_px, points)
            elif isinstance(seg, se.QuadraticBezier):
                # quadratica -> cubica e EXATO: c1 = s + 2/3(c-s), c2 = e + 2/3(c-e)
                sx, sy = seg.start.x, seg.start.y
                qx, qy = seg.control.x, seg.control.y
                ex, ey = seg.end.x, seg.end.y
                curves.append(
                    BezierSegment(
                        _pt((sx, sy)),
                        _pt((sx + 2.0 / 3.0 * (qx - sx), sy + 2.0 / 3.0 * (qy - sy))),
                        _pt((ex + 2.0 / 3.0 * (qx - ex), ey + 2.0 / 3.0 * (qy - ey))),
                        _pt((ex, ey)),
                    )
                )
                flatten_curve(self._point_at(seg), tol_px, points)
            elif isinstance(seg, se.Curve):  # se.Arc e o caso restante
                exato = False
                flatten_curve(self._point_at(seg), tol_px, points)
        return points, (curves if exato else [])

    @staticmethod
    def _point_at(seg):
        """Avaliador t -> (x, y) de um segmento curvo do svgelements."""

        def at(t: float) -> tuple[float, float]:
            p = seg.point(t)
            return (p.x, p.y)

        return at


def _pt(xy: tuple[float, float]) -> Point2D:
    return Point2D(xy[0], xy[1])
