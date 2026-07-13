from __future__ import annotations

from pathlib import Path

import pypdfium2.raw as pdfium_raw

from app.application.ports.pdf_importer import IPdfImporter
from app.domain.geometry import Measurement, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.infrastructure.pdfium_boxes import open_pdf, page_box_dims_pt

# Numero minimo de desenhos vetoriais para considerar a arte "vetorial".
_VECTOR_MIN_DRAWINGS = 2
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


def count_page_objects(page) -> tuple[int, int]:
    """(desenhos vetoriais, imagens) da pagina, contando os objetos do
    pdfium (paths e imagens POSICIONADAS, inclusive dentro de formularios)."""
    drawings = images = 0
    for obj in page.get_objects(max_depth=4):
        if obj.type == pdfium_raw.FPDF_PAGEOBJ_PATH:
            drawings += 1
        elif obj.type == pdfium_raw.FPDF_PAGEOBJ_IMAGE:
            images += 1
    return drawings, images


class PdfiumImporter(IPdfImporter):
    """Importa PDF com pypdfium2: dimensao real, rotacao e classificacao.

    Substitui o importador PyMuPDF (migracao de licenca AGPL -> livre)
    mantendo o MESMO contrato: caixas com prioridade Apara -> Crop -> Midia
    no modo auto/trim, swap de dimensao em rotacao 90/270 e arredondamento
    de 0,001mm (QAX-03) para matar o ruido da conversao pt -> mm.
    """

    def import_artworks(self, path: str, box: str = "auto") -> list[Artwork]:
        document = open_pdf(path)
        try:
            stem = Path(path).stem
            return [
                self._page_to_artwork(document[i], stem, i, box)
                for i in range(len(document))
            ]
        finally:
            document.close()

    def _page_to_artwork(self, page, stem: str, index: int, box: str) -> Artwork:
        width_pt, height_pt = page_box_dims_pt(page, box)
        if page.get_rotation() in _ROTATIONS_THAT_SWAP:
            width_pt, height_pt = height_pt, width_pt

        # QAX-03: a conversao pt->mm traz ruido de float (uma pagina "100mm"
        # media 100,0000046mm) e 9 MILIONESIMOS de mm faziam o encaixe exato
        # descartar uma coluna inteira da chapa. Arredonda a 0,001mm (1 um) —
        # muito abaixo de qualquer tolerancia fisica de impressao/corte.
        size = Size(
            round(Measurement.points(width_pt).millimeters, 3),
            round(Measurement.points(height_pt).millimeters, 3),
        )
        drawings, images = count_page_objects(page)
        return Artwork(
            id=f"{stem}#p{index + 1}",
            name=f"{stem} (pagina {index + 1})",
            file_format=FileFormat.PDF,
            size=size,
            kind=classify_kind(drawings=drawings, images=images),
        )
