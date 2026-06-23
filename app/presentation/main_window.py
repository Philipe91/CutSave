from __future__ import annotations

import contextlib
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRect, Qt, QThread, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QTransform,
    QUndoCommand,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
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
from app.application.project_io import (
    PROJECT_EXTENSION,
    PROJECT_SETTING_KEYS,
    ProjectDocument,
    ProjectFile,
    ProjectStore,
)
from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase
from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
from app.application.use_cases.run_production_pipeline import (
    ProductionResult,
    RunProductionPipelineUseCase,
)
from app.domain.cut.contour_ops import offset_contour
from app.domain.geometry import Point2D, Size
from app.domain.model.image_artwork import ImageArtwork
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.shared.config.settings import AppSettings, SettingsStore
from app.shared.errors import ProjectError, ValidationError

IMAGE_FILE_FILTER = (
    "Arquivos suportados (*.pdf *.png *.jpg *.jpeg *.webp);;"
    "PDF (*.pdf);;Imagens (*.png *.jpg *.jpeg *.webp)"
)

RULER_SIZE = 24

# Empurrar com as setas (nudge), estilo CorelDRAW: normal, micro (Ctrl), super (Shift).
NUDGE_MM = 1.0
NUDGE_MICRO_MM = 0.1
NUDGE_SUPER_MM = 10.0
SNAP_THRESHOLD_MM = 2.0  # distancia (mm) para o encaixe "grudar"


class SnapConfig:
    """Estado compartilhado do encaixe (snap) ao arrastar pecas."""

    def __init__(self, enabled: bool = True, threshold_mm: float = SNAP_THRESHOLD_MM) -> None:
        self.enabled = enabled
        self.threshold_mm = threshold_mm
        self.dragging = False  # snap so age durante o arraste com o mouse


class ZoomableGraphicsView(QGraphicsView):
    """Preview estilo CorelDRAW: zoom (roda), pan (arrastar), fundo cinza."""

    view_changed = Signal()
    drag_started = Signal()
    drag_finished = Signal()
    nudge = Signal(float, float)  # deslocamento (dx, dy) em mm, via setas

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        # esquerdo: seleciona item / move; em area vazia faz laco de selecao.
        # meio faz pan; roda da zoom.
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor(170, 170, 170))  # mesa cinza
        self._panning = False
        self._pan_last = None
        self._left_drag = False

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        self.view_changed.emit()

    def keyPressEvent(self, event) -> None:
        deltas = {
            Qt.Key_Left: (-1.0, 0.0),
            Qt.Key_Right: (1.0, 0.0),
            Qt.Key_Up: (0.0, -1.0),
            Qt.Key_Down: (0.0, 1.0),
        }
        unit = deltas.get(event.key())
        if unit is not None:
            mods = event.modifiers()
            if mods & Qt.ControlModifier:
                step = NUDGE_MICRO_MM
            elif mods & Qt.ShiftModifier:
                step = NUDGE_SUPER_MM
            else:
                step = NUDGE_MM
            self.nudge.emit(unit[0] * step, unit[1] * step)
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_last = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item is not None:
                self.setDragMode(QGraphicsView.NoDrag)
                self._left_drag = True
                self.drag_started.emit()
            else:
                self.setDragMode(QGraphicsView.RubberBandDrag)
                self._left_drag = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning and self._pan_last is not None:
            delta = event.position() - self._pan_last
            self._pan_last = event.position()
            hbar, vbar = self.horizontalScrollBar(), self.verticalScrollBar()
            hbar.setValue(hbar.value() - int(delta.x()))
            vbar.setValue(vbar.value() - int(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton and self._left_drag:
            self._left_drag = False
            self.drag_finished.emit()


class MoveCommand(QUndoCommand):
    """Desfazer/refazer de movimento de pecas/grupos na area de trabalho."""

    def __init__(self, moves) -> None:
        super().__init__("mover")
        self._moves = moves  # lista de (item, pos_antiga, pos_nova)

    def undo(self) -> None:
        for item, old, _ in self._moves:
            item.setPos(old)

    def redo(self) -> None:
        for item, _, new in self._moves:
            item.setPos(new)

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self.view_changed.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.view_changed.emit()


class PieceItem(QGraphicsRectItem):
    """Peca na area de trabalho: selecionavel e movel (arte + faca como filhos)."""

    def __init__(self, width, height, *, artwork_id, name, art_size, sheet_index, dx, dy):
        super().__init__(0.0, 0.0, width, height)
        self.artwork_id = artwork_id
        self.piece_name = name
        self.art_size = art_size
        self.sheet_index = sheet_index
        self.dx = dx
        self.dy = dy
        self.snap: SnapConfig | None = None
        self.sheet_rect: tuple[float, float, float, float] | None = None
        self.setPen(QPen(Qt.NoPen))

    @staticmethod
    def _snap_axis(start: float, size: float, lines, threshold: float) -> float:
        """Encaixa a borda esquerda/direita/centro na linha mais proxima (mm)."""
        best, best_dist = start, threshold
        for anchor in (start, start + size, start + size / 2.0):
            offset = anchor - start
            for line in lines:
                dist = abs(anchor - line)
                if dist < best_dist:
                    best_dist = dist
                    best = line - offset
        return best

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.snap is not None
            and self.snap.enabled
            and self.snap.dragging
            and self.scene() is not None
        ):
            value = self._snapped(value)
        return super().itemChange(change, value)

    def _snapped(self, pos: QPointF) -> QPointF:
        rect = self.rect()
        width, height = rect.width(), rect.height()
        xlines: list[float] = []
        ylines: list[float] = []
        if self.sheet_rect is not None:
            sx, sy, sw, sl = self.sheet_rect
            xlines += [sx, sx + sw]
            ylines += [sy, sy + sl]
        for other in self.scene().items():
            if other is self or not isinstance(other, PieceItem) or other.isSelected():
                continue
            r = other.sceneBoundingRect()
            xlines += [r.left(), r.right(), r.center().x()]
            ylines += [r.top(), r.bottom(), r.center().y()]
        th = self.snap.threshold_mm
        nx = self._snap_axis(pos.x(), width, xlines, th)
        ny = self._snap_axis(pos.y(), height, ylines, th)
        return QPointF(nx, ny)


class Ruler(QWidget):
    """Regua (mm) sincronizada com o view, no estilo de softwares de pre-impressao."""

    def __init__(self, view: ZoomableGraphicsView, horizontal: bool) -> None:
        super().__init__()
        self._view = view
        self._h = horizontal
        if horizontal:
            self.setFixedHeight(RULER_SIZE)
        else:
            self.setFixedWidth(RULER_SIZE)

    @staticmethod
    def _nice_step(px_per_mm: float) -> float:
        raw = 60.0 / px_per_mm  # alvo ~60px entre marcas
        for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000):
            if step >= raw:
                return float(step)
        return 10000.0

    def paintEvent(self, event) -> None:  # noqa: ARG002
        import math

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(245, 245, 245))
        painter.setPen(QColor(110, 110, 110))

        view = self._view
        vp = view.viewport()
        if self._h:
            length = vp.width()
            lo = view.mapToScene(0, 0).x()
            hi = view.mapToScene(length, 0).x()
        else:
            length = vp.height()
            lo = view.mapToScene(0, 0).y()
            hi = view.mapToScene(0, length).y()
        span = hi - lo
        if length <= 0 or span <= 0:
            return

        step = self._nice_step(length / span)
        value = math.floor(lo / step) * step
        while value <= hi:
            if self._h:
                pos = view.mapFromScene(QPointF(value, 0.0)).x()
                painter.drawLine(pos, RULER_SIZE - 6, pos, RULER_SIZE)
                painter.drawText(pos + 2, RULER_SIZE - 8, f"{value:.0f}")
            else:
                pos = view.mapFromScene(QPointF(0.0, value)).y()
                painter.drawLine(RULER_SIZE - 6, pos, RULER_SIZE, pos)
                painter.save()
                painter.translate(RULER_SIZE - 9, pos - 2)
                painter.rotate(-90)
                painter.drawText(0, 0, f"{value:.0f}")
                painter.restore()
            value += step


class ProductionWorker(QObject):
    """Importa + monta producao e rasteriza as paginas, fora da thread da UI."""

    progress = Signal(int, int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, pipeline, renderer, paths, material, offset, sheet_height, box,
                 sensitivity=50.0, ignore_white=True):
        super().__init__()
        self._pipeline = pipeline
        self._renderer = renderer
        self._paths = paths
        self._material = material
        self._offset = offset
        self._sheet_height = sheet_height
        self._box = box
        self._sensitivity = sensitivity
        self._ignore_white = ignore_white

    def run(self) -> None:
        try:
            result = self._pipeline.execute(
                self._paths, self._material, self._offset, self._sheet_height, self._box,
                on_progress=lambda done, total: self.progress.emit(done, total),
                sensitivity=self._sensitivity, ignore_white=self._ignore_white,
            )
            unique = sorted(set(result.sources.values()))
            png_map = {}
            for index, (path, page) in enumerate(unique, start=1):
                png_map[(path, page)] = self._renderer.render_png(path, page, box=self._box)
                self.progress.emit(index, len(unique))
        except Exception as exc:  # reportado a UI
            self.failed.emit(str(exc))
            return
        self.finished.emit((result, png_map))


def _spin(minimum, maximum, decimals=None):
    box = QSpinBox() if decimals is None else QDoubleSpinBox()
    box.setRange(minimum, maximum)
    return box


class QuantityStepper(QWidget):
    """Seletor de quantidade moderno: botoes - / + ladeando o numero centralizado.

    Expoe value()/setValue()/valueChanged como um QSpinBox para o restante do
    codigo (e os testes) usarem sem saber que e um widget composto.
    """

    valueChanged = Signal(int)

    def __init__(self, minimum: int = 1, maximum: int = 100000, value: int = 1) -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._minus = QPushButton("−")  # minus sign
        self._minus.setObjectName("qtyMinus")
        self._spin = QSpinBox()
        self._spin.setRange(minimum, maximum)
        self._spin.setValue(value)
        self._spin.setButtonSymbols(QSpinBox.NoButtons)
        self._spin.setAlignment(Qt.AlignCenter)
        self._plus = QPushButton("+")
        self._plus.setObjectName("qtyPlus")
        for btn in (self._minus, self._plus):
            btn.setFixedWidth(24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setAutoRepeat(True)
        lay.addWidget(self._minus)
        lay.addWidget(self._spin, 1)
        lay.addWidget(self._plus)
        self._minus.clicked.connect(lambda: self._spin.stepBy(-1))
        self._plus.clicked.connect(lambda: self._spin.stepBy(1))
        self._spin.valueChanged.connect(self.valueChanged)
        self.setStyleSheet(
            "QuantityStepper{background:white; border:1px solid #cfd6dd; border-radius:6px;}"
            "QSpinBox{border:none; background:transparent; font-weight:bold;"
            " font-size:13px; color:#2c3e50;}"
            "QPushButton{border:none; background:#34495e; color:white; font-weight:bold;"
            " font-size:15px; padding:3px 0;}"
            "QPushButton:hover{background:#41617d;}"
            "QPushButton:pressed{background:#2c3e50;}"
            "QPushButton#qtyMinus{border-top-left-radius:5px; border-bottom-left-radius:5px;}"
            "QPushButton#qtyPlus{border-top-right-radius:5px; border-bottom-right-radius:5px;}"
        )

    def value(self) -> int:
        return self._spin.value()

    def setValue(self, value: int) -> None:
        self._spin.setValue(value)


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
        self._origins: dict[str, str] = {}  # id da arte -> caminho original (quantidade)
        self._pixmaps: dict[tuple[str, int], QPixmap] = {}
        self._loaded = False
        self._result: ProductionResult | None = None
        self._thread: QThread | None = None
        self._worker: ProductionWorker | None = None
        self._piece_items: list = []
        self._undo = QUndoStack(self)
        self._move_snapshot: dict = {}
        self._fit_next = True  # ajusta o zoom so apos gerar; preserva no relayout
        self._snap = SnapConfig()
        self._project_store = ProjectStore()
        self._project_path: str | None = None

        self.setWindowTitle("PrintNest MVP")
        self._build_ui()
        self._load_settings()
        self._build_menu_toolbar()
        self._update_title()
        self._maybe_reopen_last()

    def _act(self, text, slot, shortcut=None, tip=None) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(lambda *_: slot())
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if tip:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        return action

    def _build_menu_toolbar(self) -> None:
        novo = self._act("Novo Projeto", self.new_project, "Ctrl+N",
                         "Comeca um projeto vazio")
        abrir = self._act("Abrir Projeto...", self.open_project, "Ctrl+Shift+O",
                          "Abre um projeto .printnest salvo")
        salvar = self._act("Salvar Projeto", self.save_project, "Ctrl+S",
                           "Salva o projeto atual")
        salvar_como = self._act("Salvar Como...", self.save_project_as, "Ctrl+Shift+S",
                                "Salva o projeto em um novo arquivo")
        add = self._act("Adicionar PDFs...", self.add_pdfs, "Ctrl+O",
                        "Adiciona arquivos PDF a lista")
        substituir = self._act("Substituir arquivo selecionado...", self.replace_selected, None,
                               "Troca o arquivo da linha selecionada (ex.: arquivo nao encontrado)")
        gerar = self._act("Gerar Producao", self.generate, "F5",
                          "Importa, gera a faca e organiza o nesting")
        fit = self._act("Ajustar a tela", self._fit_view, "Ctrl+0",
                        "Enquadra todo o trabalho na tela")
        undo = self._act("Desfazer", self._undo.undo, "Ctrl+Z", "Desfaz o ultimo movimento")
        redo = self._act("Refazer", self._undo.redo, "Ctrl+Y", "Refaz o movimento")
        grp = self._act("Agrupar", self._group_selected, "Ctrl+G",
                        "Agrupa as pecas selecionadas")
        ungrp = self._act("Desagrupar", self._ungroup_selected, "Ctrl+Shift+G",
                          "Desagrupa as pecas")
        sel_all = self._act("Selecionar tudo", self._select_all, "Ctrl+A",
                            "Seleciona todas as pecas na area de trabalho")
        excluir = self._act("Excluir selecionado", self._delete_selected, "Del",
                            "Exclui as pecas selecionadas do arranjo")
        reset = self._act("Resetar arranjo", self._reset_arrangement, None,
                          "Refaz o nesting do zero (descarta ajustes manuais)")
        rem = self._act("Remover PDF selecionado", self.remove_selected, None,
                        "Remove o PDF selecionado da lista")
        dup = self._act("Duplicar", self._duplicate_selected, "Ctrl+D",
                        "Duplica as pecas selecionadas com um pequeno deslocamento")
        step = self._act("Repetir em grade...", self._step_repeat_dialog, "Ctrl+Shift+D",
                         "Cria varias copias em linhas e colunas (step and repeat)")
        al_l = self._act("Alinhar a esquerda", lambda: self._align("left"), None,
                         "Alinha as bordas esquerdas das pecas selecionadas")
        al_r = self._act("Alinhar a direita", lambda: self._align("right"), None,
                         "Alinha as bordas direitas")
        al_t = self._act("Alinhar ao topo", lambda: self._align("top"), None,
                         "Alinha as bordas superiores")
        al_b = self._act("Alinhar a base", lambda: self._align("bottom"), None,
                         "Alinha as bordas inferiores")
        al_cx = self._act("Centralizar na vertical", lambda: self._align("hcenter"), None,
                          "Alinha os centros numa mesma linha vertical")
        al_cy = self._act("Centralizar na horizontal", lambda: self._align("vcenter"), None,
                          "Alinha os centros numa mesma linha horizontal")
        dist_h = self._act("Distribuir na horizontal", lambda: self._distribute("h"), None,
                           "Espaca as pecas igualmente na horizontal")
        dist_v = self._act("Distribuir na vertical", lambda: self._distribute("v"), None,
                           "Espaca as pecas igualmente na vertical")
        snap_act = QAction("Encaixar (snap)", self)
        snap_act.setCheckable(True)
        snap_act.setChecked(self._snap.enabled)
        snap_act.setShortcut(QKeySequence("Alt+Q"))
        snap_act.setToolTip("Liga/desliga o encaixe ao arrastar pecas")
        snap_act.toggled.connect(self._set_snap)
        self._snap_action = snap_act
        exp_pdf = self._act("Exportar PDF de impressao...", self.export_pdf, None,
                            "Gera o PDF de impressao")
        exp_dxf = self._act("Exportar DXF (unico)...", self.export_dxf, None,
                            "Gera um DXF com todas as chapas")
        exp_dxf_n = self._act("Exportar DXF por chapa...", self.export_dxf_per_sheet, None,
                              "Gera um arquivo DXF para cada chapa")
        exp_img = self._act("Exportar Imagem (PNG/JPEG)...", self.export_image, None,
                            "Rasteriza a impressao em imagem, no DPI escolhido")
        sair = self._act("Sair", self.close, None, "Fecha o programa")
        sobre = self._act("Sobre", self._show_about, None, "Sobre o PrintNest")

        bar = self.menuBar()
        m_arq = bar.addMenu("&Arquivo")
        for action in (novo, abrir, salvar, salvar_como,
                       None, add, substituir,
                       None, exp_pdf, exp_dxf, exp_dxf_n, exp_img,
                       None, sair):
            m_arq.addSeparator() if action is None else m_arq.addAction(action)
        m_edit = bar.addMenu("&Editar")
        for action in (undo, redo, None, sel_all, dup, step, grp, ungrp,
                       None, excluir, reset, rem):
            m_edit.addSeparator() if action is None else m_edit.addAction(action)
        m_org = bar.addMenu("&Organizar")
        for action in (al_l, al_r, al_t, al_b, al_cx, al_cy,
                       None, dist_h, dist_v, None, snap_act):
            m_org.addSeparator() if action is None else m_org.addAction(action)
        m_exib = bar.addMenu("E&xibir")
        m_exib.addAction(fit)
        m_ferr = bar.addMenu("&Ferramentas")
        m_ferr.addAction(gerar)
        bar.addMenu("A&juda").addAction(sobre)

        toolbar = self.addToolBar("Principal")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        for action in (add, gerar, reset, fit, None, undo, redo,
                       sel_all, dup, grp, ungrp, excluir,
                       None, exp_pdf, exp_dxf, exp_dxf_n, exp_img):
            toolbar.addSeparator() if action is None else toolbar.addAction(action)

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "PrintNest",
            "PrintNest - preparacao de producao grafica.\nV1.1 (prototipo).",
        )

    # ---- projeto (.printnest) ----
    def _update_title(self) -> None:
        name = Path(self._project_path).name if self._project_path else "Sem titulo"
        self.setWindowTitle(f"PrintNest - {name}")

    def _collect_project(self) -> ProjectDocument:
        """Captura o estado atual (arquivos + parametros) como ProjectDocument."""
        self._save_settings()  # sincroniza os widgets -> self._settings
        quantities = self._quantities()
        rotation = self._rotation_value()
        files = [
            ProjectFile(path=path, quantity=quantities.get(path, 1), rotation=rotation)
            for path in self._paths
        ]
        settings = {key: getattr(self._settings, key) for key in PROJECT_SETTING_KEYS}
        return ProjectDocument(files=files, settings=settings)

    def _apply_project(self, doc: ProjectDocument) -> None:
        """Restaura o estado do projeto SEM gerar producao (regra do projeto)."""
        for key, value in doc.settings.items():
            if key in PROJECT_SETTING_KEYS and hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self._load_settings()  # empurra os parametros para os widgets
        self._reset_project_state()
        self._populate_files(doc.files)

    def _reset_project_state(self) -> None:
        """Descarta a producao carregada (mantem parametros e widgets)."""
        self._loaded = False
        self._result = None
        self._base_artworks = []
        self._sources = {}
        self._pixmaps = {}
        self._piece_items = []
        self._scene.clear()
        self._undo.clear()
        self._btn_pdf.setEnabled(False)
        self._btn_dxf.setEnabled(False)
        self._btn_img.setEnabled(False)
        self._status.setText("")

    def _populate_files(self, files: list[ProjectFile]) -> None:
        """Recria a tabela de arquivos a partir do projeto, marcando os ausentes."""
        self._table.setRowCount(0)
        self._paths = []
        for pfile in files:
            self.add_paths([pfile.path])
            row = self._table.rowCount() - 1
            spin = self._table.cellWidget(row, 1)
            if spin is not None:
                spin.setValue(max(1, int(pfile.quantity)))
            if not Path(pfile.path).exists():
                self._mark_missing(row)

    def _mark_missing(self, row: int) -> None:
        item = self._table.item(row, 0)
        if item is None:
            return
        item.setForeground(QColor(192, 57, 43))
        item.setText(f"⚠ {item.text()}")
        item.setToolTip("Arquivo nao encontrado. Use 'Substituir arquivo' ou remova a linha.")

    def replace_selected(self) -> None:
        """Troca o arquivo da linha selecionada (sem perder o resto do projeto)."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._paths):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Substituir arquivo", self._settings.last_dir, IMAGE_FILE_FILTER
        )
        if not path:
            return
        self._paths[row] = path
        self._table.setItem(row, 0, QTableWidgetItem(Path(path).name))
        if self._loaded:
            self._relayout()

    def new_project(self) -> None:
        self._project_path = None
        self._reset_project_state()
        self._table.setRowCount(0)
        self._paths = []
        self._settings.last_project = ""
        self._store.save(self._settings)
        self._update_title()

    def open_project(self, path: str | None = None) -> bool:
        interactive = not isinstance(path, str) or not path
        if interactive:
            path, _ = QFileDialog.getOpenFileName(
                self, "Abrir projeto", self._settings.last_dir,
                f"Projeto PrintNest (*{PROJECT_EXTENSION})",
            )
            if not path:
                return False
        try:
            doc = self._project_store.load(path)
        except ProjectError as exc:
            if interactive:
                QMessageBox.critical(self, "PrintNest", str(exc))
            return False
        self._apply_project(doc)
        self._project_path = path
        self._settings.last_project = path
        self._store.save(self._settings)
        self._update_title()
        missing = [f.path for f in doc.files if not Path(f.path).exists()]
        if interactive and missing:
            QMessageBox.warning(
                self, "PrintNest",
                f"{len(missing)} arquivo(s) nao encontrado(s) (marcados em vermelho).\n"
                "Use 'Substituir arquivo' ou remova as linhas para continuar.",
            )
        return True

    def save_project(self, path: str | None = None) -> bool:
        interactive = not isinstance(path, str) or not path
        if interactive:
            path = self._project_path
        if not path:
            return self.save_project_as()
        doc = self._collect_project()
        try:
            self._project_store.save(path, doc)
        except ProjectError as exc:
            QMessageBox.critical(self, "PrintNest", str(exc))
            return False
        self._project_path = path
        self._settings.last_project = path
        self._store.save(self._settings)
        self._update_title()
        return True

    def save_project_as(self) -> bool:
        start = self._project_path or str(
            Path(self._settings.last_dir or "") / f"projeto{PROJECT_EXTENSION}"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar projeto como", start,
            f"Projeto PrintNest (*{PROJECT_EXTENSION})",
        )
        if not path:
            return False
        if not path.lower().endswith(PROJECT_EXTENSION):
            path += PROJECT_EXTENSION
        return self.save_project(path)

    def _maybe_reopen_last(self) -> None:
        """Reabre o ultimo projeto ao iniciar (silencioso; nao quebra se faltar)."""
        last = self._settings.last_project
        if last and Path(last).exists():
            # nunca impedir a abertura do programa por causa de um projeto ruim
            with contextlib.suppress(Exception):
                self.open_project(last)

    # ---- construcao da UI ----
    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)

        panel = QVBoxLayout()
        panel.addWidget(self._build_arquivo_group())
        panel.addWidget(self._build_chapa_group())
        panel.addWidget(self._build_faca_group())
        panel.addWidget(self._build_registro_group())
        panel.addWidget(self._build_exibicao_group())

        self._btn_generate = QPushButton("Gerar Producao")
        self._btn_generate.clicked.connect(lambda: self.generate())
        panel.addWidget(self._btn_generate)

        self._btn_fit = QPushButton("Ajustar a tela (zoom)")
        self._btn_fit.clicked.connect(lambda: self._fit_view())
        panel.addWidget(self._btn_fit)

        self._btn_pdf = QPushButton("Exportar PDF")
        self._btn_pdf.clicked.connect(lambda: self.export_pdf())
        self._btn_pdf.setEnabled(False)
        panel.addWidget(self._btn_pdf)

        self._btn_dxf = QPushButton("Exportar DXF")
        self._btn_dxf.clicked.connect(lambda: self.export_dxf())
        self._btn_dxf.setEnabled(False)
        panel.addWidget(self._btn_dxf)

        self._btn_img = QPushButton("Exportar Imagem (PNG/JPEG)")
        self._btn_img.clicked.connect(lambda: self.export_image())
        self._btn_img.setEnabled(False)
        panel.addWidget(self._btn_img)

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
        self._view.drag_started.connect(self._begin_move)
        self._view.drag_finished.connect(self._end_move)
        self._view.nudge.connect(self._nudge)

        # area de trabalho estilo Corel: reguas no topo e a esquerda
        work = QWidget()
        grid = QGridLayout(work)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self._corner = QWidget()
        self._corner.setFixedSize(RULER_SIZE, RULER_SIZE)
        self._corner.setStyleSheet("background:#e0e0e0;")
        self._h_ruler = Ruler(self._view, horizontal=True)
        self._v_ruler = Ruler(self._view, horizontal=False)
        grid.addWidget(self._corner, 0, 0)
        grid.addWidget(self._h_ruler, 0, 1)
        grid.addWidget(self._v_ruler, 1, 0)
        grid.addWidget(self._view, 1, 1)
        self._view.view_changed.connect(self._h_ruler.update)
        self._view.view_changed.connect(self._v_ruler.update)

        root.addWidget(scroll, 0)
        root.addWidget(work, 1)
        self.setCentralWidget(central)
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        self._table.setToolTip("Arquivos e a quantidade de copias de cada um")
        self._import_box.setToolTip(
            "Caixa de Midia mantem a sangria; Caixa de Apara corta no traco de corte do PDF"
        )
        self._rotation.setToolTip("Gira todos os arquivos (graus)")
        self._width.setToolTip("Largura da chapa de material (mm)")
        self._height.setToolTip("Altura da chapa (mm). 0 = chapa unica (comprimento aberto)")
        self._spacing.setToolTip("Espaco entre as pecas (mm)")
        self._offset.setToolTip("Sangria: aumenta a faca para fora da arte (mm)")
        self._safety.setToolTip("Recuo: faca para dentro, para nao cortar informacao (mm)")
        self._crop.setToolTip("Corta as bordas da arte (remove faixa branca) (mm)")
        self._shared.setToolTip("Faca por peca (quadrados) ou compartilhada (grade fora a fora)")
        self._reg_type.setToolTip("Tipo de marca de registro para a mesa de corte")
        self._mk_distance.setToolTip("Mimaki: distancia do quadro ate o conteudo (mm)")
        self._mk_size.setToolTip("Mimaki: tamanho das marcas em L (mm)")
        self._mk_thickness.setToolTip("Mimaki: espessura das marcas (mm)")
        self._view_mode.setToolTip("O que mostrar: impressao, corte, ambos ou tela dividida")
        self._show_rulers.setToolTip("Mostra/esconde as reguas (mm)")
        self._snap_check.setToolTip(
            "Encaixe magnetico: a peca gruda nas bordas/centro das outras e da chapa (Alt+Q)"
        )

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
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Arquivo", "Qtd"])
        self._table.verticalHeader().setVisible(False)
        self._table.setColumnWidth(0, 165)
        self._table.setColumnWidth(1, 92)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.itemSelectionChanged.connect(self._update_selection_info)
        lay.addWidget(self._table)
        lay.addWidget(QLabel("Cortar para (caixa do PDF)"))
        self._import_box = QComboBox()
        self._import_box.addItem("Caixa de Midia (sangria)", "media")
        self._import_box.addItem("Caixa de Apara (corte)", "trim")
        lay.addWidget(self._import_box)
        self._btn_remove = QPushButton("Remover PDF selecionado")
        self._btn_remove.clicked.connect(lambda: self.remove_selected())
        lay.addWidget(self._btn_remove)
        self._sel_info = QLabel("Selecione um arquivo")
        self._sel_info.setWordWrap(True)
        self._sel_info.setStyleSheet(
            "border:1px solid #34495e; border-radius:4px; padding:6px; background:white;"
        )
        lay.addWidget(self._sel_info)
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

        # Faca automatica de imagens (PNG/JPG/WEBP)
        sep = QLabel("Faca automatica (imagens)")
        sep.setStyleSheet("font-weight:bold; color:#c0392b; margin-top:6px;")
        lay.addWidget(sep)
        lay.addWidget(QLabel("Sensibilidade (0-100)"))
        self._auto_sensitivity = _spin(0, 100)
        lay.addWidget(self._auto_sensitivity)
        self._auto_ignore_white = QCheckBox("Ignorar fundo branco (imagens opacas)")
        lay.addWidget(self._auto_ignore_white)
        lay.addWidget(QLabel("Offset externo - sangria p/ fora (mm)"))
        self._auto_offset_ext = _spin(0, 100, decimals=2)
        self._auto_offset_ext.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._auto_offset_ext)
        lay.addWidget(QLabel("Offset interno - recuo p/ dentro (mm)"))
        self._auto_offset_int = _spin(0, 100, decimals=2)
        self._auto_offset_int.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._auto_offset_int)
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

    def _build_exibicao_group(self) -> QFrame:
        group, lay = self._section("Exibicao", "#2c3e50")
        lay.addWidget(QLabel("Modo de visualizacao"))
        self._view_mode = QComboBox()
        self._view_mode.addItem("Impressao + Corte", "both")
        self._view_mode.addItem("So Impressao", "print")
        self._view_mode.addItem("So Corte", "cut")
        self._view_mode.addItem("Tela dividida (impressao / corte)", "split")
        self._view_mode.currentIndexChanged.connect(lambda _: self._refresh_preview())
        lay.addWidget(self._view_mode)
        self._show_rulers = QCheckBox("Mostrar reguas (mm)")
        self._show_rulers.toggled.connect(lambda _: self._apply_rulers_visibility())
        lay.addWidget(self._show_rulers)
        self._snap_check = QCheckBox("Encaixar pecas ao arrastar (snap)")
        self._snap_check.toggled.connect(self._set_snap)
        lay.addWidget(self._snap_check)
        return group

    def _apply_rulers_visibility(self) -> None:
        visible = self._show_rulers.isChecked()
        self._h_ruler.setVisible(visible)
        self._v_ruler.setVisible(visible)
        self._corner.setVisible(visible)

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
        self._show_rulers.setChecked(s.show_rulers)
        self._apply_rulers_visibility()
        self._snap_check.setChecked(s.snap_enabled)
        self._set_snap(s.snap_enabled)
        self._view_mode.setCurrentIndex(max(0, self._view_mode.findData(s.view_mode)))
        self._import_box.setCurrentIndex(max(0, self._import_box.findData(s.import_box)))
        self._auto_sensitivity.setValue(int(s.auto_sensitivity))
        self._auto_ignore_white.setChecked(s.auto_ignore_white)
        self._auto_offset_ext.setValue(s.auto_offset_external)
        self._auto_offset_int.setValue(s.auto_offset_internal)

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
        s.show_rulers = self._show_rulers.isChecked()
        s.view_mode = self._view_mode.currentData()
        s.import_box = self._import_box.currentData()
        s.snap_enabled = self._snap.enabled
        s.auto_sensitivity = float(self._auto_sensitivity.value())
        s.auto_ignore_white = self._auto_ignore_white.isChecked()
        s.auto_offset_external = float(self._auto_offset_ext.value())
        s.auto_offset_internal = float(self._auto_offset_int.value())
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

    def _image_faca(self, base: ImageArtwork, net_offset: float):
        """Faca de uma imagem: contorno detectado com o offset externo/interno."""
        contour = base.raw_contour
        if contour is not None and net_offset != 0:
            contour = offset_contour(contour, net_offset)
        return replace(base, cut_contour=contour)

    # ---- lista de arquivos ----
    def add_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar arquivos (PDF / imagem)", self._settings.last_dir,
            IMAGE_FILE_FILTER,
        )
        if paths:
            self.add_paths(paths)
            self._settings.last_dir = str(Path(paths[0]).parent)
            self._store.save(self._settings)

    def add_paths(self, paths: list[str]) -> None:
        for path in paths:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(Path(path).name))
            spin = QuantityStepper(1, 100000, 1)
            spin.valueChanged.connect(lambda _: self._relayout())
            self._table.setCellWidget(row, 1, spin)
            self._table.setRowHeight(row, 34)
            self._paths.append(path)

    def remove_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        self._table.removeRow(row)
        del self._paths[row]
        self._relayout()

    @staticmethod
    def _fmt_mm(value: float) -> str:
        return f"{value:.0f}" if abs(value - round(value)) < 0.05 else f"{value:.1f}"

    def _update_selection_info(self) -> None:
        """Mostra a medida do arquivo selecionado numa caixa (sem poluir o preview)."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._paths):
            self._sel_info.setText("Selecione um arquivo")
            return
        path = self._paths[row]
        name = Path(path).name
        sizes, seen = [], set()
        for art in self._base_artworks:
            if self._sources.get(art.id, (None,))[0] != path:
                continue
            key = (round(art.size.width, 1), round(art.size.height, 1))
            if key not in seen:
                seen.add(key)
                sizes.append(f"{self._fmt_mm(art.size.width)} x {self._fmt_mm(art.size.height)} mm")
        if sizes:
            self._sel_info.setText(f"{name}\n" + " | ".join(sizes))
        else:
            self._sel_info.setText(f"{name}\n(gere a producao para ver a medida)")

    def _quantities(self) -> dict[str, int]:
        """Quantidade por arquivo, lida da tabela (path -> qtd)."""
        result: dict[str, int] = {}
        for row in range(self._table.rowCount()):
            spin = self._table.cellWidget(row, 1)
            result[self._paths[row]] = spin.value() if spin else 1
        return result

    # ---- producao ----
    def _material(self) -> Material:
        return Material(
            name="MVP", width=float(self._width.value()), spacing=float(self._spacing.value())
        )

    def generate(self, *, blocking: bool = False) -> None:
        if not self._paths:
            QMessageBox.warning(self, "PrintNest", "Adicione ao menos um arquivo.")
            return
        self._save_settings()
        material = self._material()
        offset = self._effective_offset()
        sheet_height = float(self._height.value())
        box = self._import_box.currentData()
        sensitivity = float(self._auto_sensitivity.value())
        ignore_white = self._auto_ignore_white.isChecked()
        self._fit_next = True  # ajusta o zoom uma vez apos gerar

        if blocking:
            result = self._pipeline.execute(
                self._paths, material, offset, sheet_height, box,
                sensitivity=sensitivity, ignore_white=ignore_white,
            )
            unique = sorted(set(result.sources.values()))
            png_map = {key: self._renderer.render_png(key[0], key[1], box=box) for key in unique}
            self._load_production(result, png_map)
            return

        self._set_busy(True)
        self._thread = QThread()
        self._worker = ProductionWorker(
            self._pipeline, self._renderer, list(self._paths),
            material, offset, sheet_height, box, sensitivity, ignore_white,
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
        self._origins = dict(result.origins) or {
            art_id: src[0] for art_id, src in result.sources.items()
        }
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
        self._btn_img.setEnabled(True)
        self._relayout()
        self._update_selection_info()

    def _relayout(self) -> None:
        """Recalcula faca + nesting com os parametros atuais (tempo real)."""
        if not self._loaded:
            return
        offset = self._effective_offset()
        material = self._material()
        sheet_height = float(self._height.value())
        quantities = self._quantities()
        net_image_offset = (
            float(self._auto_offset_ext.value()) - float(self._auto_offset_int.value())
        )
        try:
            artworks = []
            for base in self._base_artworks:
                path = self._origins.get(base.id) or self._sources.get(base.id, (None,))[0]
                qty = quantities.get(path, 0)  # arquivo removido da tabela -> 0
                if qty <= 0:
                    continue
                if isinstance(base, ImageArtwork):
                    art = self._image_faca(base, net_image_offset)
                else:
                    art = self._faca_uc.execute(self._transform(base), offset)
                artworks.extend([art] * qty)
        except ValidationError:
            self._status.setText("Recorte/recuo grande demais para a peca.")
            return
        if not artworks:
            self._scene.clear()
            self._status.setText("Nenhuma peca (verifique quantidades).")
            return
        sheets = self._nesting_uc.execute_sheets(artworks, material, sheet_height)
        self._result = ProductionResult(sheets=sheets, artworks=artworks, sources=self._sources)
        self._draw_preview()
        total = sum(s.item_count for s in sheets)
        self._status.setText(f"{len(sheets)} chapa(s) | {total} peca(s)")

    def _refresh_preview(self) -> None:
        if self._result is not None:
            self._draw_preview()

    def _draw_preview(self) -> None:
        self._piece_items = []
        self._undo.clear()  # arranjo regenerado: zera historico de movimentos
        self._scene.clear()
        if self._result is None:
            return
        mode = self._view_mode.currentData()
        if mode == "split":
            self._draw_sheets(draw_art=True, draw_cut=False, dy=0.0, interactive=False)
            total_h = max((s.used_length for s in self._result.sheets), default=0.0)
            self._draw_sheets(
                draw_art=False, draw_cut=True, dy=total_h + max(50.0, total_h * 0.15),
                interactive=False,
            )
        else:
            self._draw_sheets(
                draw_art=mode in ("both", "print"),
                draw_cut=mode in ("both", "cut"),
                dy=0.0,
                interactive=mode in ("both", "print"),
            )
        if self._fit_next:
            self._fit_view()
            self._fit_next = False
        else:
            self._view.view_changed.emit()  # mantem o zoom; atualiza reguas

    def _draw_sheets(self, *, draw_art: bool, draw_cut: bool, dy: float, interactive: bool) -> None:
        result = self._result
        by_id = {a.id: a for a in result.artworks}
        sheet_brush = QBrush(QColor(255, 255, 255))  # chapa = pagina branca
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
                dx, dy, layout.material.width, layout.used_length, material_pen, sheet_brush
            )
            for item in layout.items:
                art = by_id.get(item.artwork_id)
                if art is None:
                    continue
                fp = artwork_footprint(art)
                piece = PieceItem(
                    fp.max_x - fp.min_x, fp.max_y - fp.min_y,
                    artwork_id=item.artwork_id, name=art.name, art_size=art.size,
                    sheet_index=index, dx=dx, dy=dy,
                )
                piece.setPos(dx + item.position.x, dy + item.position.y)
                if interactive:
                    piece.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                    piece.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                    piece.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
                    piece.snap = self._snap
                    piece.sheet_rect = (dx, dy, layout.material.width, layout.used_length)
                    self._piece_items.append(piece)

                ax, ay = -fp.min_x, -fp.min_y  # origem da arte relativa a celula
                if draw_art:
                    key = self._sources.get(item.artwork_id)
                    pixmap = self._pixmaps.get(key)
                    if pixmap is not None and not pixmap.isNull() and pixmap.width() > 0:
                        display = self._display_pixmap(
                            pixmap, crop, rotation, art.size, cropped_cache, key
                        )
                        child = QGraphicsPixmapItem(display, piece)
                        child.setScale(art.size.width / display.width())
                        child.setPos(ax, ay)
                    else:
                        rect = QGraphicsRectItem(ax, ay, art.size.width, art.size.height, piece)
                        rect.setBrush(empty_brush)
                        rect.setPen(material_pen)
                if draw_cut and art.has_cut and not shared:
                    faca = art.cut_contour
                    poly = QPolygonF([QPointF(ax + p.x, ay + p.y) for p in faca.points])
                    poly_item = QGraphicsPolygonItem(poly, piece)
                    poly_item.setPen(faca_pen)
                    poly_item.setBrush(Qt.NoBrush)
                self._scene.addItem(piece)

            if draw_cut and shared:
                for seg in shared_cut_segments(layout, result.artworks):
                    self._scene.addLine(
                        dx + seg.start.x, dy + seg.start.y,
                        dx + seg.end.x, dy + seg.end.y, faca_pen,
                    )
            if draw_cut:
                self._draw_marks(
                    layout, result.artworks, dx, dy, reg, mark_pen, mark_brush, faca_pen
                )

    def _fit_view(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if not rect.isEmpty():
            self._view.fitInView(rect, Qt.KeepAspectRatio)
            self._view.view_changed.emit()

    # ---- edicao na area de trabalho (mover / agrupar / desfazer) ----
    def _begin_move(self) -> None:
        self._snap.dragging = True  # ativa o encaixe so durante o arraste
        self._move_snapshot = {
            it: it.pos()
            for it in self._scene.selectedItems()
            if it.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        }

    def _end_move(self) -> None:
        self._snap.dragging = False
        moves = []
        for item, old in self._move_snapshot.items():
            new = item.pos()
            if abs(new.x() - old.x()) > 0.01 or abs(new.y() - old.y()) > 0.01:
                moves.append((item, old, new))
        if moves:
            self._undo.push(MoveCommand(moves))
        self._move_snapshot = {}

    def _group_selected(self) -> None:
        items = [it for it in self._scene.selectedItems() if isinstance(it, PieceItem)]
        if len(items) < 2:
            return
        group = self._scene.createItemGroup(items)
        group.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        group.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    def _ungroup_selected(self) -> None:
        for item in list(self._scene.selectedItems()):
            if isinstance(item, QGraphicsItemGroup):
                self._scene.destroyItemGroup(item)

    # ---- snap / nudge / alinhar / distribuir / duplicar ----
    def _set_snap(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self._snap.enabled = enabled
        if hasattr(self, "_snap_check") and self._snap_check.isChecked() != enabled:
            self._snap_check.setChecked(enabled)
        if hasattr(self, "_snap_action") and self._snap_action.isChecked() != enabled:
            self._snap_action.setChecked(enabled)

    def _selected_movable(self) -> list:
        return [
            it for it in self._scene.selectedItems()
            if it.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        ]

    def _selected_pieces(self) -> list:
        """Pecas selecionadas, abrindo grupos selecionados."""
        out: list = []
        for it in self._scene.selectedItems():
            if isinstance(it, QGraphicsItemGroup):
                out.extend(c for c in it.childItems() if isinstance(c, PieceItem))
            elif isinstance(it, PieceItem):
                out.append(it)
        return out

    def _nudge(self, dx: float, dy: float) -> None:
        """Empurra as pecas selecionadas com as setas (mm), com desfazer."""
        items = self._selected_movable()
        if not items:
            return
        moves = []
        for it in items:
            old = it.pos()
            moves.append((it, old, QPointF(old.x() + dx, old.y() + dy)))
        self._undo.push(MoveCommand(moves))

    def _align(self, mode: str) -> None:
        items = self._selected_movable()
        if len(items) < 2:
            return
        rects = {it: it.sceneBoundingRect() for it in items}
        left = min(r.left() for r in rects.values())
        right = max(r.right() for r in rects.values())
        top = min(r.top() for r in rects.values())
        bottom = max(r.bottom() for r in rects.values())
        cx, cy = (left + right) / 2.0, (top + bottom) / 2.0
        moves = []
        for it, r in rects.items():
            dx = dy = 0.0
            if mode == "left":
                dx = left - r.left()
            elif mode == "right":
                dx = right - r.right()
            elif mode == "hcenter":
                dx = cx - r.center().x()
            elif mode == "top":
                dy = top - r.top()
            elif mode == "bottom":
                dy = bottom - r.bottom()
            elif mode == "vcenter":
                dy = cy - r.center().y()
            if abs(dx) > 0.001 or abs(dy) > 0.001:
                old = it.pos()
                moves.append((it, old, QPointF(old.x() + dx, old.y() + dy)))
        if moves:
            self._undo.push(MoveCommand(moves))

    def _distribute(self, axis: str) -> None:
        items = self._selected_movable()
        if len(items) < 3:
            return
        horizontal = axis == "h"
        rects = {it: it.sceneBoundingRect() for it in items}
        ordered = sorted(items, key=lambda it: rects[it].left() if horizontal else rects[it].top())
        if horizontal:
            span = rects[ordered[-1]].right() - rects[ordered[0]].left()
            sizes = sum(rects[it].width() for it in ordered)
        else:
            span = rects[ordered[-1]].bottom() - rects[ordered[0]].top()
            sizes = sum(rects[it].height() for it in ordered)
        gap = (span - sizes) / (len(ordered) - 1)
        cursor = rects[ordered[0]].left() if horizontal else rects[ordered[0]].top()
        moves = []
        for it in ordered:
            r = rects[it]
            if horizontal:
                dx, dy = cursor - r.left(), 0.0
                cursor += r.width() + gap
            else:
                dx, dy = 0.0, cursor - r.top()
                cursor += r.height() + gap
            if abs(dx) > 0.001 or abs(dy) > 0.001:
                old = it.pos()
                moves.append((it, old, QPointF(old.x() + dx, old.y() + dy)))
        if moves:
            self._undo.push(MoveCommand(moves))

    def _add_placed(self, add_by_sheet: dict) -> None:
        """Acrescenta PlacedItems por chapa e redesenha (estende o comprimento usado)."""
        if not add_by_sheet:
            return
        by_id = {a.id: a for a in self._result.artworks}
        sheets = []
        for index, layout in enumerate(self._effective_sheets()):
            items = list(layout.items) + add_by_sheet.get(index, [])
            used = layout.used_length
            for placed in items:
                art = by_id.get(placed.artwork_id)
                if art is None:
                    continue
                fp = artwork_footprint(art)
                used = max(used, placed.position.y + (fp.max_y - fp.min_y))
            sheets.append(Layout(layout.material, items, used))
        self._result = ProductionResult(
            sheets=sheets, artworks=self._result.artworks, sources=self._sources
        )
        self._draw_preview()
        total = sum(s.item_count for s in sheets)
        self._status.setText(f"{len(sheets)} chapa(s) | {total} peca(s)")

    def _duplicate_selected(self) -> None:
        """Duplica as pecas selecionadas com deslocamento diagonal (Corel: Ctrl+D)."""
        if self._result is None:
            return
        sel = self._selected_pieces()
        if not sel:
            return
        off = NUDGE_SUPER_MM
        add: dict[int, list] = {}
        for piece in sel:
            px = piece.scenePos().x() - piece.dx + off
            py = piece.scenePos().y() - piece.dy + off
            add.setdefault(piece.sheet_index, []).append(
                PlacedItem(piece.artwork_id, Point2D(px, py))
            )
        self._add_placed(add)

    def _step_repeat(self, cols: int, rows: int, gap: float) -> None:
        """Cria copias em grade das pecas selecionadas (step and repeat)."""
        if self._result is None:
            return
        sel = self._selected_pieces()
        if not sel or cols < 1 or rows < 1 or (cols == 1 and rows == 1):
            return
        by_id = {a.id: a for a in self._result.artworks}
        add: dict[int, list] = {}
        for piece in sel:
            art = by_id.get(piece.artwork_id)
            if art is None:
                continue
            fp = artwork_footprint(art)
            width, height = fp.max_x - fp.min_x, fp.max_y - fp.min_y
            bx = piece.scenePos().x() - piece.dx
            by = piece.scenePos().y() - piece.dy
            for col in range(cols):
                for row in range(rows):
                    if col == 0 and row == 0:
                        continue
                    px = bx + col * (width + gap)
                    py = by + row * (height + gap)
                    add.setdefault(piece.sheet_index, []).append(
                        PlacedItem(piece.artwork_id, Point2D(px, py))
                    )
        self._add_placed(add)

    def _step_repeat_dialog(self) -> None:
        if self._result is None or not self._selected_pieces():
            QMessageBox.information(self, "PrintNest", "Selecione ao menos uma peca.")
            return
        cols, ok = QInputDialog.getInt(self, "Repetir em grade", "Colunas:", 2, 1, 200)
        if not ok:
            return
        rows, ok = QInputDialog.getInt(self, "Repetir em grade", "Linhas:", 1, 1, 200)
        if not ok:
            return
        gap, ok = QInputDialog.getDouble(
            self, "Repetir em grade", "Espacamento entre copias (mm):", 5.0, 0.0, 1000.0, 1
        )
        if not ok:
            return
        self._step_repeat(cols, rows, gap)

    def _effective_sheets(self) -> list:
        """Sheets refletindo movimentos manuais das pecas (ou o nesting original)."""
        if not self._piece_items:
            return self._result.sheets
        moved: dict[int, list] = {}
        for piece in self._piece_items:
            # scenePos funciona mesmo se a peca estiver dentro de um grupo
            pos = Point2D(piece.scenePos().x() - piece.dx, piece.scenePos().y() - piece.dy)
            moved.setdefault(piece.sheet_index, []).append(PlacedItem(piece.artwork_id, pos))
        sheets = []
        for index, layout in enumerate(self._result.sheets):
            items = moved.get(index, [])  # vazio = todas as pecas excluidas
            sheets.append(Layout(layout.material, items, layout.used_length))
        return sheets

    def _select_all(self) -> None:
        for piece in self._piece_items:
            piece.setSelected(True)

    def _delete_selected(self) -> None:
        if not self._piece_items:
            return
        to_remove = set()
        for item in list(self._scene.selectedItems()):
            if isinstance(item, QGraphicsItemGroup):
                to_remove.update(c for c in item.childItems() if isinstance(c, PieceItem))
            elif isinstance(item, PieceItem):
                to_remove.add(item)
        if not to_remove:
            return
        self._piece_items = [p for p in self._piece_items if p not in to_remove]
        self._result = ProductionResult(
            sheets=self._effective_sheets(),
            artworks=self._result.artworks,
            sources=self._sources,
        )
        self._draw_preview()
        total = sum(s.item_count for s in self._result.sheets)
        self._status.setText(f"{len(self._result.sheets)} chapa(s) | {total} peca(s)")

    def _reset_arrangement(self) -> None:
        """Refaz o nesting do zero (descarta movimentos/exclusoes manuais)."""
        self._fit_next = True
        self._relayout()

    def _draw_marks(self, layout, artworks, dx, dy, reg, mark_pen, mark_brush, faca_pen) -> None:
        if reg == "circles":
            for mark in registration_marks(
                layout, artworks,
                margin_mm=float(self._reg_margin.value()),
                diameter_mm=float(self._reg_diameter.value()),
            ):
                self._scene.addEllipse(
                    dx + mark.center.x - mark.radius, dy + mark.center.y - mark.radius,
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
                dx + f.min_x, dy + f.min_y, f.max_x - f.min_x, f.max_y - f.min_y, faca_pen
            )
            for seg in marks.segments:
                self._scene.addLine(
                    dx + seg.start.x, dy + seg.start.y,
                    dx + seg.end.x, dy + seg.end.y, mark_pen,
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
    def _print_kwargs(self) -> dict:
        """Parametros de marca/recorte/rotacao/caixa comuns ao PDF e a imagem."""
        return {
            "reg_type": self._reg(),
            "reg_margin_mm": float(self._reg_margin.value()),
            "reg_diameter_mm": float(self._reg_diameter.value()),
            "mimaki_distance_mm": float(self._mk_distance.value()),
            "mimaki_size_mm": float(self._mk_size.value()),
            "mimaki_thickness_mm": float(self._mk_thickness.value()),
            "crop_mm": float(self._crop.value()),
            "rotate": self._rotation_value(),
            "box": self._import_box.currentData(),
        }

    def export_pdf(self, path: str | None = None, pages=None) -> None:
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        sheets = self._select_export_sheets(
            self._effective_sheets(), pages, interactive, "Exportar PDF de impressao"
        )
        if sheets is None:
            return
        if not sheets:
            if interactive:
                QMessageBox.warning(self, "PrintNest", "Nenhuma chapa selecionada.")
            return
        if interactive:
            path, _ = QFileDialog.getSaveFileName(
                self, "Exportar PDF", str(Path(self._settings.last_dir) / "IMPRESSAO.pdf"),
                "PDF (*.pdf)",
            )
            if not path:
                return
        self._print_export.execute(
            sheets, self._result.artworks, self._result.sources, path, **self._print_kwargs()
        )
        if interactive:
            QMessageBox.information(self, "PrintNest", f"PDF gerado:\n{path}")

    def export_image(
        self, path: str | None = None, pages=None, dpi=None, image_format=None
    ) -> None:
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        sheets = self._select_export_sheets(
            self._effective_sheets(), pages, interactive, "Exportar Imagem"
        )
        if sheets is None:
            return
        if not sheets:
            if interactive:
                QMessageBox.warning(self, "PrintNest", "Nenhuma chapa selecionada.")
            return
        if dpi is None:
            if interactive:
                dpi, ok = QInputDialog.getInt(
                    self, "Exportar Imagem", "Resolucao (DPI):",
                    int(self._settings.export_dpi), 30, 1200, 10,
                )
                if not ok:
                    return
            else:
                dpi = int(self._settings.export_dpi)
        if interactive:
            path, _ = QFileDialog.getSaveFileName(
                self, "Exportar Imagem",
                str(Path(self._settings.last_dir) / "IMPRESSAO.png"),
                "PNG (*.png);;JPEG (*.jpg *.jpeg)",
            )
            if not path:
                return
        if image_format is None:
            image_format = "jpeg" if Path(path).suffix.lower() in (".jpg", ".jpeg") else "png"
        self._settings.export_dpi = int(dpi)
        self._store.save(self._settings)
        gerados = self._print_export.execute_image(
            sheets, self._result.artworks, self._result.sources, path,
            dpi=int(dpi), image_format=image_format, **self._print_kwargs(),
        )
        if interactive:
            QMessageBox.information(
                self, "PrintNest", f"{len(gerados)} imagem(ns) gerada(s) a {int(dpi)} DPI."
            )

    @staticmethod
    def _parse_pages(spec: str, total: int) -> list[int]:
        """Converte '1,3-5' em indices 0-based; vazio = todas as chapas."""
        spec = (spec or "").strip()
        if not spec:
            return list(range(total))
        result: set[int] = set()
        for part in spec.replace(" ", "").split(","):
            if "-" in part:
                a, _, b = part.partition("-")
                if a.isdigit() and b.isdigit():
                    for i in range(int(a), int(b) + 1):
                        if 1 <= i <= total:
                            result.add(i - 1)
            elif part.isdigit() and 1 <= int(part) <= total:
                result.add(int(part) - 1)
        return sorted(result)

    def _select_export_sheets(self, sheets_all, pages, interactive, title):
        """Escolhe quais chapas exportar. Retorna None se o usuario cancelar."""
        total = len(sheets_all)
        if pages is None:
            if interactive and total > 1:
                spec, ok = QInputDialog.getText(
                    self, title,
                    f"Chapas a exportar (1-{total}). Vazio = todas. Ex.: 1,3-5",
                )
                if not ok:
                    return None
                idxs = self._parse_pages(spec, total)
            else:
                idxs = list(range(total))
        elif isinstance(pages, str):
            idxs = self._parse_pages(pages, total)
        else:
            idxs = [i for i in pages if 0 <= i < total]
        return [sheets_all[i] for i in idxs]

    def _dxf_payload(self, sheets):
        """Monta (contornos, segmentos, marcas, marcas-em-L) de um conjunto de chapas."""
        artworks = self._result.artworks
        sheet_width = sheets[0].material.width
        reg = self._reg()
        if self._shared.currentIndex() == 1:
            contours = []
            segments = shared_cut_segments_sheets(sheets, artworks, sheet_width)
        else:
            contours = positioned_cut_contours_sheets(sheets, artworks, sheet_width)
            segments = []
        marks, mark_segments = [], []
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
        return contours, segments, marks, mark_segments

    def export_dxf(self, path: str | None = None, pages=None) -> None:
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        sheets = self._select_export_sheets(
            self._effective_sheets(), pages, interactive, "Exportar DXF"
        )
        if sheets is None:
            return
        if not sheets:
            if interactive:
                QMessageBox.warning(self, "PrintNest", "Nenhuma chapa selecionada.")
            return
        if interactive:
            path, _ = QFileDialog.getSaveFileName(
                self, "Exportar DXF", str(Path(self._settings.last_dir) / "CORTE.dxf"),
                "DXF (*.dxf)",
            )
            if not path:
                return
        contours, segments, marks, mark_segments = self._dxf_payload(sheets)
        self._dxf_export.execute(
            contours, path, segments=segments, marks=marks, mark_segments=mark_segments
        )
        if interactive:
            QMessageBox.information(self, "PrintNest", f"DXF gerado:\n{path}")

    def export_dxf_per_sheet(self, base_path: str | None = None) -> None:
        """Exporta um DXF por chapa: CORTE_01.dxf, CORTE_02.dxf, ..."""
        if self._result is None:
            return
        interactive = not isinstance(base_path, str) or not base_path
        if interactive:
            base_path, _ = QFileDialog.getSaveFileName(
                self, "Exportar DXF por chapa",
                str(Path(self._settings.last_dir) / "CORTE.dxf"), "DXF (*.dxf)",
            )
            if not base_path:
                return
        sheets = self._effective_sheets()
        stem = str(Path(base_path).with_suffix(""))
        ext = Path(base_path).suffix or ".dxf"
        gerados = []
        for i, sheet in enumerate(sheets, start=1):
            contours, segments, marks, mark_segments = self._dxf_payload([sheet])
            out = f"{stem}_{i:02d}{ext}"
            self._dxf_export.execute(
                contours, out, segments=segments, marks=marks, mark_segments=mark_segments
            )
            gerados.append(out)
        if interactive:
            QMessageBox.information(
                self, "PrintNest", f"{len(gerados)} arquivo(s) DXF gerado(s)."
            )
