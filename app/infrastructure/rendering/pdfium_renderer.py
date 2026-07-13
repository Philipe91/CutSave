from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from app.application.ports.page_renderer import IPageRenderer
from app.infrastructure.pdfium_boxes import clip_topleft_pt, open_pdf
from app.shared.errors import PdfImportError

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class PdfiumPageRenderer(IPageRenderer):
    """Rasteriza uma pagina de PDF para PNG (bytes) com pypdfium2.

    'box' recorta a renderizacao na mesma caixa usada pela faca, para a
    imagem do preview enquadrar corretamente (Apara remove marcas/sangria).

    Arquivos de IMAGEM tambem passam por aqui (dialogo de recorte usa o
    mesmo caminho): saem re-escalados por dpi/72, como o motor antigo fazia
    (1 px tratado como 1 pt).
    """

    def render_png(
        self, path: str, page_index: int = 0, dpi: int = 96, box: str = "media"
    ) -> bytes:
        if Path(path).suffix.lower() in _IMAGE_SUFFIXES:
            return self._render_image_file(path, dpi)
        document = open_pdf(path)
        try:
            page = document[page_index]
            scale = dpi / 72.0
            pil = page.render(scale=scale).to_pil()
            clip = clip_topleft_pt(page, box)
            if clip is not None:
                x0, y0, w, h = (v * scale for v in clip)
                pil = pil.crop((
                    max(0, round(x0)), max(0, round(y0)),
                    min(pil.width, round(x0 + w)), min(pil.height, round(y0 + h)),
                ))
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            return buf.getvalue()
        finally:
            document.close()

    @staticmethod
    def _render_image_file(path: str, dpi: int) -> bytes:
        try:
            pil = Image.open(path)
            pil.load()
        except Exception as exc:
            raise PdfImportError(f"Falha ao abrir imagem: {path}") from exc
        scale = dpi / 72.0
        if abs(scale - 1.0) > 1e-9:
            pil = pil.resize(
                (max(1, round(pil.width * scale)), max(1, round(pil.height * scale))),
                Image.LANCZOS,
            )
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return buf.getvalue()
