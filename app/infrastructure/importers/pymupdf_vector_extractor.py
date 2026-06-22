from __future__ import annotations

import fitz

from app.application.ports.vector_extractor import IVectorExtractor
from app.shared.errors import PdfImportError

PT2MM = 25.4 / 72.0


class PyMuPdfVectorExtractor(IVectorExtractor):
    """Extrai aneis vetoriais de uma pagina com PyMuPDF, em milimetros.

    Lados retos e retangulos viram pontos diretos; curvas de Bezier sao
    amostradas em segmentos. Nao trata rotacao de pagina (assume 0).
    """

    def __init__(self, bezier_steps: int = 8) -> None:
        self._steps = bezier_steps

    def extract_rings(self, path: str, page_index: int = 0) -> list[list[tuple[float, float]]]:
        try:
            document = fitz.open(path)
        except Exception as exc:  # erros do fitz nao sao tipados
            raise PdfImportError(f"Falha ao abrir PDF: {path}") from exc
        try:
            if not document.is_pdf:
                raise PdfImportError(f"Arquivo nao e um PDF valido: {path}")
            page = document[page_index]
            rings = []
            for drawing in page.get_drawings():
                ring = self._drawing_to_ring(drawing)
                if len(ring) >= 3:
                    rings.append(ring)
            return rings
        finally:
            document.close()

    def _drawing_to_ring(self, drawing) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        for item in drawing["items"]:
            op = item[0]
            if op == "l":
                p1, p2 = item[1], item[2]
                points.append((p1.x, p1.y))
                points.append((p2.x, p2.y))
            elif op == "c":
                p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                points.append((p1.x, p1.y))
                points.extend(self._sample_bezier(p1, p2, p3, p4))
            elif op == "re":
                r = item[1]
                points.extend([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
        return [(x * PT2MM, y * PT2MM) for x, y in points]

    def _sample_bezier(self, p0, p1, p2, p3) -> list[tuple[float, float]]:
        out = []
        for i in range(1, self._steps + 1):
            t = i / self._steps
            mt = 1 - t
            x = mt**3 * p0.x + 3 * mt**2 * t * p1.x + 3 * mt * t * t * p2.x + t**3 * p3.x
            y = mt**3 * p0.y + 3 * mt**2 * t * p1.y + 3 * mt * t * t * p2.y + t**3 * p3.y
            out.append((x, y))
        return out
