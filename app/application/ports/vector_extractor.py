from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.cut.vector import RingInfo


class IVectorExtractor(ABC):
    """Porta de extracao de geometrias vetoriais de uma pagina de PDF.

    Retorna aneis de pontos (x, y) em milimetros, prontos para uniao geometrica.
    """

    @abstractmethod
    def extract_rings(self, path: str, page_index: int = 0) -> list[list[tuple[float, float]]]:
        raise NotImplementedError

    def extract_rings_info(self, path: str, page_index: int = 0) -> list[RingInfo]:
        """Aneis + pintura (traço/preenchimento/cor) para separar FACA de arte.

        Implementação padrão degrada para extract_rings sem metadados (tudo
        cai no tier "all" da seleção — o comportamento antigo)."""
        return [RingInfo(ring) for ring in self.extract_rings(path, page_index)]
