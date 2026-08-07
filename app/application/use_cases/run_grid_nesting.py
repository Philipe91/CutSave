from __future__ import annotations

from collections.abc import Sequence

from app.application.footprint import artwork_footprint
from app.domain.model.artwork import Artwork
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.nesting.grid import GridPacker, NestingPiece
from app.shared.errors import ValidationError

# Rotacao automatica no encaixe do MODO IMPRESSAO (07/08/2026). Mora aqui, e
# nao na janela, para ter UMA fonte da verdade: a janela e o medidor de
# aproveitamento (scripts/nesting_baseline.py) leem daqui, entao nao existe
# medir uma coisa e entregar outra.
#
# O motor sempre soube girar; ficou desligado por anos porque o preview, o PDF
# de impressao, a faca e o DXF ignoravam PlacedItem.rotation — com o giro
# ligado, a peca sairia desenhada SEM girar dentro do espaco reservado GIRADO
# (pecas sobrepostas na chapa, sem nada acusando). Os quatro passaram a honrar
# o giro via app/application/footprint.py.
#
# Ganho medido: +0,52 pp de aproveitamento na media dos oito casos, +3,66 pp
# em tiras compridas, e nenhum caso piorou. False aqui devolve o encaixe
# exatamente ao que era, sem versao nova.
GIRO_AUTOMATICO = True


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
        return [NestingPiece(art.id, artwork_footprint(art).size) for art in artworks]

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
