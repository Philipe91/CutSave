from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path

from app.application.dto.print_placement import PrintSheet
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.infrastructure.exporters.pdf_writer import PdfWriter
from app.infrastructure.pdfium_boxes import PDFIUM_LOCK, open_pdf, raw_box, trim_clip_pdf
from app.infrastructure.pdfium_knife import knife_free_pdf
from app.shared.errors import PrintExportError

MM2PT = 72.0 / 25.4
PT2MM = 25.4 / 72.0
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _is_image_source(path: str) -> bool:
    return Path(path).suffix.lower() in _IMAGE_SUFFIXES


class PikePdfPrintExporter(IPrintPdfExporter):
    """Gera o PDF de impressao (uma pagina por chapa), preservando vetores.

    Substitui o exportador PyMuPDF (migracao de licenca AGPL -> livre):
    cada pagina-fonte entra como Form XObject (sem rasterizar), com o mesmo
    recorte (caixa escolhida menos o recorte de borda) e rotacao. A
    exportacao em imagem rasteriza esse mesmo documento com o pdfium.
    """

    def _build_writer(self, sheets: Sequence[PrintSheet]) -> PdfWriter:
        writer = PdfWriter()
        clips: dict = {}  # (path, pagina, box, crop) -> clip em pt (ou None)
        try:
            for sheet in sheets:
                writer.new_page(sheet.size.width, sheet.size.height)
                for pl in sheet.placements:
                    if _is_image_source(pl.source_path):
                        writer.place_image(
                            pl.source_path,
                            pl.position.x, pl.position.y,
                            pl.size.width, pl.size.height,
                            rotate=pl.rotate,
                        )
                        continue
                    # impressão SEM a linha magenta da faca (cópia limpa)
                    src = knife_free_pdf(pl.source_path)
                    key = (src, pl.source_page, pl.box, pl.crop_mm)
                    if key not in clips:
                        clips[key] = self._source_clip(*key)
                    writer.place_pdf_page(
                        src, pl.source_page,
                        pl.position.x, pl.position.y,
                        pl.size.width, pl.size.height,
                        rotate=pl.rotate, clip_pdf_pt=clips[key],
                    )
                for circle in sheet.circles:
                    writer.draw_circle(
                        (circle.center.x, circle.center.y),
                        circle.diameter / 2,
                        color=(0, 0, 0), fill=(0, 0, 0),
                    )
                for line in sheet.lines:
                    writer.draw_line(
                        (line.start.x, line.start.y),
                        (line.end.x, line.end.y),
                        width_pt=line.width * MM2PT,
                        color=(0, 0, 0),
                    )
        except Exception as exc:
            writer.close()
            if isinstance(exc, PrintExportError):
                raise
            raise PrintExportError(
                "Falha ao compor o documento de impressao."
            ) from exc
        return writer

    def export(self, sheets: Sequence[PrintSheet], output_path: str) -> None:
        writer = self._build_writer(sheets)
        try:
            writer.save(output_path)
        except Exception as exc:
            raise PrintExportError(
                f"Falha ao gerar PDF de impressao: {output_path}"
            ) from exc
        finally:
            writer.close()

    def export_image(
        self,
        sheets: Sequence[PrintSheet],
        output_path: str,
        *,
        dpi: int = 150,
        image_format: str = "png",
    ) -> list[str]:
        """Rasteriza o documento de impressao: uma imagem por chapa, no DPI
        dado. Com mais de uma chapa, gera arquivos numerados (..._01, _02).
        Retorna os caminhos gerados."""
        import pypdfium2 as pdfium

        fmt = image_format.lower()
        if fmt == "jpg":
            fmt = "jpeg"
        ext = Path(output_path).suffix or ("." + ("jpg" if fmt == "jpeg" else fmt))
        stem = str(Path(output_path).with_suffix(""))
        writer = self._build_writer(sheets)
        try:
            data = writer.save_bytes()
        finally:
            writer.close()
        generated: list[str] = []
        try:
            with PDFIUM_LOCK:  # pdfium não é thread-safe (worker + UI ao vivo)
                doc = pdfium.PdfDocument(io.BytesIO(data))
                try:
                    multi = len(doc) > 1
                    for index in range(len(doc)):
                        pil = doc[index].render(scale=dpi / 72.0).to_pil()
                        target = f"{stem}_{index + 1:02d}{ext}" if multi else output_path
                        # dpi GRAVADO no arquivo: sem ele o RIP/Corel abre a
                        # 96dpi e a chapa de 19,7cm vira 92cm (teste real
                        # 16/07 — regressão da migração PyMuPDF->pdfium)
                        if fmt == "jpeg":
                            pil.convert("RGB").save(
                                target, format="JPEG", quality=95, dpi=(dpi, dpi)
                            )
                        else:
                            pil.save(target, format=fmt.upper(), dpi=(dpi, dpi))
                        generated.append(target)
                finally:
                    doc.close()
        except Exception as exc:
            raise PrintExportError(f"Falha ao gerar imagem: {output_path}") from exc
        return generated

    @staticmethod
    def _source_clip(path: str, page_index: int, box: str, crop_mm: float):
        """Recorte da origem em coords PDF cruas (pt): caixa escolhida
        (midia/apara) menos o recorte de borda. None = pagina inteira."""
        with PDFIUM_LOCK:  # pdfium não é thread-safe (worker + UI ao vivo)
            doc = open_pdf(path)
            try:
                page = doc[page_index]
                rect = trim_clip_pdf(page, box)
                if rect is None:
                    rect = raw_box(page, "MediaBox")
                    if rect is None:
                        w, h = page.get_size()
                        rect = (0.0, 0.0, w, h)
                if crop_mm > 0:
                    crop_pt = crop_mm * MM2PT
                    x0, y0, x1, y1 = rect
                    if (x1 - x0) > 2 * crop_pt and (y1 - y0) > 2 * crop_pt:
                        rect = (x0 + crop_pt, y0 + crop_pt, x1 - crop_pt, y1 - crop_pt)
                return tuple(rect)
            finally:
                doc.close()
