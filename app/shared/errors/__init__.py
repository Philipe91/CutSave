class PrintNestError(Exception):
    """Erro base de toda a aplicacao PrintNest."""


class ConfigError(PrintNestError):
    """Falha ao carregar ou salvar a configuracao da aplicacao."""


class ValidationError(PrintNestError):
    """Entidade de dominio construida com dados invalidos."""


class PdfInspectionError(PrintNestError):
    """Falha ao abrir ou analisar um arquivo PDF."""


class PdfImportError(PrintNestError):
    """Falha ao importar um arquivo PDF como Artworks."""


class DxfExportError(PrintNestError):
    """Falha ao exportar geometrias para DXF."""


class PrintExportError(PrintNestError):
    """Falha ao gerar o PDF de impressao."""
