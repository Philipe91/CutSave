from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
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

from app.application.footprint import artwork_footprint
from app.application.ports.page_renderer import IPageRenderer
from app.application.positioning import (
    SHEET_GAP_MM,
    positioned_cut_contours_sheets,
    registration_marks,
    registration_marks_sheets,
    shared_cut_segments,
    shared_cut_segments_sheets,
)
from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase
from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
from app.application.use_cases.run_production_pipeline import (
    ProductionResult,
    RunProductionPipelineUseCase,
)
from app.domain.model.material import Material
from app.shared.config.settings import AppSettings, SettingsStore
from app.shared.errors import ValidationError


class ZoomableGraphicsView(QGraphicsView):
    """Preview com zoom (roda do mouse) e arrastar (segurar e mover)."""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class ProductionWorker(QObject):
    """Importa + monta producao e rasteriza as paginas, fora da thread da UI."""

    progress = Signal(int, int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, pipeline, renderer, paths, material, offset, sheet_height):
        super().__init__()
        self._pipeline = pipeline
        self._renderer = renderer
        self._paths = paths
        self._material = material
        self._offset = offset
        self._sheet_height = sheet_height

    def run(self) -> None:
        try:
            result = self._pipeline.execute(
                self._paths, self._material, self._offset, self._sheet_height,
                on_progress=lambda done, total: self.progress.emit(done, total),
            )
            unique = sorted(set(result.sources.values()))
            png_map = {}
            for index, (path, page) in enumerate(unique, start=1):
                png_map[(path, page)] = self._renderer.render_png(path, page)
                self.progress.emit(index, len(unique))
        except Exception as exc:  # reportado a UI
            self.failed.emit(str(exc))
            return
        self.finished.emit((result, png_map))


class MainWindow(QMainWindow):
    """Tela unica do MVP PrintNest, com preview da arte + faca."""

    def __init__(
        self,
        pipeline: RunProductionPipelineUseCase,
        print_export: ExportPrintPdfUseCase,
        dxf_export: ExportDxfUseCase,
        renderer: IPageRenderer,
        settings_store: SettingsStore,
        settings: AppSettings,
    ) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._print_export = print_export
        self._dxf_export = dxf_export
        self._renderer = renderer
        self._store = settings_store
        self._settings = settings

        self._faca_uc = GenerateRectangularCutUseCase()
        self._nesting_uc = RunGridNestingUseCase()

        self._paths: list[str] = []
        self._base_artworks: list = []
        self._sources: dict[str, tuple[str, int]] = {}
        self._pixmaps: dict[tuple[str, int], QPixmap] = {}
        self._loaded = False
        self._result: ProductionResult | None = None
        self._thread: QThread | None = None
        self._worker: ProductionWorker | None = None

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

        self._btn_remove = QPushButton("Remover PDF selecionado")
        self._btn_remove.clicked.connect(lambda: self.remove_selected())
        panel.addWidget(self._btn_remove)

        panel.addWidget(QLabel("Largura da chapa (mm)"))
        self._width = QSpinBox()
        self._width.setRange(1, 20000)
        self._width.valueChanged.connect(lambda _: self._relayout())
        panel.addWidget(self._width)

        panel.addWidget(QLabel("Altura da chapa (mm) - 0 = chapa unica"))
        self._height = QSpinBox()
        self._height.setRange(0, 20000)
        self._height.valueChanged.connect(lambda _: self._relayout())
        panel.addWidget(self._height)

        panel.addWidget(QLabel("Espacamento (mm)"))
        self._spacing = QDoubleSpinBox()
        self._spacing.setRange(0, 500)
        self._spacing.valueChanged.connect(lambda _: self._relayout())
        panel.addWidget(self._spacing)

        panel.addWidget(QLabel("Offset da faca - sangria p/ fora (mm)"))
        self._offset = QDoubleSpinBox()
        self._offset.setRange(-100, 100)
        self._offset.valueChanged.connect(lambda _: self._relayout())
        panel.addWidget(self._offset)

        panel.addWidget(QLabel("Recuo de seguranca - faca p/ dentro (mm)"))
        self._safety = QDoubleSpinBox()
        self._safety.setRange(0, 100)
        self._safety.valueChanged.connect(lambda _: self._relayout())
        panel.addWidget(self._safety)

        self._shared = QCheckBox("Faca compartilhada (grade fora a fora)")
        self._shared.toggled.connect(lambda _: self._relayout())
        panel.addWidget(self._shared)

        self._regmarks = QCheckBox("Marcas de registro (5 bolinhas)")
        self._regmarks.toggled.connect(lambda _: self._relayout())
        panel.addWidget(self._regmarks)

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
        self._safety.setValue(self._settings.safety_inset)
        self._shared.setChecked(self._settings.shared_faca)
        self._regmarks.setChecked(self._settings.reg_marks)

    def _save_settings(self) -> None:
        self._settings.material_width = float(self._width.value())
        self._settings.material_height = float(self._height.value())
        self._settings.spacing = float(self._spacing.value())
        self._settings.offset = float(self._offset.value())
        self._settings.safety_inset = float(self._safety.value())
        self._settings.shared_faca = self._shared.isChecked()
        self._settings.reg_marks = self._regmarks.isChecked()
        self._store.save(self._settings)

    def _effective_offset(self) -> float:
        """Sangria (p/ fora) menos recuo de seguranca (p/ dentro)."""
        return float(self._offset.value()) - float(self._safety.value())

    # ---- lista de arquivos ----
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

    def remove_selected(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        self._list.takeItem(row)
        del self._paths[row]

    # ---- producao ----
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
        offset = self._effective_offset()
        sheet_height = float(self._height.value())

        if blocking:
            result = self._pipeline.execute(self._paths, material, offset, sheet_height)
            unique = sorted(set(result.sources.values()))
            png_map = {key: self._renderer.render_png(*key) for key in unique}
            self._load_production(result, png_map)
            return

        self._set_busy(True)
        self._thread = QThread()
        self._worker = ProductionWorker(
            self._pipeline, self._renderer, list(self._paths), material, offset, sheet_height
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

    def _on_finished(self, bundle) -> None:
        self._set_busy(False)
        result, png_map = bundle
        self._load_production(result, png_map)

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "PrintNest", f"Falha ao gerar producao:\n{message}")

    def _load_production(self, result: ProductionResult, png_map: dict) -> None:
        self._base_artworks = result.artworks
        self._sources = result.sources
        self._pixmaps = {}
        by_bytes: dict[bytes, QPixmap] = {}
        for key, data in png_map.items():
            pixmap = by_bytes.get(data)
            if pixmap is None:
                pixmap = QPixmap()
                pixmap.loadFromData(data, "PNG")
                by_bytes[data] = pixmap
            self._pixmaps[key] = pixmap
        self._loaded = True
        self._btn_pdf.setEnabled(True)
        self._btn_dxf.setEnabled(True)
        self._relayout()

    def _relayout(self) -> None:
        """Recalcula faca + nesting com os parametros atuais (tempo real)."""
        if not self._loaded:
            return
        offset = self._effective_offset()
        material = self._material()
        sheet_height = float(self._height.value())
        try:
            artworks = [self._faca_uc.execute(art, offset) for art in self._base_artworks]
        except ValidationError:
            self._status.setText("Recuo de seguranca grande demais para a peca.")
            return
        sheets = self._nesting_uc.execute_sheets(artworks, material, sheet_height)
        self._result = ProductionResult(sheets=sheets, artworks=artworks, sources=self._sources)
        self._draw_preview()
        total = sum(s.item_count for s in sheets)
        self._status.setText(f"{len(sheets)} chapa(s) | {total} peca(s)")

    def _draw_preview(self) -> None:
        self._scene.clear()
        result = self._result
        if result is None:
            return
        by_id = {a.id: a for a in result.artworks}

        material_pen = QPen(QColor(40, 40, 40))
        material_pen.setCosmetic(True)
        faca_pen = QPen(QColor(220, 0, 0))
        faca_pen.setCosmetic(True)
        mark_brush = QBrush(QColor(0, 0, 0))
        empty_brush = QBrush(QColor(200, 200, 200, 120))

        shared = self._shared.isChecked()
        regmarks = self._regmarks.isChecked()

        for index, layout in enumerate(result.sheets):
            dx = index * (layout.material.width + SHEET_GAP_MM)
            self._scene.addRect(
                dx, 0, layout.material.width, layout.used_length, material_pen
            )
            for item in layout.items:
                art = by_id.get(item.artwork_id)
                if art is None:
                    continue
                fp = artwork_footprint(art)
                # canto da arte (art-local 0,0) na chapa
                base_x = dx + item.position.x - fp.min_x
                base_y = item.position.y - fp.min_y

                pixmap = self._pixmaps.get(self._sources.get(item.artwork_id))
                if pixmap is not None and not pixmap.isNull() and pixmap.width() > 0:
                    pm_item = self._scene.addPixmap(pixmap)
                    pm_item.setScale(art.size.width / pixmap.width())
                    pm_item.setPos(base_x, base_y)
                else:
                    self._scene.addRect(
                        base_x, base_y, art.size.width, art.size.height,
                        material_pen, empty_brush,
                    )
                # faca de quadrados (vermelho) por cima, na posicao real da peca
                if art.has_cut and not shared:
                    faca = art.cut_contour
                    self._scene.addRect(
                        base_x + faca.origin.x, base_y + faca.origin.y,
                        faca.size.width, faca.size.height, faca_pen,
                    )

            if shared:
                for seg in shared_cut_segments(layout, result.artworks):
                    self._scene.addLine(
                        dx + seg.start.x, seg.start.y, dx + seg.end.x, seg.end.y, faca_pen
                    )
            if regmarks:
                marks = registration_marks(
                    layout, result.artworks,
                    margin_mm=self._settings.reg_margin,
                    diameter_mm=self._settings.reg_diameter,
                )
                for mark in marks:
                    self._scene.addEllipse(
                        dx + mark.center.x - mark.radius, mark.center.y - mark.radius,
                        mark.diameter, mark.diameter, faca_pen, mark_brush,
                    )
        self._view.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    # ---- exportacao ----
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
            self._result.sheets, self._result.artworks, self._result.sources, path,
            reg_marks=self._regmarks.isChecked(),
            reg_margin_mm=self._settings.reg_margin,
            reg_diameter_mm=self._settings.reg_diameter,
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
        sheets = self._result.sheets
        artworks = self._result.artworks
        sheet_width = sheets[0].material.width

        if self._shared.isChecked():
            contours = []
            segments = shared_cut_segments_sheets(sheets, artworks, sheet_width)
        else:
            contours = positioned_cut_contours_sheets(sheets, artworks, sheet_width)
            segments = []
        marks = (
            registration_marks_sheets(
                sheets, artworks, sheet_width,
                margin_mm=self._settings.reg_margin,
                diameter_mm=self._settings.reg_diameter,
            )
            if self._regmarks.isChecked()
            else []
        )
        self._dxf_export.execute(contours, path, segments=segments, marks=marks)
        if interactive:
            QMessageBox.information(self, "PrintNest", f"DXF gerado:\n{path}")
