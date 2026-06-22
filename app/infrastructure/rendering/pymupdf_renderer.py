from __future__ import annotations

import fitz

from app.application.ports.page_renderer import IPageRenderer
from app.shared.errors import PdfImportError


class PyMuPdfPageRenderer(IPageRenderer):
    """Rasteriza uma pagina de PDF para PNG (bytes) com PyMuPDF."""

    def render_png(self, path: str, page_index: int = 0, dpi: int = 96) -> bytes:
        try:
            document = fitz.open(path)
        except Exception as exc:  # erros do fitz nao sao tipados
            raise PdfImportError(f"Falha ao abrir PDF: {path}") from exc
        try:
            pixmap = document[page_index].get_pixmap(dpi=dpi)
            return pixmap.tobytes("png")
        finally:
            document.close()
