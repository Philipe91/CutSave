from __future__ import annotations

from collections.abc import Sequence

from app.application.ports.dxf_exporter import IDxfExporter
from app.domain.cut.registration import RegistrationMark
from app.domain.cut.shared import Segment
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


class ExportDxfUseCase:
    """Exporta facas (quadrados e/ou compartilhada) e marcas para um DXF."""

    def __init__(self, exporter: IDxfExporter) -> None:
        self._exporter = exporter

    def execute(
        self,
        contours: CutContour | Sequence[CutContour],
        output_path: str,
        *,
        segments: Sequence[Segment] = (),
        marks: Sequence[RegistrationMark] = (),
    ) -> str:
        if isinstance(contours, CutContour):
            contours = [contours]
        contours = list(contours)
        segments = list(segments)
        if not contours and not segments:
            raise ValidationError("Nenhuma faca para exportar.")
        self._exporter.export(contours, output_path, segments=segments, marks=marks)
        return output_path
