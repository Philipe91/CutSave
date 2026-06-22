from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase
from app.application.use_cases.import_pdf import ImportPdfUseCase
from app.application.use_cases.run_production_pipeline import RunProductionPipelineUseCase
from app.infrastructure.exporters.dxf_exporter import DxfExporter
from app.infrastructure.exporters.pymupdf_print_exporter import PyMuPdfPrintExporter
from app.infrastructure.importers.pymupdf_importer import PyMuPdfImporter
from app.presentation.main_window import MainWindow
from app.shared.config import AppPaths, SettingsStore
from app.shared.logging import setup_logging


def main() -> int:
    paths = AppPaths.default().ensure()
    store = SettingsStore(paths.config_file)
    settings = store.load_or_create()
    setup_logging(settings.log_level, paths.logs_dir)

    app = QApplication(sys.argv)
    pipeline = RunProductionPipelineUseCase(ImportPdfUseCase(PyMuPdfImporter()))
    window = MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PyMuPdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        store,
        settings,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
