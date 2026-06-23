from __future__ import annotations

import fitz

from app.application.ports.page_renderer import IPageRenderer
from app.infrastructure.pdf_boxes import box_clip_rect
from app.shared.errors import PdfImportError


class PyMuPdfPageRenderer(IPageRenderer):
    """Rasteriza uma pagina de PDF para PNG (bytes) com PyMuPDF.

    'box' recorta a renderizacao na mesma caixa usada pela faca, para a
    imagem do preview enquadrar corretamente (Apara remove marcas/sangria).
    """

    def render_png(
        self, path: str, page_index: int = 0, dpi: int = 96, box: str = "media"
    ) -> bytes:
        try:
            document = fitz.open(path)
        except Exception as exc:  # erros do fitz nao sao tipados
            raise PdfImportError(f"Falha ao abrir PDF: {path}") from exc
        try:
            page = document[page_index]
            clip = box_clip_rect(document, page, box)
            pixmap = page.get_pixmap(dpi=dpi, clip=clip) if clip else page.get_pixmap(dpi=dpi)
            return pixmap.tobytes("png")
        finally:
            document.close()
