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


@dataclass(frozen=True, slots=True)
class PrintSheet:
    """Uma pagina do PDF de impressao: seus carimbos + o tamanho da folha (mm)."""

    placements: tuple[PrintPlacement, ...]
    size: Size
