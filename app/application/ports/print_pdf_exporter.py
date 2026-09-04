from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence

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
        progresso: Callable[[float, str], None] | None = None,
        color_space: str = "rgb",
        icc_path: str | None = None,
        quality: int = 95,
    ) -> list[str]:
        """Rasteriza as chapas em imagem (PNG/JPEG). Opcional na porta.

        'progresso' recebe (fracao 0..1, texto) na mesma thread da chamada.
        'color_space' e 'rgb' ou 'cmyk' (CMYK so em JPEG, convertido para
        'icc_path'); 'quality' vale para JPEG."""
        raise NotImplementedError
