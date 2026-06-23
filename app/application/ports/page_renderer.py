from __future__ import annotations

from abc import ABC, abstractmethod


class IPageRenderer(ABC):
    """Porta de rasterizacao de uma pagina de PDF para PNG (preview)."""

    @abstractmethod
    def render_png(
        self, path: str, page_index: int = 0, dpi: int = 96, box: str = "media"
    ) -> bytes:
        raise NotImplementedError
