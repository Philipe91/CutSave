from __future__ import annotations

from dataclasses import dataclass

from app.domain.geometry import Point2D, Size


@dataclass(frozen=True, slots=True)
class PrintPlacement:
    """Carimbo de uma pagina de origem no PDF de impressao.

    position e size em milimetros (canto inferior-esquerdo + tamanho real da arte).
    """

    source_path: str
    source_page: int
    position: Point2D
    size: Size
    crop_mm: float = 0.0  # recorta esse tanto de cada borda da pagina de origem
    rotate: int = 0  # rotacao da arte em graus (0/90/180/270)
    box: str = "media"  # caixa de origem: 'media' (sangria) ou 'trim'/'auto' (apara)


@dataclass(frozen=True, slots=True)
class PrintCircle:
    """Circulo preenchido impresso (marca de registro). center/diameter em mm."""

    center: Point2D
    diameter: float


@dataclass(frozen=True, slots=True)
class PrintLine:
    """Linha preenchida impressa (marca em L da Mimaki). Espessura em mm."""

    start: Point2D
    end: Point2D
    width: float


@dataclass(frozen=True, slots=True)
class PrintSheet:
    """Uma pagina do PDF de impressao: carimbos + marcas + tamanho da folha (mm)."""

    placements: tuple[PrintPlacement, ...]
    size: Size
    circles: tuple[PrintCircle, ...] = ()
    lines: tuple[PrintLine, ...] = ()
