"""Ponto de entrada do executavel PrintNest (build PyInstaller).

Sem argumentos: abre a interface grafica.
Com --selftest: roda o fluxo completo (importar -> faca -> nesting ->
PDF -> DXF) de forma headless e sai com 0/1. Usado para validar a build.
"""
from __future__ import annotations

import sys


def _selftest() -> int:
    import os
    import tempfile

    import fitz
    from app.application.positioning import positioned_cut_contours_sheets
    from app.application.use_cases.export_dxf import ExportDxfUseCase
    from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase
    from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
    from app.application.use_cases.import_pdf import ImportPdfUseCase
    from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
    from app.domain.model.material import Material
    from app.infrastructure.exporters.dxf_exporter import DxfExporter
    from app.infrastructure.exporters.pymupdf_print_exporter import PyMuPdfPrintExporter
    from app.infrastructure.importers.pymupdf_importer import PyMuPdfImporter

    tmp = tempfile.mkdtemp(prefix="printnest_selftest_")
    src = os.path.join(tmp, "amostra.pdf")
    doc = fitz.open()
    for _ in range(3):
        page = doc.new_page(width=200, height=100)
        page.draw_rect(page.rect, color=(1, 1, 0), fill=(1, 1, 0))
    doc.save(src)
    doc.close()

    arts = ImportPdfUseCase(PyMuPdfImporter()).execute(src)
    faca = GenerateRectangularCutUseCase()
    arts = [faca.execute(a, 3.0) for a in arts]
    material = Material("UV", width=600, spacing=5)
    sheets = RunGridNestingUseCase().execute_sheets(arts, material, 0)
    sources = {a.id: (src, i) for i, a in enumerate(arts)}

    pdf_out = os.path.join(tmp, "IMPRESSAO.pdf")
    dxf_out = os.path.join(tmp, "CORTE.dxf")
    ExportPrintPdfUseCase(PyMuPdfPrintExporter()).execute(sheets, arts, sources, pdf_out)
    contours = positioned_cut_contours_sheets(sheets, arts, material.width)
    ExportDxfUseCase(DxfExporter()).execute(contours, dxf_out)

    ok = os.path.exists(pdf_out) and os.path.exists(dxf_out)
    print("SELFTEST OK" if ok else "SELFTEST FAIL")
    print(f"  pecas={sum(s.item_count for s in sheets)} pdf={pdf_out} dxf={dxf_out}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    from app.presentation.__main__ import main as gui_main

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
