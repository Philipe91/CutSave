from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.application.dto.print_placement import PrintSheet


class IPrintPdfExporter(ABC):
    """Porta de exportacao do PDF de impressao (uma pagina por chapa)."""

    @abstractmethod
    def export(self, sheets: Sequence[PrintSheet], output_path: str) -> None:
        raise NotImplementedError

    def export_image(
        self,
        sheets: Sequence[PrintSheet],
        output_path: str,
        *,
        dpi: int = 150,
        image_format: str = "png",
    ) -> list[str]:
        """Rasteriza as chapas em imagem (PNG/JPEG). Opcional na porta."""
        raise NotImplementedError
