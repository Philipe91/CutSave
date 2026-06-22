from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.application.positioning import SHEET_GAP_MM, positioned_cut_contours_sheets
from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase
from app.application.use_cases.run_production_pipeline import (
    ProductionResult,
    RunProductionPipelineUseCase,
)
from app.domain.model.material import Material
from app.shared.config.settings import AppSettings, SettingsStore


class ZoomableGraphicsView(QGraphicsView):
    """Preview com zoom (roda do mouse) e arrastar (segurar e mover)."""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class PipelineWorker(QObject):
    """Executa o pipeline em uma thread, sem travar a UI."""

    progress = Signal(int, int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, pipeline, paths, material, offset_mm, sheet_height):
        super().__init__()
        self._pipeline = pipeline
        self._paths = paths
        self._material = material
        self._offset = offset_mm
        self._sheet_height = sheet_height

    def run(self) -> None:
        try:
            result = self._pipeline.execute(
                self._paths, self._material, self._offset, self._sheet_height,
                on_progress=lambda done, total: self.progress.emit(done, total),
            )
        except Exception as exc:  # reportado a UI
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class MainWindow(QMainWindow):
    """Tela unica do MVP PrintNest."""

    def __init__(
        self,
        pipeline: RunProductionPipelineUseCase,
        print_export: ExportPrintPdfUseCase,
        dxf_export: ExportDxfUseCase,
        settings_store: SettingsStore,
        settings: AppSettings,
    ) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._print_export = print_export
        self._dxf_export = dxf_export
        self._store = settings_store
        self._settings = settings

        self._paths: list[str] = []
        self._result: ProductionResult | None = None
        self._thread: QThread | None = None
        self._worker: PipelineWorker | None = None

        self.setWindowTitle("PrintNest MVP")
        self._build_ui()
        self._load_settings()

    # ---- construcao da UI ----
    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)

        panel = QVBoxLayout()
        self._btn_add = QPushButton("Adicionar PDFs")
        self._btn_add.clicked.connect(lambda: self.add_pdfs())
        panel.addWidget(self._btn_add)

        self._list = QListWidget()
        panel.addWidget(self._list)

        panel.addWidget(QLabel("Largura da chapa (mm)"))
        self._width = QSpinBox()
        self._width.setRange(1, 20000)
        panel.addWidget(self._width)

        panel.addWidget(QLabel("Altura da chapa (mm) - 0 = chapa unica"))
        self._height = QSpinBox()
        self._height.setRange(0, 20000)
        panel.addWidget(self._height)

        panel.addWidget(QLabel("Espacamento (mm)"))
        self._spacing = QDoubleSpinBox()
        self._spacing.setRange(0, 500)
        panel.addWidget(self._spacing)

        panel.addWidget(QLabel("Offset da faca (mm)"))
        self._offset = QDoubleSpinBox()
        self._offset.setRange(-100, 100)
        panel.addWidget(self._offset)

        self._btn_generate = QPushButton("Gerar Producao")
        self._btn_generate.clicked.connect(lambda: self.generate())
        panel.addWidget(self._btn_generate)

        self._btn_pdf = QPushButton("Exportar PDF")
        self._btn_pdf.clicked.connect(lambda: self.export_pdf())
        self._btn_pdf.setEnabled(False)
        panel.addWidget(self._btn_pdf)

        self._btn_dxf = QPushButton("Exportar DXF")
        self._btn_dxf.clicked.connect(lambda: self.export_dxf())
        self._btn_dxf.setEnabled(False)
        panel.addWidget(self._btn_dxf)

        self._progress = QProgressBar()
        panel.addWidget(self._progress)

        self._status = QLabel("")
        panel.addWidget(self._status)
        panel.addStretch()

        self._scene = QGraphicsScene()
        self._view = ZoomableGraphicsView(self._scene)

        root.addLayout(panel, 0)
        root.addWidget(self._view, 1)
        self.setCentralWidget(central)

    # ---- settings ----
    def _load_settings(self) -> None:
        self._width.setValue(int(self._settings.material_width))
        self._height.setValue(int(self._settings.material_height))
        self._spacing.setValue(self._settings.spacing)
        self._offset.setValue(self._settings.offset)

    def _save_settings(self) -> None:
        self._settings.material_width = float(self._width.value())
        self._settings.material_height = float(self._height.value())
        self._settings.spacing = float(self._spacing.value())
        self._settings.offset = float(self._offset.value())
        self._store.save(self._settings)

    # ---- acoes ----
    def add_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar PDFs", self._settings.last_dir, "PDF (*.pdf)"
        )
        if paths:
            self.add_paths(paths)
            self._settings.last_dir = str(Path(paths[0]).parent)
            self._store.save(self._settings)

    def add_paths(self, paths: list[str]) -> None:
        for path in paths:
            self._paths.append(path)
            self._list.addItem(Path(path).name)

    def _material(self) -> Material:
        return Material(
            name="MVP",
            width=float(self._width.value()),
            spacing=float(self._spacing.value()),
        )

    def generate(self, *, blocking: bool = False) -> None:
        if not self._paths:
            QMessageBox.warning(self, "PrintNest", "Adicione ao menos um PDF.")
            return
        self._save_settings()
        material = self._material()
        offset = float(self._offset.value())
        sheet_height = float(self._height.value())

        if blocking:
            self._apply_result(
                self._pipeline.execute(self._paths, material, offset, sheet_height)
            )
            return

        self._set_busy(True)
        self._thread = QThread()
        self._worker = PipelineWorker(
            self._pipeline, list(self._paths), material, offset, sheet_height
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _set_busy(self, busy: bool) -> None:
        self._btn_generate.setEnabled(not busy)
        self._btn_add.setEnabled(not busy)

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)

    def _on_finished(self, result: ProductionResult) -> None:
        self._set_busy(False)
        self._apply_result(result)

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "PrintNest", f"Falha ao gerar producao:\n{message}")

    def _apply_result(self, result: ProductionResult) -> None:
        self._result = result
        self._draw_preview()
        self._btn_pdf.setEnabled(True)
        self._btn_dxf.setEnabled(True)
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        total = sum(layout.item_count for layout in result.sheets)
        self._status.setText(f"{len(result.sheets)} chapa(s) | {total} peca(s)")

    def _draw_preview(self) -> None:
        self._scene.clear()
        result = self._result
        if result is None:
            return
        by_id = {a.id: a for a in result.artworks}

        material_pen = QPen(QColor(40, 40, 40))
        material_pen.setCosmetic(True)
        piece_pen = QPen(QColor(0, 90, 180))
        piece_pen.setCosmetic(True)
        piece_brush = QBrush(QColor(120, 170, 220, 90))

        for index, layout in enumerate(result.sheets):
            dx = index * (layout.material.width + SHEET_GAP_MM)
            self._scene.addRect(
                dx, 0, layout.material.width, layout.used_length, material_pen
            )
            for item in layout.items:
                art = by_id.get(item.artwork_id)
                if art is None:
                    continue
                foot = art.cut_contour.size if art.has_cut else art.size
                self._scene.addRect(
                    dx + item.position.x, item.position.y, foot.width, foot.height,
                    piece_pen, piece_brush,
                )
        self._view.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def export_pdf(self, path: str | None = None) -> None:
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        if interactive:
            path, _ = QFileDialog.getSaveFileName(
                self, "Exportar PDF", str(Path(self._settings.last_dir) / "IMPRESSAO.pdf"),
                "PDF (*.pdf)",
            )
            if not path:
                return
        self._print_export.execute(
            self._result.sheets, self._result.artworks, self._result.sources, path
        )
        if interactive:
            QMessageBox.information(self, "PrintNest", f"PDF gerado:\n{path}")

    def export_dxf(self, path: str | None = None) -> None:
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        if interactive:
            path, _ = QFileDialog.getSaveFileName(
                self, "Exportar DXF", str(Path(self._settings.last_dir) / "CORTE.dxf"),
                "DXF (*.dxf)",
            )
            if not path:
                return
        sheet_width = self._result.sheets[0].material.width
        contours = positioned_cut_contours_sheets(
            self._result.sheets, self._result.artworks, sheet_width
        )
        self._dxf_export.execute(contours, path)
        if interactive:
            QMessageBox.information(self, "PrintNest", f"DXF gerado:\n{path}")
