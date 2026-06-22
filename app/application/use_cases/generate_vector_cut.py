from __future__ import annotations

from dataclasses import replace

from app.application.ports.vector_extractor import IVectorExtractor
from app.domain.cut.vector import VectorContourGenerator
from app.domain.model.artwork import Artwork


class GenerateVectorCutUseCase:
    """Gera a faca de contorno de uma Artwork a partir dos vetores do PDF.

    Extrai os aneis vetoriais (porta) e delega a uniao/extracao de contorno ao
    gerador de dominio. Retorna nova Artwork imutavel com cut_contour preenchida.
    """

    def __init__(
        self,
        extractor: IVectorExtractor,
        generator: VectorContourGenerator | None = None,
    ) -> None:
        self._extractor = extractor
        self._generator = generator or VectorContourGenerator()

    def execute(self, artwork: Artwork, path: str, page_index: int = 0) -> Artwork:
        rings = self._extractor.extract_rings(path, page_index)
        cut = self._generator.generate(rings)
        return replace(artwork, cut_contour=cut)
