from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.model.artwork import Artwork
from app.domain.model.cut_contour import CutContour


class ImageKind(Enum):
    """Classificacao de uma imagem quanto ao fundo, para a faca automatica."""

    IMAGE_ALPHA = "alpha"  # tem canal de transparencia (recorte pelo alpha)
    IMAGE_OPAQUE = "opaque"  # sem transparencia (recorte por area util / fundo branco)


@dataclass(frozen=True, slots=True)
class ImageArtwork(Artwork):
    """Arte raster (PNG/JPG/WEBP) com metadados da imagem e contorno detectado.

    - dpi: resolucao real usada para converter pixels em milimetros.
    - image_kind: alpha (transparencia) ou opaque (fundo solido/branco).
    - raw_contour: contorno externo detectado, em mm art-local, com offset zero.
      A faca final (cut_contour) e derivada dele aplicando os offsets na UI.
    """

    dpi: float = 96.0
    image_kind: ImageKind = ImageKind.IMAGE_OPAQUE
    raw_contour: CutContour | None = None
