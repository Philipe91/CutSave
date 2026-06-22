from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.dto.pdf_report import PdfDocumentReport


class IPdfInspector(ABC):
    """Porta de inspecao tecnica de PDF. A infraestrutura implementa."""

    @abstractmethod
    def inspect(self, path: str) -> PdfDocumentReport:
        """Analisa o PDF e retorna seu diagnostico tecnico."""
        raise NotImplementedError
