from __future__ import annotations

from dataclasses import replace

from app.application.ports.vector_extractor import IVectorExtractor
from app.domain.cut.vector import VectorContourGenerator, select_cut_rings
from app.domain.model.artwork import Artwork


class GenerateVectorCutUseCase:
    """Gera a faca de contorno de uma Artwork a partir dos vetores do PDF.

    Extrai os aneis vetoriais (porta), separa a FACA da arte pela pintura
    (select_cut_rings: traço magenta > spot > sem preenchimento > tudo) e
    delega a uniao/extracao de contorno ao gerador de dominio. Retorna nova
    Artwork imutavel com cut_contour preenchida.
    """

    def __init__(
        self,
        extractor: IVectorExtractor,
        generator: VectorContourGenerator | None = None,
    ) -> None:
        self._extractor = extractor
        self._generator = generator or VectorContourGenerator()

    def execute(self, artwork: Artwork, path: str, page_index: int = 0) -> Artwork:
        infos = self._extractor.extract_rings_info(path, page_index)
        rings, _reason = select_cut_rings(infos)
        cut = self._generator.generate(rings)
        return replace(artwork, cut_contour=cut)
