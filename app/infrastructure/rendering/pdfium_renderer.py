from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from app.application.ports.page_renderer import IPageRenderer
from app.infrastructure.pdfium_boxes import PDFIUM_LOCK, clip_topleft_pt, open_pdf
from app.infrastructure.pdfium_knife import knife_free_page, knife_free_pdf
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
        self, path: str, page_index: int = 0, dpi: int = 96, box: str = "media",
        *, only_page: bool = False,
    ) -> bytes:
        def _para_png(pil) -> bytes:
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            return buf.getvalue()

        return self._render(path, page_index, dpi, box, only_page, _para_png)

    def render_raw(
        self, path: str, page_index: int = 0, dpi: int = 96, box: str = "media",
        *, only_page: bool = False,
    ) -> tuple[bytes, int, int]:
        """Mesma imagem do render_png, porem em RGBA cru: (bytes, larg, alt).

        O preview serializava PNG so para o Qt desserializar na linha seguinte.
        Medido em PDF de 60 paginas A3: 21s codificando + 4s decodificando de
        um congelamento de 29s, e 217 MB de bytes de PNG vivos ao mesmo tempo
        que os pixmaps. Quem so quer pixel na tela usa este caminho; o
        render_png continua para quem precisa do arquivo PNG de verdade
        (detector de contorno, dialogo de recorte, testes)."""
        def _para_rgba(pil):
            if pil.mode != "RGBA":
                pil = pil.convert("RGBA")
            return pil.tobytes("raw", "RGBA"), pil.width, pil.height

        return self._render(path, page_index, dpi, box, only_page, _para_rgba)

    def _render(
        self, path: str, page_index: int, dpi: int, box: str, only_page: bool, finish
    ):
        """Rasteriza a pagina e aplica `finish` AINDA com o documento aberto.

        `finish` roda dentro do try de proposito: to_pil() COMPARTILHA o buffer
        do pdfium, que morre no document.close(). Devolver a imagem para o
        chamador exigiria uma copia inteira so para nao ler memoria liberada —
        num PDF de 60 paginas A3 isso e meio giga de memcpy a toa."""
        if Path(path).suffix.lower() in _IMAGE_SUFFIXES:
            return finish(self._pil_image_file(path, dpi))
        # a linha MAGENTA e faca (instrução de corte), não arte: renderiza a
        # cópia limpa — preview/miniatura mostram o que de fato imprime.
        # only_page: limpa SO esta pagina (miniatura de PDF grande nao paga o
        # strip do documento inteiro — eram 4,3s de janela travada ao soltar
        # um PDF de 60 paginas so para desenhar um icone de 48px).
        if only_page:
            path, page_index = knife_free_page(path, page_index)
        else:
            path = knife_free_pdf(path)
        with PDFIUM_LOCK:  # pdfium não é thread-safe (worker + UI ao vivo)
            document = open_pdf(path)
            try:
                page = document[page_index]
                scale = dpi / 72.0
                bitmap = page.render(scale=scale)  # segura o bitmap vivo
                pil = bitmap.to_pil()
                clip = clip_topleft_pt(page, box)
                if clip is not None:
                    x0, y0, w, h = (v * scale for v in clip)
                    pil = pil.crop((
                        max(0, round(x0)), max(0, round(y0)),
                        min(pil.width, round(x0 + w)), min(pil.height, round(y0 + h)),
                    ))
                return finish(pil)
            finally:
                document.close()

    @staticmethod
    def _pil_image_file(path: str, dpi: int):
        try:
            pil = Image.open(path)
            pil.load()
        except Exception as exc:
            raise PdfImportError(f"Falha ao abrir imagem: {path}") from exc
        # JPEG de grafica costuma vir CMYK (e ha YCbCr/16-bit): PNG so aceita
        # RGB/RGBA/L/LA — sem converter, o preview EXPLODIA e a peca nunca
        # aparecia na chapa (bug do adesivo CMYK, 14/07).
        if pil.mode not in ("RGB", "RGBA", "L", "LA"):
            pil = pil.convert("RGBA" if "transparency" in pil.info else "RGB")
        scale = dpi / 72.0
        if abs(scale - 1.0) > 1e-9:
            pil = pil.resize(
                (max(1, round(pil.width * scale)), max(1, round(pil.height * scale))),
                Image.LANCZOS,
            )
        return pil
