from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.application.dto.print_placement import PrintPlacement, PrintSheet
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import Artwork
from app.domain.model.layout import Layout
from app.shared.errors import ValidationError


class ExportPrintPdfUseCase:
    """Gera um PDF de impressao com uma pagina por chapa do nesting.

    'sources' mapeia o id da arte para (caminho_pdf, indice_pagina). A arte e
    carimbada no tamanho real, centralizada na celula da faca (offset = margem).
    """

    def __init__(self, exporter: IPrintPdfExporter) -> None:
        self._exporter = exporter

    def execute(
        self,
        sheets: Sequence[Layout],
        artworks: Sequence[Artwork],
        sources: Mapping[str, tuple[str, int]],
        output_path: str,
    ) -> str:
        layouts = [layout for layout in sheets if layout.items]
        if not layouts:
            raise ValidationError("Nenhuma chapa com pecas para imprimir.")
        by_id = {art.id: art for art in artworks}

        print_sheets: list[PrintSheet] = []
        for layout in layouts:
            placements = []
            for item in layout.items:
                art = by_id.get(item.artwork_id)
                if art is None:
                    raise ValidationError(f"Arte ausente para id {item.artwork_id}.")
                source = sources.get(item.artwork_id)
                if source is None:
                    raise ValidationError(f"Origem ausente para id {item.artwork_id}.")
                footprint = art.cut_contour.size if art.has_cut else art.size
                inset_x = (footprint.width - art.size.width) / 2
                inset_y = (footprint.height - art.size.height) / 2
                position = Point2D(item.position.x + inset_x, item.position.y + inset_y)
                placements.append(PrintPlacement(source[0], source[1], position, art.size))
            sheet_size = Size(layout.material.width, layout.used_length)
            print_sheets.append(PrintSheet(tuple(placements), sheet_size))

        self._exporter.export(print_sheets, output_path)
        return output_path
