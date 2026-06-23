from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.cut.registration import RegistrationMark
from app.domain.cut.shared import Segment
from app.domain.model.cut_contour import CutContour


class IDxfExporter(ABC):
    """Porta de exportacao de facas para DXF.

    Suporta contornos fechados (faca de quadrados), segmentos abertos (faca
    compartilhada) e marcas de registro (circulos).
    """

    @abstractmethod
    def export(
        self,
        contours: Sequence[CutContour],
        output_path: str,
        *,
        segments: Sequence[Segment] = (),
        marks: Sequence[RegistrationMark] = (),
    ) -> None:
        raise NotImplementedError
