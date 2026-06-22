from __future__ import annotations

from abc import ABC, abstractmethod


class IVectorExtractor(ABC):
    """Porta de extracao de geometrias vetoriais de uma pagina de PDF.

    Retorna aneis de pontos (x, y) em milimetros, prontos para uniao geometrica.
    """

    @abstractmethod
    def extract_rings(self, path: str, page_index: int = 0) -> list[list[tuple[float, float]]]:
        raise NotImplementedError
