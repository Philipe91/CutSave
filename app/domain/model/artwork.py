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
    # facas ADICIONAIS na mesma peca: uma imagem pode conter varios desenhos
    # separados (ex.: folha com 6 adesivos) -> uma linha de corte para cada.
    # A peca segue sendo UMA so (bounding box); estas sao cortes internos.
    extra_cuts: tuple[CutContour, ...] = ()
    # Peca vinda do MODO CORTE (letras/formas true-shape, tarefa E1). Campo
    # ADITIVO com default False: toda arte de IMPRESSAO (mesmo com faca)
    # continua no comportamento de sempre; so quem nasce no Modo Corte liga
    # isto — e ganha, por exemplo, hit-test pelo contorno real no canvas.
    from_cut_mode: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise ValidationError("Artwork requer id.")
        if not self.name.strip():
            raise ValidationError("Artwork requer nome.")

    @property
    def has_cut(self) -> bool:
        return self.cut_contour is not None
