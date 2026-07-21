from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.geometry.polygon_with_holes import PolygonWithHoles


class IVectorImporter(ABC):
    """Porta de importacao de arquivos vetoriais (SVG/PDF) para o nesting.

    Retorna uma PolygonWithHoles por forma fechada do arquivo, em MILIMETROS,
    origem topo-esquerda e Y crescendo para baixo (convencao do sistema),
    transforms do arquivo ja aplicados e furos ja detectados por contencao.
    Lanca VectorImportError se o arquivo nao puder ser lido.
    """

    @abstractmethod
    def load(self, path: str) -> list[PolygonWithHoles]:
        raise NotImplementedError
