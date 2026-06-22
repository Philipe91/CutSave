from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.model.cut_contour import CutContour


class IDxfExporter(ABC):
    """Porta de exportacao de facas (CutContour) para arquivo DXF."""

    @abstractmethod
    def export(self, contours: Sequence[CutContour], output_path: str) -> None:
        raise NotImplementedError
