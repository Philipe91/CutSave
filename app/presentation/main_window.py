from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QRect, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.application.footprint import artwork_footprint
from app.application.ports.page_renderer import IPageRenderer
from app.application.positioning import (
    SHEET_GAP_MM,
    mimaki_frame_contours,
    mimaki_marks,
    mimaki_marks_sheets,
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
from app.domain.geometry import Size
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


def _spin(minimum, maximum, decimals=None):
    box = QSpinBox() if decimals is None else QDoubleSpinBox()
    box.setRange(minimum, maximum)
    return box


class MainWindow(QMainWindow):
    """Tela unica do MVP PrintNest, organizada por categorias."""

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
        panel.addWidget(self._build_arquivo_group())
        panel.addWidget(self._build_chapa_group())
        panel.addWidget(self._build_faca_group())
        panel.addWidget(self._build_registro_group())

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

        panel_widget = QWidget()
        panel_widget.setLayout(panel)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel_widget)
        scroll.setMinimumWidth(320)

        self._scene = QGraphicsScene()
        self._view = ZoomableGraphicsView(self._scene)

        root.addWidget(scroll, 0)
        root.addWidget(self._view, 1)
        self.setCentralWidget(central)

    def _section(self, title: str, color: str) -> tuple[QFrame, QVBoxLayout]:
        """Faixa moderna recolhivel: clicar no cabecalho abre/fecha a secao."""
        box = QFrame()
        box.setObjectName("section")
        box.setStyleSheet(
            f"QFrame#section{{background:#fafafa; border:1px solid {color}; border-radius:6px;}}"
        )
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(6)

        header = QPushButton()
        header.setCheckable(True)
        header.setChecked(True)
        header.setCursor(Qt.PointingHandCursor)
        header.setStyleSheet(
            f"QPushButton{{background:{color}; color:white; font-weight:bold;"
            "letter-spacing:1px; text-align:left; padding:7px 12px; border:none;"
            "border-top-left-radius:5px; border-top-right-radius:5px;}}"
        )
        outer.addWidget(header)

        content_widget = QWidget()
        content = QVBoxLayout(content_widget)
        content.setContentsMargins(10, 0, 10, 0)
        outer.addWidget(content_widget)

        def _toggle() -> None:
            arrow = "▾" if header.isChecked() else "▸"  # ▾ / ▸
            header.setText(f"{arrow}  {title.upper()}")
            content_widget.setVisible(header.isChecked())

        header.toggled.connect(lambda _: _toggle())
        _toggle()
        return box, content

    def _build_arquivo_group(self) -> QFrame:
        group, lay = self._section("Arquivo", "#34495e")
        self._btn_add = QPushButton("Adicionar PDFs")
        self._btn_add.clicked.connect(lambda: self.add_pdfs())
        lay.addWidget(self._btn_add)
        self._list = QListWidget()
        lay.addWidget(self._list)
        self._btn_remove = QPushButton("Remover PDF selecionado")
        self._btn_remove.clicked.connect(lambda: self.remove_selected())
        lay.addWidget(self._btn_remove)
        lay.addWidget(QLabel("Rotacionar arquivo (graus)"))
        self._rotation = QComboBox()
        self._rotation.addItems(["0", "90", "180", "270"])
        self._rotation.currentIndexChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._rotation)
        return group

    def _build_chapa_group(self) -> QFrame:
        group, lay = self._section("Chapa / Material", "#16a085")
        lay.addWidget(QLabel("Largura da chapa (mm)"))
        self._width = _spin(1, 20000)
        self._width.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._width)
        lay.addWidget(QLabel("Altura da chapa (mm) - 0 = chapa unica"))
        self._height = _spin(0, 20000)
        self._height.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._height)
        lay.addWidget(QLabel("Espacamento (mm)"))
        self._spacing = _spin(0, 500, decimals=2)
        self._spacing.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._spacing)
        return group

    def _build_faca_group(self) -> QFrame:
        group, lay = self._section("Faca", "#c0392b")
        lay.addWidget(QLabel("Offset - sangria p/ fora (mm)"))
        self._offset = _spin(-100, 100, decimals=2)
        self._offset.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._offset)
        lay.addWidget(QLabel("Recuo de seguranca - faca p/ dentro (mm)"))
        self._safety = _spin(0, 100, decimals=2)
        self._safety.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._safety)
        lay.addWidget(QLabel("Recorte da arte - cortar bordas (mm)"))
        self._crop = _spin(0, 100, decimals=2)
        self._crop.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._crop)
        self._shared = QComboBox()
        self._shared.addItems(["Faca por peca (quadrados)", "Faca compartilhada (grade)"])
        self._shared.currentIndexChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._shared)
        return group

    def _build_registro_group(self) -> QFrame:
        group, lay = self._section("Marcas de registro", "#8e44ad")
        lay.addWidget(QLabel("Tipo de registro"))
        self._reg_type = QComboBox()
        self._reg_type.addItem("Nenhum", "none")
        self._reg_type.addItem("Bolinhas (5)", "circles")
        self._reg_type.addItem("Mimaki (marcas em L)", "mimaki")
        self._reg_type.currentIndexChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._reg_type)

        lay.addWidget(QLabel("Bolinhas: afastamento / diametro (mm)"))
        self._reg_margin = _spin(0, 200, decimals=1)
        lay.addWidget(self._reg_margin)
        self._reg_diameter = _spin(1, 50, decimals=1)
        lay.addWidget(self._reg_diameter)

        lay.addWidget(QLabel("Mimaki: distancia do quadro (mm)"))
        self._mk_distance = _spin(0, 200, decimals=1)
        self._mk_distance.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._mk_distance)
        lay.addWidget(QLabel("Mimaki: tamanho da marca (mm)"))
        self._mk_size = _spin(1, 100, decimals=1)
        self._mk_size.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._mk_size)
        lay.addWidget(QLabel("Mimaki: espessura da marca (mm)"))
        self._mk_thickness = _spin(0.1, 10, decimals=1)
        lay.addWidget(self._mk_thickness)
        return group

    # ---- settings ----
    def _load_settings(self) -> None:
        s = self._settings
        self._width.setValue(int(s.material_width))
        self._height.setValue(int(s.material_height))
        self._spacing.setValue(s.spacing)
        self._offset.setValue(s.offset)
        self._safety.setValue(s.safety_inset)
        self._crop.setValue(s.crop)
        self._rotation.setCurrentText(str(s.rotation))
        self._shared.setCurrentIndex(1 if s.shared_faca else 0)
        idx = max(0, self._reg_type.findData(s.reg_type))
        self._reg_type.setCurrentIndex(idx)
        self._reg_margin.setValue(s.reg_margin)
        self._reg_diameter.setValue(s.reg_diameter)
        self._mk_distance.setValue(s.mimaki_distance)
        self._mk_size.setValue(s.mimaki_size)
        self._mk_thickness.setValue(s.mimaki_thickness)

    def _save_settings(self) -> None:
        s = self._settings
        s.material_width = float(self._width.value())
        s.material_height = float(self._height.value())
        s.spacing = float(self._spacing.value())
        s.offset = float(self._offset.value())
        s.safety_inset = float(self._safety.value())
        s.crop = float(self._crop.value())
        s.rotation = self._rotation_value()
        s.shared_faca = self._shared.currentIndex() == 1
        s.reg_type = self._reg_type.currentData()
        s.reg_margin = float(self._reg_margin.value())
        s.reg_diameter = float(self._reg_diameter.value())
        s.mimaki_distance = float(self._mk_distance.value())
        s.mimaki_size = float(self._mk_size.value())
        s.mimaki_thickness = float(self._mk_thickness.value())
        self._store.save(s)

    # ---- helpers de leitura ----
    def _rotation_value(self) -> int:
        return int(self._rotation.currentText())

    def _reg(self) -> str:
        return self._reg_type.currentData()

    def _effective_offset(self) -> float:
        return float(self._offset.value()) - float(self._safety.value())

    def _transform(self, art):
        """Aplica recorte (bordas) e rotacao a uma arte (tamanho)."""
        crop = float(self._crop.value())
        width = art.size.width - 2 * crop
        height = art.size.height - 2 * crop
        if self._rotation_value() in (90, 270):
            width, height = height, width
        return replace(art, size=Size(width, height), cut_contour=None)

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
            name="MVP", width=float(self._width.value()), spacing=float(self._spacing.value())
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
            artworks = [
                self._faca_uc.execute(self._transform(a), offset)
                for a in self._base_artworks
            ]
        except ValidationError:
            self._status.setText("Recorte/recuo grande demais para a peca.")
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
        mark_pen = QPen(QColor(0, 90, 180))
        mark_pen.setCosmetic(True)
        mark_brush = QBrush(QColor(0, 90, 180))
        empty_brush = QBrush(QColor(200, 200, 200, 120))

        shared = self._shared.currentIndex() == 1
        reg = self._reg()
        crop = float(self._crop.value())
        rotation = self._rotation_value()
        cropped_cache: dict = {}

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
                base_x = dx + item.position.x - fp.min_x
                base_y = item.position.y - fp.min_y

                key = self._sources.get(item.artwork_id)
                pixmap = self._pixmaps.get(key)
                if pixmap is not None and not pixmap.isNull() and pixmap.width() > 0:
                    display = self._display_pixmap(
                        pixmap, crop, rotation, art.size, cropped_cache, key
                    )
                    pm_item = self._scene.addPixmap(display)
                    pm_item.setScale(art.size.width / display.width())
                    pm_item.setPos(base_x, base_y)
                else:
                    self._scene.addRect(
                        base_x, base_y, art.size.width, art.size.height,
                        material_pen, empty_brush,
                    )
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
            self._draw_marks(layout, result.artworks, dx, reg, mark_pen, mark_brush, faca_pen)
        self._view.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def _draw_marks(self, layout, artworks, dx, reg, mark_pen, mark_brush, faca_pen) -> None:
        if reg == "circles":
            for mark in registration_marks(
                layout, artworks,
                margin_mm=float(self._reg_margin.value()),
                diameter_mm=float(self._reg_diameter.value()),
            ):
                self._scene.addEllipse(
                    dx + mark.center.x - mark.radius, mark.center.y - mark.radius,
                    mark.diameter, mark.diameter, mark_pen, mark_brush,
                )
        elif reg == "mimaki":
            marks = mimaki_marks(
                layout, artworks,
                distance_mm=float(self._mk_distance.value()),
                mark_size_mm=float(self._mk_size.value()),
            )
            if marks is None:
                return
            f = marks.frame
            self._scene.addRect(
                dx + f.min_x, f.min_y, f.max_x - f.min_x, f.max_y - f.min_y, faca_pen
            )
            for seg in marks.segments:
                self._scene.addLine(
                    dx + seg.start.x, seg.start.y, dx + seg.end.x, seg.end.y, mark_pen
                )

    @staticmethod
    def _display_pixmap(pixmap, crop, rotation, art_size, cache, key):
        """Recorta e rotaciona o pixmap para o preview (cache por origem)."""
        cache_key = (key, rotation)
        if crop <= 0 and rotation == 0:
            return pixmap
        if cache_key in cache:
            return cache[cache_key]
        out = pixmap
        if crop > 0:
            # antes da rotacao art_size pode estar trocado; reconstroi original
            unrotated_w = art_size.width if rotation in (0, 180) else art_size.height
            orig_w = unrotated_w + 2 * crop
            fx = crop / orig_w
            x = round(pixmap.width() * fx)
            y = round(pixmap.height() * fx)
            w = pixmap.width() - 2 * x
            h = pixmap.height() - 2 * y
            if w > 0 and h > 0:
                out = pixmap.copy(QRect(x, y, w, h))
        if rotation:
            out = out.transformed(QTransform().rotate(rotation))
        cache[cache_key] = out
        return out

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
            reg_type=self._reg(),
            reg_margin_mm=float(self._reg_margin.value()),
            reg_diameter_mm=float(self._reg_diameter.value()),
            mimaki_distance_mm=float(self._mk_distance.value()),
            mimaki_size_mm=float(self._mk_size.value()),
            mimaki_thickness_mm=float(self._mk_thickness.value()),
            crop_mm=float(self._crop.value()),
            rotate=self._rotation_value(),
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
        reg = self._reg()

        if self._shared.currentIndex() == 1:
            contours = []
            segments = shared_cut_segments_sheets(sheets, artworks, sheet_width)
        else:
            contours = positioned_cut_contours_sheets(sheets, artworks, sheet_width)
            segments = []

        marks = []
        mark_segments = []
        if reg == "circles":
            marks = registration_marks_sheets(
                sheets, artworks, sheet_width,
                margin_mm=float(self._reg_margin.value()),
                diameter_mm=float(self._reg_diameter.value()),
            )
        elif reg == "mimaki":
            mk_list = mimaki_marks_sheets(
                sheets, artworks, sheet_width,
                distance_mm=float(self._mk_distance.value()),
                mark_size_mm=float(self._mk_size.value()),
            )
            contours = list(contours) + mimaki_frame_contours(mk_list)
            for mk in mk_list:
                mark_segments.extend(mk.segments)

        self._dxf_export.execute(
            contours, path, segments=segments, marks=marks, mark_segments=mark_segments
        )
        if interactive:
            QMessageBox.information(self, "PrintNest", f"DXF gerado:\n{path}")
