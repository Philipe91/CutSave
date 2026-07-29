from __future__ import annotations

from abc import ABC, abstractmethod


class IPageRenderer(ABC):
    """Porta de rasterizacao de uma pagina de PDF para PNG (preview)."""

    @abstractmethod
    def render_png(
        self, path: str, page_index: int = 0, dpi: int = 96, box: str = "media"
    ) -> bytes:
        raise NotImplementedError

    def render_raw(
        self, path: str, page_index: int = 0, dpi: int = 96, box: str = "media"
    ) -> tuple[bytes, int, int]:
        """Mesma imagem em RGBA cru: (bytes, largura, altura).

        NAO e abstrato de proposito: implementacao que so sabe PNG continua
        valida e cai neste padrao (decodifica o proprio PNG). Quem rasteriza
        de verdade sobrescreve e evita o par codificar/decodificar."""
        import io

        from PIL import Image

        pil = Image.open(io.BytesIO(self.render_png(path, page_index, dpi, box)))
        pil = pil.convert("RGBA")
        return pil.tobytes("raw", "RGBA"), pil.width, pil.height
