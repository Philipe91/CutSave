from __future__ import annotations

from pathlib import Path

import fitz

from app.application.ports.pdf_importer import IPdfImporter
from app.domain.geometry import Measurement, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.shared.errors import PdfImportError

# Numero minimo de desenhos vetoriais para considerar a arte "vetorial".
_VECTOR_MIN_DRAWINGS = 2
# Ordem de prioridade da caixa que define o tamanho real do produto.
_BOX_PRIORITY = ("TrimBox", "CropBox", "MediaBox")
_ROTATIONS_THAT_SWAP = (90, 270)


def classify_kind(drawings: int, images: int) -> ArtKind:
    """Classificacao conservadora por contagem (sem heuristica de contorno).

    - VETORIAL: ha geometria vetorial relevante (pode gerar faca).
    - RASTER: arte baseada em imagem, sem geometria vetorial relevante.
    - RETANGULAR: nem vetor relevante nem imagem (provavel fill retangular).
    """
    if drawings >= _VECTOR_MIN_DRAWINGS:
        return ArtKind.VETORIAL
    if images > 0:
        return ArtKind.RASTER
    return ArtKind.RETANGULAR


class PyMuPdfImporter(IPdfImporter):
    """Importa PDF com PyMuPDF: dimensao real, rotacao e classificacao."""

    def import_artworks(self, path: str) -> list[Artwork]:
        try:
            document = fitz.open(path)
        except Exception as exc:  # erros do fitz nao sao tipados
            raise PdfImportError(f"Falha ao abrir PDF: {path}") from exc

        try:
            if not document.is_pdf:
                raise PdfImportError(f"Arquivo nao e um PDF valido: {path}")
            stem = Path(path).stem
            return [
                self._page_to_artwork(document, document[i], stem, i)
                for i in range(document.page_count)
            ]
        finally:
            document.close()

    def _page_to_artwork(self, doc, page, stem: str, index: int) -> Artwork:
        width_pt, height_pt = self._product_box_pt(doc, page)
        if page.rotation in _ROTATIONS_THAT_SWAP:
            width_pt, height_pt = height_pt, width_pt

        size = Size(
            Measurement.points(width_pt).millimeters,
            Measurement.points(height_pt).millimeters,
        )
        kind = classify_kind(
            drawings=len(page.get_drawings()),
            images=len(page.get_images(full=True)),
        )
        return Artwork(
            id=f"{stem}#p{index + 1}",
            name=f"{stem} (pagina {index + 1})",
            file_format=FileFormat.PDF,
            size=size,
            kind=kind,
        )

    @staticmethod
    def _product_box_pt(doc, page) -> tuple[float, float]:
        """Dimensao do produto em points, na prioridade Trim -> Crop -> Media."""
        for key in _BOX_PRIORITY:
            box = PyMuPdfImporter._read_box(doc, page, key)
            if box is not None:
                return box
        # Fallback: caixa resolvida pelo fitz (cobre boxes herdadas do pai).
        rect = page.rect
        return rect.width, rect.height

    @staticmethod
    def _read_box(doc, page, key: str) -> tuple[float, float] | None:
        kind, value = doc.xref_get_key(page.xref, key)
        if kind == "null" or not value:
            return None
        try:
            nums = [float(n) for n in value.strip("[]").split()]
        except ValueError:
            return None
        if len(nums) != 4:
            return None
        x0, y0, x1, y1 = nums
        return abs(x1 - x0), abs(y1 - y0)
