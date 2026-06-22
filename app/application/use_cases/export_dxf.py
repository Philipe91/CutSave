from __future__ import annotations

from collections.abc import Sequence

from app.application.ports.dxf_exporter import IDxfExporter
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


class ExportDxfUseCase:
    """Exporta uma ou varias facas para um arquivo DXF."""

    def __init__(self, exporter: IDxfExporter) -> None:
        self._exporter = exporter

    def execute(
        self,
        contours: CutContour | Sequence[CutContour],
        output_path: str,
    ) -> str:
        if isinstance(contours, CutContour):
            contours = [contours]
        contours = list(contours)
        if not contours:
            raise ValidationError("Nenhuma faca para exportar.")
        self._exporter.export(contours, output_path)
        return output_path
