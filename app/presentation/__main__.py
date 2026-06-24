from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase
from app.application.use_cases.import_image import ImportImageUseCase
from app.application.use_cases.import_pdf import ImportPdfUseCase
from app.application.use_cases.run_production_pipeline import RunProductionPipelineUseCase
from app.infrastructure.exporters.dxf_exporter import DxfExporter
from app.infrastructure.exporters.pymupdf_print_exporter import PyMuPdfPrintExporter
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter
from app.infrastructure.importers.pymupdf_importer import PyMuPdfImporter
from app.infrastructure.rendering.pymupdf_renderer import PyMuPdfPageRenderer
from app.presentation import theme
from app.presentation.main_window import MainWindow
from app.shared.config import AppPaths, SettingsStore
from app.shared.logging import setup_logging
from app.shared.resources import resource_path


def main() -> int:
    paths = AppPaths.default().ensure()
    store = SettingsStore(paths.config_file)
    settings = store.load_or_create()
    setup_logging(settings.log_level, paths.logs_dir)

    app = QApplication(sys.argv)
    # Trava o tema em Claro: a interface fica igual em qualquer PC,
    # independente do modo Claro/Escuro do Windows (Qt 6 segue o sistema).
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyleSheet(theme.build_app_qss())  # folha de estilo global (design system)
    icon_file = resource_path("assets/printnest.ico")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))
    pipeline = RunProductionPipelineUseCase(
        ImportPdfUseCase(PyMuPdfImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(paths.cache_dir)),
    )
    window = MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PyMuPdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PyMuPdfPageRenderer(),
        store,
        settings,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
