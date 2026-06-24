from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.geometry import Point2D, Size
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem


@dataclass(frozen=True, slots=True)
class NestingPiece:
    """Peca a posicionar: id da arte + footprint (mm) que ocupa na chapa."""

    artwork_id: str
    size: Size


class GridPacker:
    """Grid packing simples: linhas da esquerda para a direita, sem rotacao.

    Quebra de linha quando a proxima peca nao cabe na largura util do material.
    Usa material.margin (borda) e material.spacing (entre pecas).
    """

    def pack(self, pieces: Sequence[NestingPiece], material: Material) -> Layout:
        margin = material.margin
        spacing = material.spacing
        spacing_y = material.spacing_y
        usable = material.usable_width
        right_limit = margin + usable

        x = margin
        y = margin
        row_height = 0.0
        placed: list[PlacedItem] = []

        for piece in pieces:
            width = piece.size.width
            height = piece.size.height
            # Quebra de linha: nao cabe e a linha ja tem alguma peca.
            if x > margin and x + width > right_limit:
                y += row_height + spacing_y
                x = margin
                row_height = 0.0
            placed.append(PlacedItem(piece.artwork_id, Point2D(x, y)))
            x += width + spacing
            row_height = max(row_height, height)

        used_length = (y + row_height + margin) if placed else 0.0
        return Layout(material=material, items=placed, used_length=used_length)

    def pack_sheets(
        self,
        pieces: Sequence[NestingPiece],
        material: Material,
        sheet_length: float,
    ) -> list[Layout]:
        """Igual ao pack, mas quebra em varias chapas de altura fixa.

        sheet_length <= 0 -> chapa aberta (uma unica chapa, como pack()).
        Cada chapa retornada tem used_length = sheet_length (folha cheia).
        """
        if sheet_length <= 0:
            return [self.pack(pieces, material)]

        margin = material.margin
        spacing = material.spacing
        spacing_y = material.spacing_y
        right_limit = margin + material.usable_width

        sheets: list[Layout] = []
        current: list[PlacedItem] = []
        x = margin
        y = margin
        row_height = 0.0

        for piece in pieces:
            width = piece.size.width
            height = piece.size.height
            if x > margin and x + width > right_limit:  # nova linha
                y += row_height + spacing_y
                x = margin
                row_height = 0.0
            if current and y + height > sheet_length:  # nova chapa
                sheets.append(Layout(material, current, sheet_length))
                current = []
                x = margin
                y = margin
                row_height = 0.0
            current.append(PlacedItem(piece.artwork_id, Point2D(x, y)))
            x += width + spacing
            row_height = max(row_height, height)

        if current:
            sheets.append(Layout(material, current, sheet_length))
        return sheets
