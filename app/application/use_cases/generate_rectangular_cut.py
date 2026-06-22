from __future__ import annotations

from dataclasses import replace

from app.domain.cut.rectangular import RectangularCutGenerator
from app.domain.geometry import BoundingBox
from app.domain.model.artwork import Artwork


class GenerateRectangularCutUseCase:
    """Gera a faca retangular de uma Artwork e a armazena em cut_contour.

    A area do produto e o retangulo da propria arte (origem 0,0). Retorna uma
    nova Artwork imutavel com a faca preenchida.
    """

    def __init__(self, generator: RectangularCutGenerator | None = None) -> None:
        self._generator = generator or RectangularCutGenerator()

    def execute(self, artwork: Artwork, offset_mm: float = 0.0) -> Artwork:
        area = BoundingBox(0.0, 0.0, artwork.size.width, artwork.size.height)
        cut = self._generator.generate(area, offset_mm)
        return replace(artwork, cut_contour=cut)
