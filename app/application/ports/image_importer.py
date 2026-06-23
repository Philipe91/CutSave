from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.model.image_artwork import ImageArtwork


@dataclass(frozen=True, slots=True)
class ImportedImage:
    """Resultado da importacao de uma imagem.

    - artwork: a ImageArtwork (tamanho real, classificacao, contorno detectado).
    - render_path: arquivo que o renderer/exportador deve usar (igual ao original
      para PNG/JPG; um PNG normalizado em cache para WEBP, que o fitz nao abre).
    """

    artwork: ImageArtwork
    render_path: str


class IImageImporter(ABC):
    """Porta de importacao de imagens raster (PNG/JPG/WEBP) com faca automatica."""

    @abstractmethod
    def import_image(
        self,
        path: str,
        *,
        sensitivity: float = 50.0,
        ignore_white: bool = True,
    ) -> ImportedImage:
        """Importa a imagem e detecta o contorno externo.

        sensitivity: 0-100; maior inclui pixels mais fracos (sombras, off-white).
        ignore_white: em imagens opacas, recorta a area util ignorando o fundo branco.
        """
        raise NotImplementedError
