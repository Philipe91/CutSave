"""Importador de PDF -> PolygonWithHoles (Fase 3B).

Le a PAGINA 0 com pypdfium2 (mesmo motor do preview) e entrega o contrato do
IVectorImporter: formas fechadas com furos, em mm, origem topo-esquerda e Y
crescendo para baixo.

Convencoes e limites:
- Cada FPDF_SEGMENT_MOVETO inicia um ANEL NOVO — diferente do
  PdfiumVectorExtractor (faca/arte), que funde os subpaths de um objeto num
  anel so. Para o nesting isso e essencial: o furo do "O" e um subpath e
  precisa virar anel proprio; a contencao (group_rings) decide quem e furo.
- Coordenadas: matriz do objeto aplicada ANTES do flip de Y (page_h - ty),
  depois pt -> mm com 25.4/72. Rotacao de pagina assumida 0 (mesma limitacao
  do extractor).
- Curvas (sempre Bezier cubica em PDF) viram polilinha por subdivisao
  adaptativa com desvio maximo 'approximation' (mm) — helper compartilhado
  com o importador de SVG (3A).
- FPDF_PAGEOBJ_TEXT nao e path: ignorado em silencio (texto precisa vir
  convertido em curvas; texto digitado e a Fase 3C). Pagina so com texto
  retorna lista vazia, sem erro.
"""

from __future__ import annotations

import ctypes

import pypdfium2.raw as raw

from app.application.ports.vector_importer import IVectorImporter
from app.domain.geometry.polygon import Polygon
from app.domain.geometry.polygon_with_holes import PolygonWithHoles, group_rings
from app.infrastructure.importers._flatten import PointAt, flatten_curve, to_ring
from app.infrastructure.pdfium_boxes import PDFIUM_LOCK, open_pdf
from app.shared.errors import PdfImportError, VectorImportError

PT2MM = 25.4 / 72.0


def _cubic_at(p0, p1, p2, p3) -> PointAt:
    """Avaliador t -> (x, y) da Bezier cubica com controles ja transformados
    (transformacao afim comuta com a avaliacao da curva)."""

    def at(t: float) -> tuple[float, float]:
        mt = 1.0 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]
        return (x, y)

    return at


class PdfVectorImporter(IVectorImporter):
    """Le a pagina 0 de um PDF e devolve as formas fechadas com furos, em mm."""

    def __init__(self, approximation: float = 0.1) -> None:
        if approximation <= 0:
            raise VectorImportError("approximation deve ser positiva (mm).")
        self._approximation = approximation

    def load(self, path: str) -> list[PolygonWithHoles]:
        with PDFIUM_LOCK:  # pdfium não é thread-safe (worker + UI ao vivo)
            try:
                document = open_pdf(path)
            except PdfImportError as exc:
                raise VectorImportError(str(exc)) from exc
            try:
                page = document[0]
                _w, page_h = page.get_size()
                rings: list[Polygon] = []
                for obj in page.get_objects(max_depth=4):
                    if obj.type != raw.FPDF_PAGEOBJ_PATH:
                        continue  # texto/imagem: texto digitado e a 3C
                    rings.extend(self._object_rings(obj, page_h))
                return group_rings(rings)
            finally:
                document.close()

    # -- internas ---------------------------------------------------------------

    def _object_rings(self, obj, page_h: float) -> list[Polygon]:
        """Cada subpath (MOVETO ate o proximo MOVETO) do objeto vira um anel
        em mm. Fechamento fica implicito (Polygon fecha sozinho)."""
        m = raw.FS_MATRIX()
        raw.FPDFPageObj_GetMatrix(obj.raw, m)

        def xform(x: float, y: float) -> tuple[float, float]:
            # matriz do objeto e depois PDF (baixo-esq) -> tela (topo-esq)
            tx = m.a * x + m.c * y + m.e
            ty = m.b * x + m.d * y + m.f
            return tx, page_h - ty

        tol_pt = self._approximation / PT2MM
        subpaths: list[list[tuple[float, float]]] = []
        points: list[tuple[float, float]] = []
        pending_bezier: list[tuple[float, float]] = []
        for i in range(raw.FPDFPath_CountSegments(obj.raw)):
            seg = raw.FPDFPath_GetPathSegment(obj.raw, i)
            xc, yc = ctypes.c_float(), ctypes.c_float()
            raw.FPDFPathSegment_GetPoint(seg, xc, yc)
            pt = xform(xc.value, yc.value)
            seg_type = raw.FPDFPathSegment_GetType(seg)
            if seg_type == raw.FPDF_SEGMENT_MOVETO:
                if points:
                    subpaths.append(points)
                points = [pt]
                pending_bezier = []
            elif seg_type == raw.FPDF_SEGMENT_LINETO:
                points.append(pt)
            elif seg_type == raw.FPDF_SEGMENT_BEZIERTO:
                pending_bezier.append(pt)
                if len(pending_bezier) == 3:
                    if points:  # sem MOVETO previo o path e malformado: pula
                        flatten_curve(_cubic_at(points[-1], *pending_bezier), tol_pt, points)
                    pending_bezier = []
        if points:
            subpaths.append(points)
        return [ring for sp in subpaths if (ring := to_ring(sp, PT2MM)) is not None]
