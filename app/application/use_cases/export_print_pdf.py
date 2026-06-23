from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.application.dto.print_placement import (
    PrintCircle,
    PrintLine,
    PrintPlacement,
    PrintSheet,
)
from app.application.footprint import artwork_footprint
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.application.positioning import mimaki_marks, registration_marks
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import Artwork
from app.domain.model.layout import Layout
from app.shared.errors import ValidationError


class ExportPrintPdfUseCase:
    """Gera um PDF de impressao com uma pagina por chapa do nesting.

    Tipos de registro ('reg_type'):
      - 'none'    : sem marcas.
      - 'circles' : 5 bolinhas ao redor (padding = margem + diametro).
      - 'mimaki'  : marcas em L nos cantos de um quadro (padding = distancia).
    A pagina ganha 'padding' para as marcas caberem; o conteudo e deslocado.
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
        reg_type: str = "none",
        reg_margin_mm: float = 15.0,
        reg_diameter_mm: float = 6.0,
        mimaki_distance_mm: float = 15.0,
        mimaki_size_mm: float = 15.0,
        mimaki_thickness_mm: float = 1.0,
        crop_mm: float = 0.0,
        rotate: int = 0,
        box: str = "media",
    ) -> str:
        layouts = [layout for layout in sheets if layout.items]
        if not layouts:
            raise ValidationError("Nenhuma chapa com pecas para imprimir.")
        by_id = {art.id: art for art in artworks}

        if reg_type == "circles":
            pad = reg_margin_mm + reg_diameter_mm
        elif reg_type == "mimaki":
            pad = mimaki_distance_mm + mimaki_thickness_mm
        else:
            pad = 0.0

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
                position = Point2D(
                    item.position.x - footprint.min_x + pad,
                    item.position.y - footprint.min_y + pad,
                )
                placements.append(
                    PrintPlacement(source[0], source[1], position, art.size, crop_mm, rotate, box)
                )

            circles, lines = self._marks(
                layout, artworks, reg_type, pad,
                reg_margin_mm, reg_diameter_mm,
                mimaki_distance_mm, mimaki_size_mm, mimaki_thickness_mm,
            )
            sheet_size = Size(layout.material.width + 2 * pad, layout.used_length + 2 * pad)
            print_sheets.append(PrintSheet(tuple(placements), sheet_size, circles, lines))

        self._exporter.export(print_sheets, output_path)
        return output_path

    @staticmethod
    def _marks(
        layout, artworks, reg_type, pad,
        reg_margin_mm, reg_diameter_mm,
        mimaki_distance_mm, mimaki_size_mm, mimaki_thickness_mm,
    ):
        circles: tuple[PrintCircle, ...] = ()
        lines: tuple[PrintLine, ...] = ()
        if reg_type == "circles":
            marks = registration_marks(
                layout, artworks, margin_mm=reg_margin_mm, diameter_mm=reg_diameter_mm
            )
            circles = tuple(
                PrintCircle(m.center.translated(pad, pad), m.diameter) for m in marks
            )
        elif reg_type == "mimaki":
            marks = mimaki_marks(
                layout, artworks,
                distance_mm=mimaki_distance_mm, mark_size_mm=mimaki_size_mm,
            )
            if marks is not None:
                lines = tuple(
                    PrintLine(
                        s.start.translated(pad, pad),
                        s.end.translated(pad, pad),
                        mimaki_thickness_mm,
                    )
                    for s in marks.segments
                )
        return circles, lines
