from __future__ import annotations

from app.application.dto.pdf_report import PdfDocumentReport, PdfPageReport
from app.application.ports.pdf_inspector import IPdfInspector
from app.domain.geometry import Measurement, Size
from app.infrastructure.importers.pdfium_importer import count_page_objects
from app.infrastructure.pdfium_boxes import open_pdf
from app.shared.errors import PdfImportError, PdfInspectionError


class PdfiumInspector(IPdfInspector):
    """Inspeciona PDFs com pypdfium2. Apenas leitura/diagnostico, sem faca."""

    def inspect(self, path: str) -> PdfDocumentReport:
        try:
            document = open_pdf(path)
        except PdfImportError as exc:
            raise PdfInspectionError(str(exc)) from exc

        try:
            pages = tuple(
                self._inspect_page(index, document[index])
                for index in range(len(document))
            )
            return PdfDocumentReport(path=path, page_count=len(document), pages=pages)
        finally:
            document.close()

    @staticmethod
    def _inspect_page(index: int, page) -> PdfPageReport:
        width_pt, height_pt = page.get_size()  # ja considera a rotacao
        drawings, images = count_page_objects(page)
        return PdfPageReport(
            index=index,
            size_mm=Size(
                Measurement.points(width_pt).millimeters,
                Measurement.points(height_pt).millimeters,
            ),
            width_pt=width_pt,
            height_pt=height_pt,
            vector_drawings=drawings,
            raster_images=images,
        )
