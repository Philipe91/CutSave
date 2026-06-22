from __future__ import annotations

from dataclasses import dataclass

from app.domain.geometry import Size


@dataclass(frozen=True, slots=True)
class PdfPageReport:
    """Diagnostico tecnico de uma pagina de PDF (sem interpretacao de faca)."""

    index: int
    size_mm: Size
    width_pt: float
    height_pt: float
    vector_drawings: int
    raster_images: int

    @property
    def has_vector(self) -> bool:
        return self.vector_drawings > 0

    @property
    def has_raster(self) -> bool:
        return self.raster_images > 0


@dataclass(frozen=True, slots=True)
class PdfDocumentReport:
    """Diagnostico tecnico de um arquivo PDF inteiro."""

    path: str
    page_count: int
    pages: tuple[PdfPageReport, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "pages", tuple(self.pages))

    @property
    def has_vector(self) -> bool:
        return any(p.has_vector for p in self.pages)

    @property
    def has_raster(self) -> bool:
        return any(p.has_raster for p in self.pages)
