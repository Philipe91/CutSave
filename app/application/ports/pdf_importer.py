from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.model.artwork import Artwork


class IPdfImporter(ABC):
    """Porta de importacao de PDF. A infraestrutura implementa.

    Cada pagina do PDF gera uma Artwork independente.
    """

    @abstractmethod
    def import_artworks(self, path: str) -> list[Artwork]:
        """Importa o PDF e retorna uma Artwork por pagina."""
        raise NotImplementedError
