from __future__ import annotations

from app.application.ports.pdf_importer import IPdfImporter
from app.domain.model.artwork import Artwork


class ImportPdfUseCase:
    """Caso de uso de importacao de PDF.

    Ponto de entrada estavel da aplicacao; delega a leitura ao importador
    injetado (Dependency Inversion). Aqui no futuro entrara a politica de
    associacao a um Project.
    """

    def __init__(self, importer: IPdfImporter) -> None:
        self._importer = importer

    def execute(self, path: str, box: str = "auto") -> list[Artwork]:
        return self._importer.import_artworks(path, box)
