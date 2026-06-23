from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
from app.application.use_cases.import_image import ImportImageUseCase
from app.application.use_cases.import_pdf import ImportPdfUseCase
from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
from app.domain.model.artwork import Artwork, FileFormat
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.shared.errors import ImageImportError, ValidationError


@dataclass(frozen=True, slots=True)
class ProductionResult:
    sheets: list[Layout]  # uma ou varias chapas
    artworks: list[Artwork]
    sources: dict[str, tuple[str, int]]  # id da arte -> (caminho de render, pagina)
    # id da arte -> caminho original informado pelo usuario (chave de quantidade/projeto).
    # Para PDF e igual a origem; para imagem pode diferir (ex.: WEBP -> PNG em cache).
    origins: dict[str, str] = field(default_factory=dict)


class RunProductionPipelineUseCase:
    """Pipeline do MVP: importar -> faca retangular -> nesting.

    O importador e injetado (cruza para infraestrutura); faca e nesting tem
    defaults puros.
    """

    def __init__(
        self,
        import_uc: ImportPdfUseCase,
        faca_uc: GenerateRectangularCutUseCase | None = None,
        nesting_uc: RunGridNestingUseCase | None = None,
        image_uc: ImportImageUseCase | None = None,
    ) -> None:
        self._import = import_uc
        self._faca = faca_uc or GenerateRectangularCutUseCase()
        self._nesting = nesting_uc or RunGridNestingUseCase()
        self._image = image_uc

    def execute(
        self,
        pdf_paths: Sequence[str],
        material: Material,
        offset_mm: float,
        sheet_height: float = 0.0,
        box: str = "auto",
        on_progress: Callable[[int, int], None] | None = None,
        *,
        sensitivity: float = 50.0,
        ignore_white: bool = True,
    ) -> ProductionResult:
        artworks: list[Artwork] = []
        sources: dict[str, tuple[str, int]] = {}
        origins: dict[str, str] = {}
        total = len(pdf_paths)
        for index, path in enumerate(pdf_paths, start=1):
            if self._is_image(path):
                imported = self._import_image(path, sensitivity, ignore_white)
                artworks.append(imported.artwork)
                sources[imported.artwork.id] = (imported.render_path, 0)
                origins[imported.artwork.id] = path
            else:
                for page_index, art in enumerate(self._import.execute(path, box)):
                    with_faca = self._faca.execute(art, offset_mm)
                    artworks.append(with_faca)
                    sources[with_faca.id] = (path, page_index)
                    origins[with_faca.id] = path
            if on_progress is not None:
                on_progress(index, total)

        if not artworks:
            raise ValidationError("Nenhuma arte importada.")
        sheets = self._nesting.execute_sheets(artworks, material, sheet_height)
        return ProductionResult(
            sheets=sheets, artworks=artworks, sources=sources, origins=origins
        )

    @staticmethod
    def _is_image(path: str) -> bool:
        try:
            return FileFormat.from_path(path).is_image
        except ValueError:
            return False

    def _import_image(self, path: str, sensitivity: float, ignore_white: bool):
        if self._image is None:
            raise ImageImportError("Importador de imagem nao configurado.")
        return self._image.execute(
            path, sensitivity=sensitivity, ignore_white=ignore_white
        )
