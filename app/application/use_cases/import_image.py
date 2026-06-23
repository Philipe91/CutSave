from __future__ import annotations

from app.application.ports.image_importer import IImageImporter, ImportedImage


class ImportImageUseCase:
    """Caso de uso de importacao de imagem (PNG/JPG/WEBP) com faca automatica.

    Ponto de entrada estavel; delega a leitura/deteccao ao importador injetado
    (Dependency Inversion), espelhando ImportPdfUseCase.
    """

    def __init__(self, importer: IImageImporter) -> None:
        self._importer = importer

    def execute(
        self,
        path: str,
        *,
        sensitivity: float = 50.0,
        ignore_white: bool = True,
    ) -> ImportedImage:
        return self._importer.import_image(
            path, sensitivity=sensitivity, ignore_white=ignore_white
        )
