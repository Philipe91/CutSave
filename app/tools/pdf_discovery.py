from __future__ import annotations

import sys

from app.application.dto.pdf_report import PdfDocumentReport
from app.infrastructure.importers.pymupdf_inspector import PyMuPdfInspector
from app.shared.errors import PrintNestError


def format_report(report: PdfDocumentReport) -> str:
    """Formata o diagnostico tecnico de um PDF como texto legivel."""
    lines = [
        f"Arquivo: {report.path}",
        f"Paginas: {report.page_count}",
        f"Vetores: {'sim' if report.has_vector else 'nao'} | "
        f"Raster: {'sim' if report.has_raster else 'nao'}",
    ]
    for page in report.pages:
        lines.append(
            f"  Pagina {page.index + 1}: "
            f"{page.size_mm.width:.2f} x {page.size_mm.height:.2f} mm "
            f"({page.width_pt:.1f} x {page.height_pt:.1f} pt) | "
            f"vetores={page.vector_drawings} imagens={page.raster_images}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Uso: python -m app.tools.pdf_discovery <arquivo.pdf> [...]", file=sys.stderr)
        return 2

    inspector = PyMuPdfInspector()
    exit_code = 0
    for path in args:
        try:
            report = inspector.inspect(path)
        except PrintNestError as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        print(format_report(report))
        print()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
