from __future__ import annotations

from collections.abc import Sequence

import fitz

from app.application.dto.print_placement import PrintSheet
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.shared.errors import PrintExportError

MM2PT = 72.0 / 25.4


class PyMuPdfPrintExporter(IPrintPdfExporter):
    """Gera o PDF de impressao (uma pagina por chapa), preservando vetores.

    Usa show_pdf_page, que embute cada pagina como Form XObject (sem rasterizar).
    """

    def export(self, sheets: Sequence[PrintSheet], output_path: str) -> None:
        out = fitz.open()
        sources: dict[str, fitz.Document] = {}
        try:
            for sheet in sheets:
                page = out.new_page(
                    width=sheet.size.width * MM2PT, height=sheet.size.height * MM2PT
                )
                for pl in sheet.placements:
                    src = sources.get(pl.source_path)
                    if src is None:
                        src = fitz.open(pl.source_path)
                        sources[pl.source_path] = src
                    rect = fitz.Rect(
                        pl.position.x * MM2PT,
                        pl.position.y * MM2PT,
                        (pl.position.x + pl.size.width) * MM2PT,
                        (pl.position.y + pl.size.height) * MM2PT,
                    )
                    clip = self._crop_clip(src, pl.source_page, pl.crop_mm)
                    page.show_pdf_page(
                        rect, src, pl.source_page, clip=clip, rotate=pl.rotate
                    )
                for circle in sheet.circles:
                    center = fitz.Point(
                        circle.center.x * MM2PT, circle.center.y * MM2PT
                    )
                    page.draw_circle(
                        center,
                        (circle.diameter / 2) * MM2PT,
                        color=(0, 0, 0),
                        fill=(0, 0, 0),
                    )
                for line in sheet.lines:
                    page.draw_line(
                        fitz.Point(line.start.x * MM2PT, line.start.y * MM2PT),
                        fitz.Point(line.end.x * MM2PT, line.end.y * MM2PT),
                        color=(0, 0, 0),
                        width=line.width * MM2PT,
                    )
            out.save(output_path)
        except (RuntimeError, OSError, ValueError) as exc:
            raise PrintExportError(f"Falha ao gerar PDF de impressao: {output_path}") from exc
        finally:
            for src in sources.values():
                src.close()
            out.close()

    @staticmethod
    def _crop_clip(src, page_index: int, crop_mm: float):
        """Sub-retangulo da pagina de origem, recuado crop_mm de cada borda."""
        if crop_mm <= 0:
            return None
        crop_pt = crop_mm * MM2PT
        rect = src[page_index].rect
        if rect.width <= 2 * crop_pt or rect.height <= 2 * crop_pt:
            return None
        return fitz.Rect(
            rect.x0 + crop_pt, rect.y0 + crop_pt,
            rect.x1 - crop_pt, rect.y1 - crop_pt,
        )
