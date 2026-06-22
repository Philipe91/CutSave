from __future__ import annotations

from collections.abc import Sequence

from app.domain.model.artwork import Artwork
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.nesting.grid import GridPacker, NestingPiece
from app.shared.errors import ValidationError


class RunGridNestingUseCase:
    """Posiciona Artworks em uma chapa via grid packing.

    Footprint de cada peca: a faca (cut_contour) quando existir; senao o
    tamanho da arte.
    """

    def __init__(self, packer: GridPacker | None = None) -> None:
        self._packer = packer or GridPacker()

    def _pieces(self, artworks: Sequence[Artwork]) -> list[NestingPiece]:
        if not artworks:
            raise ValidationError("Nenhuma arte para nesting.")
        return [
            NestingPiece(art.id, art.cut_contour.size if art.has_cut else art.size)
            for art in artworks
        ]

    def execute(self, artworks: Sequence[Artwork], material: Material) -> Layout:
        return self._packer.pack(self._pieces(artworks), material)

    def execute_sheets(
        self,
        artworks: Sequence[Artwork],
        material: Material,
        sheet_length: float,
    ) -> list[Layout]:
        """Divide as pecas em varias chapas de altura sheet_length.

        sheet_length <= 0 -> uma unica chapa aberta.
        """
        return self._packer.pack_sheets(self._pieces(artworks), material, sheet_length)
