from __future__ import annotations

import ctypes

import pypdfium2.raw as raw

from app.application.ports.vector_extractor import IVectorExtractor
from app.infrastructure.pdfium_boxes import open_pdf

PT2MM = 25.4 / 72.0


class PdfiumVectorExtractor(IVectorExtractor):
    """Extrai aneis vetoriais de uma pagina com pypdfium2, em milimetros.

    Mesmo contrato do extrator PyMuPDF: lados retos e retangulos viram pontos
    diretos; curvas de Bezier sao amostradas em segmentos; coordenadas saem
    com origem no TOPO-esquerda (convencao do resto do sistema). Nao trata
    rotacao de pagina (assume 0).
    """

    def __init__(self, bezier_steps: int = 8) -> None:
        self._steps = bezier_steps

    def extract_rings(self, path: str, page_index: int = 0) -> list[list[tuple[float, float]]]:
        document = open_pdf(path)
        try:
            page = document[page_index]
            _w, page_h = page.get_size()
            rings = []
            for obj in page.get_objects(max_depth=4):
                if obj.type != raw.FPDF_PAGEOBJ_PATH:
                    continue
                ring = self._path_to_ring(obj, page_h)
                if len(ring) >= 3:
                    rings.append(ring)
            return rings
        finally:
            document.close()

    def _path_to_ring(self, obj, page_h: float) -> list[tuple[float, float]]:
        """Um anel por objeto de path (como o get_drawings do fitz): move so
        desloca o cursor; linha grava os DOIS extremos; Bezier grava o inicio
        e a curva amostrada — pontos duplicados nao atrapalham o motor."""
        m = raw.FS_MATRIX()
        raw.FPDFPageObj_GetMatrix(obj.raw, m)

        def xform(x: float, y: float) -> tuple[float, float]:
            # matriz do objeto e depois PDF (baixo-esq) -> tela (topo-esq)
            tx = m.a * x + m.c * y + m.e
            ty = m.b * x + m.d * y + m.f
            return tx, page_h - ty

        n = raw.FPDFPath_CountSegments(obj.raw)
        points: list[tuple[float, float]] = []
        current: tuple[float, float] | None = None
        pending_bezier: list[tuple[float, float]] = []
        for i in range(n):
            seg = raw.FPDFPath_GetPathSegment(obj.raw, i)
            xc, yc = ctypes.c_float(), ctypes.c_float()
            raw.FPDFPathSegment_GetPoint(seg, xc, yc)
            pt = xform(xc.value, yc.value)
            seg_type = raw.FPDFPathSegment_GetType(seg)
            if seg_type == raw.FPDF_SEGMENT_MOVETO:
                current = pt
                pending_bezier = []
            elif seg_type == raw.FPDF_SEGMENT_LINETO:
                if current is not None:
                    points.append(current)
                points.append(pt)
                current = pt
            elif seg_type == raw.FPDF_SEGMENT_BEZIERTO:
                pending_bezier.append(pt)
                if len(pending_bezier) == 3 and current is not None:
                    points.append(current)
                    points.extend(
                        self._sample_bezier(current, *pending_bezier)
                    )
                    current = pending_bezier[2]
                    pending_bezier = []
        return [(x * PT2MM, y * PT2MM) for x, y in points]

    def _sample_bezier(self, p0, p1, p2, p3) -> list[tuple[float, float]]:
        out = []
        for i in range(1, self._steps + 1):
            t = i / self._steps
            mt = 1 - t
            x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0]
            y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]
            out.append((x, y))
        return out
