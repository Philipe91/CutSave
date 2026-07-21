from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.geometry.polygon_with_holes import PolygonWithHoles


@dataclass(frozen=True, slots=True)
class GlyphShapes:
    """Corpos vetoriais de UMA letra do texto.

    A associacao letra -> corpos e preservada de proposito: o "i" tem dois
    corpos (haste + pingo) e o "%" tem tres — a Fase 4/5 decide se nesta a
    letra inteira junta ou cada corpo solto.
    """

    char: str
    shapes: tuple[PolygonWithHoles, ...]


class ITextVectorizer(ABC):
    """Porta de vetorizacao de texto digitado (Fase 3C) para o nesting.

    Retorna uma GlyphShapes por caractere COM corpo, na ordem do texto
    (espaco e glifos vazios ficam de fora, mas empurram as letras seguintes
    pelo advance), em MILIMETROS, origem topo-esquerda, Y crescendo para
    baixo e bounding box global comecando em (0, 0). size_mm e o corpo
    tipografico (em) — a maiuscula fica ~70% disso (capHeight). Lanca
    TextVectorizeError para fonte ilegivel, caractere sem glifo ou
    parametros invalidos.
    """

    @abstractmethod
    def vectorize(self, text: str, font_path: str, size_mm: float) -> list[GlyphShapes]:
        raise NotImplementedError
