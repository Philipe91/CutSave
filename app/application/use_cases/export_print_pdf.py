from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.application.dto.print_placement import PrintCircle, PrintPlacement, PrintSheet
from app.application.footprint import artwork_footprint
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.application.positioning import registration_marks
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import Artwork
from app.domain.model.layout import Layout
from app.shared.errors import ValidationError


class ExportPrintPdfUseCase:
    """Gera um PDF de impressao com uma pagina por chapa do nesting.

    'sources' mapeia o id da arte para (caminho_pdf, indice_pagina). A arte e
    carimbada no tamanho real, centralizada na celula da faca (offset = margem).

    Com marcas de registro, a pagina ganha uma borda (padding) para acomodar os
    circulos: todo o conteudo e deslocado e a folha cresce nos dois eixos.
    """

    def __init__(self, exporter: IPrintPdfExporter) -> None:
        self._exporter = exporter

    def execute(
        self,
        sheets: Sequence[Layout],
        artworks: Sequence[Artwork],
        sources: Mapping[str, tuple[str, int]],
        output_path: str,
        *,
        reg_marks: bool = False,
        reg_margin_mm: float = 15.0,
        reg_diameter_mm: float = 6.0,
    ) -> str:
        layouts = [layout for layout in sheets if layout.items]
        if not layouts:
            raise ValidationError("Nenhuma chapa com pecas para imprimir.")
        by_id = {art.id: art for art in artworks}
        # Padding garante que as marcas (centro a reg_margin, raio diameter/2)
        # caibam na pagina com uma zona de respiro de diameter/2.
        pad = (reg_margin_mm + reg_diameter_mm) if reg_marks else 0.0

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
                footprint = artwork_footprint(art)
                # origem art-local (0,0) -> item.position - footprint.min (+ padding)
                position = Point2D(
                    item.position.x - footprint.min_x + pad,
                    item.position.y - footprint.min_y + pad,
                )
                placements.append(PrintPlacement(source[0], source[1], position, art.size))

            circles: tuple[PrintCircle, ...] = ()
            if reg_marks:
                marks = registration_marks(
                    layout, artworks, margin_mm=reg_margin_mm, diameter_mm=reg_diameter_mm
                )
                circles = tuple(
                    PrintCircle(m.center.translated(pad, pad), m.diameter) for m in marks
                )

            sheet_size = Size(
                layout.material.width + 2 * pad, layout.used_length + 2 * pad
            )
            print_sheets.append(PrintSheet(tuple(placements), sheet_size, circles))

        self._exporter.export(print_sheets, output_path)
        return output_path
