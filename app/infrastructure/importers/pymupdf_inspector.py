from __future__ import annotations

import fitz

from app.application.dto.pdf_report import PdfDocumentReport, PdfPageReport
from app.application.ports.pdf_inspector import IPdfInspector
from app.domain.geometry import Measurement, Size
from app.shared.errors import PdfInspectionError


class PyMuPdfInspector(IPdfInspector):
    """Inspeciona PDFs com PyMuPDF. Apenas leitura/diagnostico, sem faca."""

    def inspect(self, path: str) -> PdfDocumentReport:
        try:
            document = fitz.open(path)
        except Exception as exc:  # erros do fitz nao sao tipados
            raise PdfInspectionError(f"Falha ao abrir PDF: {path}") from exc

        try:
            if not document.is_pdf:
                raise PdfInspectionError(f"Arquivo nao e um PDF valido: {path}")
            pages = tuple(
                self._inspect_page(index, document[index])
                for index in range(document.page_count)
            )
            return PdfDocumentReport(path=path, page_count=document.page_count, pages=pages)
        finally:
            document.close()

    @staticmethod
    def _inspect_page(index: int, page: fitz.Page) -> PdfPageReport:
        rect = page.rect
        width_pt, height_pt = rect.width, rect.height
        size_mm = Size(
            Measurement.points(width_pt).millimeters,
            Measurement.points(height_pt).millimeters,
        )
        return PdfPageReport(
            index=index,
            size_mm=size_mm,
            width_pt=width_pt,
            height_pt=height_pt,
            vector_drawings=len(page.get_drawings()),
            raster_images=len(page.get_images(full=True)),
        )
