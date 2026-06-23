from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import fitz

from app.application.dto.print_placement import PrintSheet
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.infrastructure.pdf_boxes import box_clip_rect
from app.shared.errors import PrintExportError

MM2PT = 72.0 / 25.4
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _is_image_source(path: str) -> bool:
    return Path(path).suffix.lower() in _IMAGE_SUFFIXES


class PyMuPdfPrintExporter(IPrintPdfExporter):
    """Gera o PDF de impressao (uma pagina por chapa), preservando vetores.

    Usa show_pdf_page, que embute cada pagina como Form XObject (sem rasterizar).
    A exportacao em imagem (PNG/JPEG) rasteriza esse mesmo documento no DPI pedido.
    """

    def _build_document(self, sheets: Sequence[PrintSheet]) -> fitz.Document:
        """Compoe o documento de impressao (uma pagina por chapa) e o devolve.

        As origens sao fechadas aqui; o conteudo ja fica embutido em 'out'.
        """
        out = fitz.open()
        sources: dict[str, fitz.Document] = {}
        try:
            for sheet in sheets:
                page = out.new_page(
                    width=sheet.size.width * MM2PT, height=sheet.size.height * MM2PT
                )
                for pl in sheet.placements:
                    rect = fitz.Rect(
                        pl.position.x * MM2PT,
                        pl.position.y * MM2PT,
                        (pl.position.x + pl.size.width) * MM2PT,
                        (pl.position.y + pl.size.height) * MM2PT,
                    )
                    if _is_image_source(pl.source_path):
                        # imagem raster: embute o arquivo direto (crop nao se aplica)
                        page.insert_image(
                            rect, filename=pl.source_path,
                            keep_proportion=False, rotate=pl.rotate,
                        )
                        continue
                    src = sources.get(pl.source_path)
                    if src is None:
                        src = fitz.open(pl.source_path)
                        sources[pl.source_path] = src
                    clip = self._source_clip(src, pl.source_page, pl.box, pl.crop_mm)
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
        except (RuntimeError, OSError, ValueError) as exc:
            out.close()
            raise PrintExportError("Falha ao compor o documento de impressao.") from exc
        finally:
            for src in sources.values():
                src.close()
        return out

    def export(self, sheets: Sequence[PrintSheet], output_path: str) -> None:
        out = self._build_document(sheets)
        try:
            out.save(output_path)
        except (RuntimeError, OSError, ValueError) as exc:
            raise PrintExportError(f"Falha ao gerar PDF de impressao: {output_path}") from exc
        finally:
            out.close()

    def export_image(
        self,
        sheets: Sequence[PrintSheet],
        output_path: str,
        *,
        dpi: int = 150,
        image_format: str = "png",
    ) -> list[str]:
        """Rasteriza o documento de impressao: uma imagem por chapa, no DPI dado.

        Com mais de uma chapa, gera arquivos numerados (..._01, _02). Retorna os
        caminhos gerados.
        """
        fmt = image_format.lower()
        if fmt == "jpg":
            fmt = "jpeg"
        ext = Path(output_path).suffix or ("." + ("jpg" if fmt == "jpeg" else fmt))
        stem = str(Path(output_path).with_suffix(""))
        out = self._build_document(sheets)
        generated: list[str] = []
        try:
            multi = out.page_count > 1
            for index in range(out.page_count):
                pixmap = out[index].get_pixmap(dpi=dpi)
                target = f"{stem}_{index + 1:02d}{ext}" if multi else output_path
                pixmap.save(target)
                generated.append(target)
        except (RuntimeError, OSError, ValueError) as exc:
            raise PrintExportError(f"Falha ao gerar imagem: {output_path}") from exc
        finally:
            out.close()
        return generated

    @staticmethod
    def _source_clip(src, page_index: int, box: str, crop_mm: float):
        """Recorte da origem: caixa escolhida (media/apara) menos o recorte de borda."""
        page = src[page_index]
        rect = box_clip_rect(src, page, box) or page.rect
        if crop_mm > 0:
            crop_pt = crop_mm * MM2PT
            if rect.width > 2 * crop_pt and rect.height > 2 * crop_pt:
                rect = fitz.Rect(
                    rect.x0 + crop_pt, rect.y0 + crop_pt,
                    rect.x1 - crop_pt, rect.y1 - crop_pt,
                )
        return rect
