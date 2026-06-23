from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.geometry import Size
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


class FileFormat(Enum):
    PDF = "pdf"
    PNG = "png"
    JPG = "jpg"
    WEBP = "webp"

    @classmethod
    def from_path(cls, path: str) -> FileFormat:
        """Deriva o formato pela extensao do arquivo (jpeg conta como jpg)."""
        from pathlib import Path

        ext = Path(path).suffix.lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"
        return cls(ext)

    @property
    def is_image(self) -> bool:
        return self in (FileFormat.PNG, FileFormat.JPG, FileFormat.WEBP)


class ArtKind(Enum):
    """Classificacao inicial da arte, definida na importacao."""

    RETANGULAR = "retangular"
    VETORIAL = "vetorial"
    RASTER = "raster"


@dataclass(frozen=True, slots=True)
class Artwork:
    """Arte importada. Dimensao real ja convertida para milimetros.

    A faca (cut_contour) pode ser gerada depois da importacao, por isso opcional.
    """

    id: str
    name: str
    file_format: FileFormat
    size: Size
    kind: ArtKind
    cut_contour: CutContour | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValidationError("Artwork requer id.")
        if not self.name.strip():
            raise ValidationError("Artwork requer nome.")

    @property
    def has_cut(self) -> bool:
        return self.cut_contour is not None
