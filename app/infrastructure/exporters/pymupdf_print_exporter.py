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
                    page.show_pdf_page(rect, src, pl.source_page)
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
            out.save(output_path)
        except (RuntimeError, OSError, ValueError) as exc:
            raise PrintExportError(f"Falha ao gerar PDF de impressao: {output_path}") from exc
        finally:
            for src in sources.values():
                src.close()
            out.close()
