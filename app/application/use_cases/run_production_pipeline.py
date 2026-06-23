from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
from app.application.use_cases.import_pdf import ImportPdfUseCase
from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
from app.domain.model.artwork import Artwork
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class ProductionResult:
    sheets: list[Layout]  # uma ou varias chapas
    artworks: list[Artwork]
    sources: dict[str, tuple[str, int]]  # id da arte -> (caminho, pagina)


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
    ) -> None:
        self._import = import_uc
        self._faca = faca_uc or GenerateRectangularCutUseCase()
        self._nesting = nesting_uc or RunGridNestingUseCase()

    def execute(
        self,
        pdf_paths: Sequence[str],
        material: Material,
        offset_mm: float,
        sheet_height: float = 0.0,
        box: str = "auto",
        on_progress: Callable[[int, int], None] | None = None,
    ) -> ProductionResult:
        artworks: list[Artwork] = []
        sources: dict[str, tuple[str, int]] = {}
        total = len(pdf_paths)
        for index, path in enumerate(pdf_paths, start=1):
            for page_index, art in enumerate(self._import.execute(path, box)):
                with_faca = self._faca.execute(art, offset_mm)
                artworks.append(with_faca)
                sources[with_faca.id] = (path, page_index)
            if on_progress is not None:
                on_progress(index, total)

        if not artworks:
            raise ValidationError("Nenhuma arte importada.")
        sheets = self._nesting.execute_sheets(artworks, material, sheet_height)
        return ProductionResult(sheets=sheets, artworks=artworks, sources=sources)
