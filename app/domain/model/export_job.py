from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.domain.model.layout import Layout
from app.shared.errors import ValidationError


class ExportFormat(Enum):
    PDF = "pdf"
    DXF = "dxf"


class ExportStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExportJob:
    """Pedido imutavel de exportacao de um layout para um arquivo."""

    id: str
    layout: Layout
    export_format: ExportFormat
    output_path: str
    status: ExportStatus = ExportStatus.PENDING

    def __post_init__(self) -> None:
        if not self.id:
            raise ValidationError("ExportJob requer id.")
        if not self.output_path.strip():
            raise ValidationError("ExportJob requer output_path.")

    def with_status(self, status: ExportStatus) -> ExportJob:
        """Retorna uma nova copia com o status alterado (imutavel)."""
        return replace(self, status=status)
