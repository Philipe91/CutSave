from __future__ import annotations

import contextlib
import functools
import tempfile
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import (
    QLocale,
    QObject,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPolygonF,
    QTransform,
    QUndoCommand,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
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
from app.domain.cut.contour_ops import (
    crop_and_rotate_contour,
    offset_contour,
    simplify_contour,
    smooth_contour,
)
from app.domain.cut.vector import VectorContourGenerator
from app.domain.geometry import Point2D, Size
from app.domain.model.cut_contour import CutContour
from app.domain.model.image_artwork import ImageArtwork, ImageKind
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.domain.nesting.max_rects import MaxRectsPacker
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter
from app.infrastructure.importers.pymupdf_vector_extractor import PyMuPdfVectorExtractor
from app.presentation import icons, measurements, messages, theme, units
from app.presentation.panels import ribbon as ribbon_panel
from app.presentation.panels.status_bar import StatusBarController
from app.presentation.widgets import (
    Alert,
    AlertLevel,
    CollapsibleCard,
    MeasureField,
    ToastManager,
    labeled,
)
from app.shared.config.settings import AppSettings, SettingsStore
from app.shared.errors import ProjectError, ValidationError
from app.shared.resources import resource_path

IMAGE_FILE_FILTER = (
    "Arquivos suportados (*.pdf *.png *.jpg *.jpeg *.webp);;"
    "PDF (*.pdf);;Imagens (*.png *.jpg *.jpeg *.webp)"
)

RULER_SIZE = 24

# Empurrar com as setas (nudge), estilo CorelDRAW: normal, micro (Ctrl), super (Shift).
NUDGE_MM = 1.0
NUDGE_MICRO_MM = 0.1
NUDGE_SUPER_MM = 10.0
# DPI para rasterizar a página de PDF ao detectar a faca "pelo contorno".
PDF_CONTOUR_DPI = 150
SNAP_THRESHOLD_MM = 2.0  # distância (mm) para o encaixe "grudar"
# zona morta do arraste (px na tela): só move a peça depois de passar disso.
# Evita que um clique com leve tremor do mouse arraste a peça sem querer.
DRAG_DEADZONE_PX = 6


class SnapConfig:
    """Estado compartilhado do encaixe (snap) ao arrastar peças."""

    def __init__(self, enabled: bool = True, threshold_mm: float = SNAP_THRESHOLD_MM) -> None:
        self.enabled = enabled
        self.threshold_mm = threshold_mm
        self.dragging = False  # snap só age durante o arraste com o mouse


class ZoomableGraphicsView(QGraphicsView):
    """Preview estilo CorelDRAW: zoom (roda), pan (arrastar), fundo cinza."""

    view_changed = Signal()
    drag_started = Signal()
    drag_finished = Signal()
    nudge = Signal(float, float)  # deslocamento (dx, dy) em mm, via setas
    cursor_moved = Signal(float, float)  # posição do cursor (x, y) em mm na cena
    library_drop = Signal(QPointF)  # arquivo arrastado da biblioteca, soltou na cena

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        # esquerdo: seleciona item / move; em área vazia faz laco de seleção.
        # meio faz pan; roda da zoom.
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor(theme.CANVAS_BG))  # mesa clara (estilo Affinity)
        self.setMouseTracking(True)  # cursor reportado mesmo sem botão pressionado
        self.setAcceptDrops(True)  # aceita arquivos arrastados da biblioteca
        # laco seleciona tudo que ele TOCAR (não precisa envolver por inteiro)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self._panning = False
        self._pan_last = None
        self._left_drag = False
        self._press_view_pos = None  # posição do clique (zona morta de arraste)
        self._drag_armed = False  # vira True só após passar a zona morta

    # ---- arrastar da biblioteca para a área de trabalho ----
    @staticmethod
    def _is_library_drag(event) -> bool:
        src = event.source()
        return isinstance(src, QTableWidget) or event.mimeData().hasFormat(
            "application/x-qabstractitemmodeldatalist"
        )

    def dragEnterEvent(self, event) -> None:
        if self._is_library_drag(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._is_library_drag(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if self._is_library_drag(event):
            self.library_drop.emit(self.mapToScene(event.position().toPoint()))
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def zoom_factor(self) -> float:
        """Fator de zoom atual (1.0 = 100%)."""
        return self.transform().m11()

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        self.view_changed.emit()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self.view_changed.emit()  # mantem réguas/overlay/guias em sincronia

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
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
            # sobe até achar um item selecionavel (peça/guia); ignora os filhos
            # (imagem/faca) e a chapa. Em área "vazia" -> laco de seleção (marquee).
            target = self.itemAt(event.position().toPoint())
            sel = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            while target is not None and not (target.flags() & sel):
                target = target.parentItem()
            if target is not None:
                self.setDragMode(QGraphicsView.NoDrag)
                self._left_drag = True
                self._press_view_pos = event.position()
                self._drag_armed = False
            else:
                self.setDragMode(QGraphicsView.RubberBandDrag)
                self._left_drag = False
        super().mousePressEvent(event)
        # drag_started DEPOIS do super: o Qt já selecionou a peça clicada, entao
        # o snapshot do desfazer (_begin_move) inclui a peça que vai ser movida.
        if self._left_drag:
            self.drag_started.emit()

    def mouseMoveEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.position().toPoint())
        self.cursor_moved.emit(scene_pos.x(), scene_pos.y())
        if self._panning and self._pan_last is not None:
            delta = event.position() - self._pan_last
            self._pan_last = event.position()
            hbar, vbar = self.horizontalScrollBar(), self.verticalScrollBar()
            hbar.setValue(hbar.value() - int(delta.x()))
            vbar.setValue(vbar.value() - int(delta.y()))
            event.accept()
            return
        # zona morta: enquanto não passar do limiar, NAO move a peça (um clique
        # com leve tremor não deve arrastar a peça para cima das vizinhas).
        if self._left_drag and not self._drag_armed and self._press_view_pos is not None:
            if (event.position() - self._press_view_pos).manhattanLength() < DRAG_DEADZONE_PX:
                event.accept()
                return
            self._drag_armed = True
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
            self._drag_armed = False
            self._press_view_pos = None
            self.drag_finished.emit()


# id de merge para que mudancas de parametro consecutivas (arrastar a setinha de
# um campo, digitar) virem UM passo de desfazer, em vez de dezenas.
RELAYOUT_MERGE_ID = 1


class SnapshotCommand(QUndoCommand):
    """Desfaz/refaz QUALQUER mudanca (mover, excluir, duplicar, repetir, alinhar,
    distribuir e também o recalculo por mudanca de parametro).

    Guarda o ESTADO (chapas + artes) antes e depois e reaplica os DADOS, não
    referencias de itens gráficos. Por isso sobrevive a redesenhos e nunca fica
    com referencias mortas — a base do Ctrl+Z ilimitado e confiavel. A pilha só
    e zerada ao gerar/abrir/criar projeto.

    O primeiro 'redo' (disparado pelo push) e ignorado: a operacao já foi
    aplicada quando o comando entra na pilha.
    """

    def __init__(self, window, before, after, text: str, merge_id: int = -1) -> None:
        super().__init__(text)
        self._window = window
        self._before = before  # (sheets, artworks)
        self._after = after
        self._applied = True
        self._merge_id = merge_id

    def id(self) -> int:
        return self._merge_id

    def mergeWith(self, other) -> bool:
        # funde recalculos consecutivos do mesmo tipo num passo só (mantem o
        # 'before' original e adota o 'after' mais novo).
        if self._merge_id < 0 or other.id() != self._merge_id:
            return False
        self._after = other._after
        return True

    def undo(self) -> None:
        self._window._apply_state(self._before)

    def redo(self) -> None:
        if self._applied:
            self._applied = False
            return
        self._window._apply_state(self._after)


class PieceItem(QGraphicsRectItem):
    """Peça na área de trabalho: selecionavel e movel (arte + faca como filhos)."""

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

    def paint(self, painter, option, widget=None) -> None:  # noqa: ARG002
        # a arte e a faca são itens filhos; a peça em si só desenha o contorno
        # AZUL quando esta selecionada (feedback de seleção, estilo CorelDRAW).
        # Não chama super().paint para não mostrar o tracejado padrão do Qt.
        if self.isSelected():
            pen = QPen(QColor(theme.ACCENT))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect())

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
    """Régua (mm) sincronizada com o view, no estilo de softwares de pre-impressao.

    Arrastar a partir da régua cria uma guia (igual CorelDRAW): da régua de cima
    (horizontal) nasce uma guia horizontal; da régua lateral, uma guia vertical.
    """

    # (guia_horizontal, valor_mm na cena) durante o arraste e ao soltar
    guide_preview = Signal(bool, float)
    guide_dropped = Signal(bool, float, bool)  # (..., dentro_do_canvas)

    def __init__(self, view: ZoomableGraphicsView, horizontal: bool) -> None:
        super().__init__()
        self._view = view
        self._h = horizontal
        self._dragging = False
        self.setCursor(Qt.SplitVCursor if horizontal else Qt.SplitHCursor)
        if horizontal:
            self.setFixedHeight(RULER_SIZE)
        else:
            self.setFixedWidth(RULER_SIZE)

    def _scene_value_at(self, gpos) -> tuple[float, bool]:
        """Converte a posição global do mouse no valor (mm) da cena e diz se
        esta dentro do canvas. Guia horizontal usa Y; vertical usa X."""
        vp = self._view.viewport()
        local = vp.mapFromGlobal(gpos)
        scene = self._view.mapToScene(local)
        value = scene.y() if self._h else scene.x()
        return value, vp.rect().contains(local)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            value, _ = self._scene_value_at(event.globalPosition().toPoint())
            self.guide_preview.emit(self._h, value)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            value, _ = self._scene_value_at(event.globalPosition().toPoint())
            self.guide_preview.emit(self._h, value)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            value, inside = self._scene_value_at(event.globalPosition().toPoint())
            self.guide_dropped.emit(self._h, value, inside)
            event.accept()
            return
        super().mouseReleaseEvent(event)

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
        painter.fillRect(self.rect(), QColor(theme.SURFACE_ALT))  # mesma familia do painel
        painter.setPen(QColor(theme.TEXT_SECONDARY))

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
            label = f"{units.from_mm(value):g}"  # valor na unidade atual (mm/cm)
            if self._h:
                pos = view.mapFromScene(QPointF(value, 0.0)).x()
                painter.drawLine(pos, RULER_SIZE - 6, pos, RULER_SIZE)
                painter.drawText(pos + 2, RULER_SIZE - 8, label)
            else:
                pos = view.mapFromScene(QPointF(0.0, value)).y()
                painter.drawLine(RULER_SIZE - 6, pos, RULER_SIZE, pos)
                painter.save()
                painter.translate(RULER_SIZE - 9, pos - 2)
                painter.rotate(-90)
                painter.drawText(0, 0, label)
                painter.restore()
            value += step


class MeasureOverlay(QFrame):
    """Caixinha flutuante no canto da área de trabalho com as medidas do que
    esta selecionado (peça/grupo) ou da chapa quando nada esta selecionado.

    Transparente a cliques (não atrapalha seleção/arraste no canvas).
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("measureOverlay")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(1)
        self._title = QLabel("")
        self._title.setObjectName("ovTitle")
        self._line1 = QLabel("")
        self._line2 = QLabel("")
        for w in (self._title, self._line1, self._line2):
            lay.addWidget(w)
        self.setStyleSheet(
            "#measureOverlay{background:rgba(255,255,255,235);"
            f" border:1px solid {theme.BORDER_STRONG}; border-radius:{theme.RADIUS}px;}}"
            f" QLabel{{color:{theme.TEXT_SECONDARY}; font-size:{theme.FONT_SM}px;}}"
            f" QLabel#ovTitle{{font-weight:600; color:{theme.TEXT};}}"
        )
        self.hide()

    def show_lines(self, title: str, line1: str, line2: str = "") -> None:
        self._title.setText(title)
        self._line1.setText(line1)
        self._line2.setText(line2)
        self._line2.setVisible(bool(line2))
        self.adjustSize()
        self.show()
        self.raise_()


class FloatingDisplayBar(QFrame):
    """Barra flutuante e ARRASTAVEL no canvas com o modo de visualizacao.

    Fica compacta e discreta no canto, para nao atrapalhar o trabalho, e o
    usuario pode reposiciona-la arrastando pela alca (icone). O combo interno
    e o self._view_mode canonico (impressao / corte / dividido).
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("floatBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 3, 8, 3)
        lay.setSpacing(6)
        self._grip = QLabel()
        self._grip.setPixmap(icons.pixmap("eye", theme.TEXT_SECONDARY, 15))
        self._grip.setCursor(Qt.OpenHandCursor)
        self._grip.setToolTip("Arraste para mover · exibicao do canvas")
        lay.addWidget(self._grip)
        self.combo = NoWheelComboBox()
        self.combo.setToolTip("Modo de visualizacao (impressao / corte / dividido)")
        lay.addWidget(self.combo)
        self.setStyleSheet(
            "#floatBar{background:rgba(255,255,255,232);"
            f" border:1px solid {theme.BORDER_STRONG}; border-radius:{theme.RADIUS}px;}}"
            "#floatBar QComboBox{min-height:16px; padding:2px 8px;"
            f" border:1px solid {theme.BORDER}; background:{theme.SURFACE};}}"
        )
        self._press_global = None
        self._press_pos = None
        self._moved = False
        self._collapsed = False

    # ---- arraste + clique (o combo trata os proprios cliques) ----
    # Clicar no olho SEM arrastar colapsa a barra para so o icone (quadradinho);
    # clicar de novo expande. Arrastar (mover alem de um limiar) reposiciona.
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_pos = self.pos()
            self._moved = False
            self._grip.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._press_global is None:
            return
        delta = event.globalPosition().toPoint() - self._press_global
        if not self._moved and delta.manhattanLength() > 4:
            self._moved = True  # passou do limiar -> vira arraste (nao clique)
        if self._moved:
            new = self._press_pos + delta
            parent = self.parent()
            if parent is not None:  # mantem dentro da area visivel do canvas
                new.setX(max(0, min(new.x(), parent.width() - self.width())))
                new.setY(max(0, min(new.y(), parent.height() - self.height())))
            self.move(new)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        was_click = self._press_global is not None and not self._moved
        self._press_global = None
        self._grip.setCursor(Qt.OpenHandCursor)
        if was_click:
            self.set_collapsed(not self._collapsed)
        event.accept()

    def set_collapsed(self, collapsed: bool) -> None:
        """Colapsa a barra para so o olho (quadradinho) ou expande de volta."""
        self._collapsed = collapsed
        self.combo.setVisible(not collapsed)
        self._grip.setToolTip(
            "Clique para expandir · arraste para mover" if collapsed
            else "Clique para recolher · arraste para mover"
        )
        self.adjustSize()


class CropPreview(QWidget):
    """Pre-visualização do recorte de página: mostra a página, sombreia o que
    será cortado e deixa arrastar as 4 bordas para definir o corte (mm)."""

    crop_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._pm: QPixmap | None = None
        self._pw_mm = 1.0
        self._ph_mm = 1.0
        self._crop = [0.0, 0.0, 0.0, 0.0]  # esquerda, cima, direita, baixo (mm)
        self._drag: str | None = None
        self.setMinimumSize(380, 380)
        self.setMouseTracking(True)

    def set_page(self, pixmap, w_mm: float, h_mm: float) -> None:
        self._pm = pixmap
        self._pw_mm = max(1e-3, w_mm)
        self._ph_mm = max(1e-3, h_mm)
        self.update()

    def set_crop(self, left, top, right, bottom) -> None:
        self._crop = [float(left), float(top), float(right), float(bottom)]
        self.update()

    def crop(self) -> tuple:
        return tuple(self._crop)

    def _geom(self):
        m = 14
        aw = max(1, self.width() - 2 * m)
        ah = max(1, self.height() - 2 * m)
        if self._pm is not None and not self._pm.isNull():
            pw, ph = self._pm.width(), self._pm.height()
        else:
            pw, ph = self._pw_mm, self._ph_mm
        s = min(aw / pw, ah / ph)
        dw, dh = pw * s, ph * s
        ox = (self.width() - dw) / 2
        oy = (self.height() - dh) / 2
        return ox, oy, dw, dh, dw / self._pw_mm, dh / self._ph_mm

    def paintEvent(self, event) -> None:  # noqa: ARG002
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(70, 72, 75))
        ox, oy, dw, dh, mmx, mmy = self._geom()
        target = QRectF(ox, oy, dw, dh)
        if self._pm is not None and not self._pm.isNull():
            p.drawPixmap(target, self._pm, QRectF(self._pm.rect()))
        else:
            p.fillRect(target, QColor(theme.SHEET))
        left, top, right, bottom = self._crop
        cx0, cy0 = ox + left * mmx, oy + top * mmy
        cx1, cy1 = ox + dw - right * mmx, oy + dh - bottom * mmy
        shade = QColor(210, 40, 40, 90)
        p.fillRect(QRectF(ox, oy, dw, top * mmy), shade)
        p.fillRect(QRectF(ox, cy1, dw, bottom * mmy), shade)
        p.fillRect(QRectF(ox, cy0, left * mmx, cy1 - cy0), shade)
        p.fillRect(QRectF(cx1, cy0, right * mmx, cy1 - cy0), shade)
        pen = QPen(QColor(theme.ACCENT))  # mesmo azul da marca no recorte
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(cx0, cy0, cx1 - cx0, cy1 - cy0))

    def _edges(self):
        ox, oy, dw, dh, mmx, mmy = self._geom()
        left, top, right, bottom = self._crop
        return {
            "l": ox + left * mmx, "r": ox + dw - right * mmx,
            "t": oy + top * mmy, "b": oy + dh - bottom * mmy,
        }, (ox, oy, dw, dh, mmx, mmy)

    def mousePressEvent(self, event) -> None:
        edges, (ox, oy, dw, dh, mmx, mmy) = self._edges()
        x, y = event.position().x(), event.position().y()
        tol, best, cand = 9, 9, None
        if oy - tol <= y <= oy + dh + tol:
            for e in ("l", "r"):
                if abs(x - edges[e]) < best:
                    best, cand = abs(x - edges[e]), e
        if ox - tol <= x <= ox + dw + tol:
            for e in ("t", "b"):
                if abs(y - edges[e]) < best:
                    best, cand = abs(y - edges[e]), e
        self._drag = cand

    def mouseMoveEvent(self, event) -> None:
        edges, (ox, oy, dw, dh, mmx, mmy) = self._edges()
        x, y = event.position().x(), event.position().y()
        if self._drag is None:
            near_v = abs(x - edges["l"]) < 9 or abs(x - edges["r"]) < 9
            near_h = abs(y - edges["t"]) < 9 or abs(y - edges["b"]) < 9
            self.setCursor(
                Qt.SizeHorCursor if near_v else
                (Qt.SizeVerCursor if near_h else Qt.ArrowCursor)
            )
            return
        left, top, right, bottom = self._crop
        if self._drag == "l":
            left = max(0.0, min((x - ox) / mmx, self._pw_mm - right - 1))
        elif self._drag == "r":
            right = max(0.0, min((ox + dw - x) / mmx, self._pw_mm - left - 1))
        elif self._drag == "t":
            top = max(0.0, min((y - oy) / mmy, self._ph_mm - bottom - 1))
        elif self._drag == "b":
            bottom = max(0.0, min((oy + dh - y) / mmy, self._ph_mm - top - 1))
        self._crop = [left, top, right, bottom]
        self.update()
        self.crop_changed.emit()

    def mouseReleaseEvent(self, event) -> None:  # noqa: ARG002
        self._drag = None


class _ResizeHandle(QGraphicsRectItem):
    """Alça de redimensionamento (estilo CorelDRAW) numa peça selecionada.

    Fica no canto/aresta inferior-direito; arrastar redimensiona a arte
    (ancorada no canto superior-esquerdo, entao a posição não muda). axis:
    'wh' (canto = largura+altura), 'w' (só largura), 'h' (só altura). Tamanho
    fixo na tela (ignora o zoom)."""

    S = 10.0

    def __init__(self, window, piece, axis: str) -> None:
        super().__init__(-self.S / 2, -self.S / 2, self.S, self.S)
        self._w = window
        self._piece = piece
        self._axis = axis
        self.setBrush(QBrush(QColor(theme.SURFACE)))
        pen = QPen(QColor(theme.ACCENT))
        pen.setCosmetic(True)
        pen.setWidth(2)
        self.setPen(pen)
        self.setZValue(2000)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setCursor({
            "wh": Qt.SizeFDiagCursor, "w": Qt.SizeHorCursor, "h": Qt.SizeVerCursor,
        }[axis])

    def mousePressEvent(self, event) -> None:
        self._w._begin_resize(self._piece)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        self._w._update_resize_preview(self._piece, event.scenePos(), self._axis)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._w._end_resize(self._piece, event.scenePos(), self._axis)
        event.accept()


class GuideItem(QGraphicsLineItem):
    """Guia pontilhada (estilo CorelDRAW): selecionavel e arrastavel, presa ao
    eixo perpendicular. 'record' e a entrada mutavel [is_h, valor_mm] guardada
    pela janela, atualizada quando a guia e movida."""

    def __init__(self, record, x0, y0, x1, y1, pen: QPen) -> None:
        super().__init__(x0, y0, x1, y1)
        self.record = record  # [is_h, valor_mm]
        self._is_h = bool(record[0])
        self._base = float(record[1])
        self.setPen(pen)
        self.setZValue(1_000_000)  # sempre acima das peças (mesmo após z-order)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.SizeVerCursor if self._is_h else Qt.SizeHorCursor)

    def shape(self):
        # área de clique mais larga que a linha fina (facilita selecionar)
        stroker = QPainterPathStroker()
        stroker.setWidth(4.0)
        return stroker.createStroke(super().shape())

    def value(self) -> float:
        off = self.pos().y() if self._is_h else self.pos().x()
        return self._base + off

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # trava no eixo perpendicular (guia sempre reta)
            return QPointF(0.0, value.y()) if self._is_h else QPointF(value.x(), 0.0)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.record[1] = self.value()  # mantem o valor guardado em dia
        return super().itemChange(change, value)


class ProductionWorker(QObject):
    """Importa + monta produção e rasteriza as páginas, fora da thread da UI."""

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


def _block_wheel(event) -> None:
    """Ignora o scroll do mouse: o valor NUNCA muda por rolagem (só setas, teclado
    ou digitacao). O evento sobe para a área de rolagem (o painel rola normal).
    Evita o erro de produção de alterar numeros sem querer ao rolar a tela."""
    event.ignore()


class _NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        _block_wheel(event)


class _NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        _block_wheel(event)


class NoWheelComboBox(QComboBox):
    """QComboBox que ignora o scroll do mouse (não troca de item ao rolar)."""

    def wheelEvent(self, event) -> None:  # noqa: N802
        _block_wheel(event)


def _spin(minimum, maximum, decimals=None):
    box = _NoWheelSpinBox() if decimals is None else _NoWheelDoubleSpinBox()
    box.setRange(minimum, maximum)
    return box


class LengthSpin(QDoubleSpinBox):
    """Campo de comprimento que guarda MILIMETROS internamente, mas exibe e
    edita na unidade atual (mm/cm).

    value()/setValue() continuam em mm (todo o app e os testes dependem disso);
    só a apresentacao muda. A conversao acontece em textFromValue/valueFromText.
    """

    def __init__(self, min_mm, max_mm) -> None:
        super().__init__()
        self.setLocale(QLocale(QLocale.Language.C))  # separador decimal '.'
        self.setKeyboardTracking(False)
        self.setDecimals(2)  # precisao interna em mm (permite 0,01 cm)
        self.setRange(float(min_mm), float(max_mm))
        self.refresh_unit()

    def refresh_unit(self) -> None:
        """Reaplica a unidade atual ao passo, sufixo e texto exibido."""
        u = units.unit()
        self.setSingleStep(units.step_mm(u))
        self.setSuffix(f" {u}")
        self.lineEdit().setText(self.textFromValue(self.value()) + self.suffix())

    def textFromValue(self, value_mm: float) -> str:
        return f"{units.from_mm(value_mm):.{units.decimals()}f}"

    def valueFromText(self, text: str) -> float:
        cleaned = text.replace(self.suffix(), "").strip().replace(",", ".")
        try:
            shown = float(cleaned)
        except ValueError:
            return self.value()
        return units.to_mm(shown)

    def wheelEvent(self, event) -> None:  # noqa: N802
        # scroll do mouse NAO altera a medida (só setas/teclado/digitacao)
        _block_wheel(event)


class _QtyLineSpin(QSpinBox):
    """QSpinBox que seleciona todo o número ao receber foco/clique, para o
    usuário digitar a quantidade direto por cima (multiplicar rápido)."""

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if not self.lineEdit().hasSelectedText():
            self.selectAll()


class QuantityStepper(_QtyLineSpin):
    """Campo de quantidade: QSpinBox NATIVO puro (mesmo visual do sistema, igual
    aos campos de Largura/Altura), sem estilizacao custom.

    Mantem value()/setValue()/valueChanged, entao a biblioteca, a aba Transformar
    e os testes continuam funcionando igual. Digitar só recalcula ao confirmar
    (Enter/ao sair); clicar seleciona o número para sobrescrever rápido.
    """

    def __init__(self, minimum: int = 1, maximum: int = 100000, value: int = 1) -> None:
        super().__init__()
        self.setRange(minimum, maximum)
        self.setValue(value)
        self.setKeyboardTracking(False)  # confirma no Enter/ao sair, não a cada tecla
        self.setFixedHeight(26)  # não estica na linha alta da tabela (evita ficar enorme)
        self.setToolTip("Digite a quantidade ou use as setas")


class ExportCenterDialog(QDialog):
    """Centro de Exportação: escolha visual das chapas (miniaturas + checkbox),
    previa da chapa em foco e formato (PDF impressao / DXF corte / Faca PDF /
    Imagem). Reusa os exportadores do MainWindow; aqui só e a parte de UI."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self._w = window
        self.setWindowTitle("Centro de Exportação")
        self.setMinimumSize(720, 480)

        sheets = window._effective_sheets()
        pre = set(window._selected_sheet_indices())  # chapas selecionadas no canvas
        self._sel_export = window._selection_export_sheets()  # (sheets, (w,h)) ou None

        root = QHBoxLayout(self)
        root.setContentsMargins(theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD)
        root.setSpacing(theme.SPACE_MD)

        # ---- esquerda: lista de chapas com miniatura + checkbox ----
        left = QVBoxLayout()
        left.setSpacing(theme.SPACE_SM)
        head = QHBoxLayout()
        title = QLabel("Chapas")
        title.setStyleSheet(f"font-weight:600; color:{theme.TEXT};")
        head.addWidget(title)
        head.addStretch()
        btn_all = QPushButton("Todas")
        btn_none = QPushButton("Nenhuma")
        for b in (btn_all, btn_none):
            b.setProperty("role", "caption")
            head.addWidget(b)
        left.addLayout(head)

        self._checks: list[QCheckBox] = []
        list_host = QWidget()
        list_lay = QVBoxLayout(list_host)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(theme.SPACE_SM)
        for i, layout in enumerate(sheets):
            row = QFrame()
            row.setObjectName("card")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(theme.SPACE_SM, theme.SPACE_SM, theme.SPACE_SM, theme.SPACE_SM)
            thumb = QLabel()
            thumb.setPixmap(window._sheet_thumbnail(i, 64))
            thumb.setFixedWidth(70)
            rl.addWidget(thumb)
            chk = QCheckBox(
                f"Chapa {i + 1}\n{units.fmt_len(layout.material.width, with_unit=False)} x "
                f"{units.fmt_len(layout.used_length)}  ·  {layout.item_count} peça(s)"
            )
            chk.setChecked(i in pre or not pre)  # selecionadas no canvas; senao todas
            chk.toggled.connect(self._sync_options)
            # mexer numa chapa = quero exportar chapas -> troca do modo "seleção"
            # (clicked so dispara por interacao do usuario, nao no setChecked)
            chk.clicked.connect(self._pick_sheets_mode)
            self._checks.append(chk)
            rl.addWidget(chk, 1)
            list_lay.addWidget(row)
        list_lay.addStretch()
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(list_host)
        left.addWidget(self._scroll, 1)
        root.addLayout(left, 1)

        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none.clicked.connect(lambda: self._set_all(False))

        # ---- direita: previa + formato + opções ----
        right = QVBoxLayout()
        right.setSpacing(theme.SPACE_SM)
        prev_card = CollapsibleCard("Pre-visualização", accent="produção")
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setMinimumHeight(220)
        self._preview.setStyleSheet(f"background:{theme.SURFACE_ALT}; border-radius:6px;")
        prev_card.body.addWidget(self._preview)
        right.addWidget(prev_card)

        # medidas do que será exportado
        self._dims = QLabel()
        self._dims.setProperty("role", "caption")
        right.addWidget(self._dims)

        # o que exportar: chapas marcadas ou apenas a seleção (estilo Corel)
        self._mode_sel = QRadioButton()
        self._mode_sheets = QRadioButton("Chapas marcadas")
        if self._sel_export is not None:
            n = len(self._w._selected_pieces())
            self._mode_sel.setText(f"Apenas a seleção ({n} peça(s))")
            mode_box = QGroupBox("O que exportar")
            mb = QVBoxLayout(mode_box)
            mb.addWidget(self._mode_sel)
            mb.addWidget(self._mode_sheets)
            right.addWidget(mode_box)
            self._mode_sel.setChecked(True)  # com seleção, exporta só ela por padrão
            self._mode_sel.toggled.connect(lambda *_: self._sync_options())
        else:
            self._mode_sheets.setChecked(True)

        fmt_box = QGroupBox("Formato")
        fmt_lay = QVBoxLayout(fmt_box)
        self._fmt_group = QButtonGroup(self)
        self._fmt_buttons = {}
        for key, text in [
            ("pdf", "PDF de impressao"),
            ("dxf", "DXF de corte"),
            ("faca", "Faca em PDF (linhas de corte)"),
            ("img", "Imagem (PNG / JPG)"),
        ]:
            rb = QRadioButton(text)
            self._fmt_group.addButton(rb)
            self._fmt_buttons[key] = rb
            fmt_lay.addWidget(rb)
        self._fmt_buttons["pdf"].setChecked(True)
        self._fmt_group.buttonToggled.connect(lambda *_: self._sync_options())
        right.addWidget(fmt_box)

        # opções especificas
        self._opt_dxf_per = QCheckBox("Um arquivo DXF por chapa")
        right.addWidget(self._opt_dxf_per)
        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("DPI da imagem"))
        self._opt_dpi = _spin(30, 1200)
        self._opt_dpi.setValue(int(window._settings.export_dpi))
        dpi_row.addWidget(self._opt_dpi)
        dpi_row.addStretch()
        self._dpi_host = QWidget()
        self._dpi_host.setLayout(dpi_row)
        right.addWidget(self._dpi_host)
        right.addStretch()

        buttons = QDialogButtonBox(parent=self)
        self._btn_export = buttons.addButton("Exportar", QDialogButtonBox.AcceptRole)
        self._btn_export.setProperty("accent", "true")
        buttons.addButton("Fechar", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._do_export)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)
        root.addLayout(right, 1)

        self._sync_options()
        self._update_preview()

    def _set_all(self, on: bool) -> None:
        self._pick_sheets_mode()  # usar Todas/Nenhuma = exportar chapas
        for chk in self._checks:
            chk.setChecked(on)

    def _pick_sheets_mode(self, *_) -> None:
        """Tocar na lista de chapas troca do modo 'Apenas a seleção' para
        'Chapas marcadas' (senao a lista fica inerte e confunde)."""
        if self._sel_export is not None and not self._mode_sheets.isChecked():
            self._mode_sheets.setChecked(True)

    def _checked_indices(self) -> list[int]:
        return [i for i, chk in enumerate(self._checks) if chk.isChecked()]

    def _current_format(self) -> str:
        for key, rb in self._fmt_buttons.items():
            if rb.isChecked():
                return key
        return "pdf"

    def _selection_mode(self) -> bool:
        return self._sel_export is not None and self._mode_sel.isChecked()

    def _sync_options(self, *_) -> None:
        fmt = self._current_format()
        sel = self._selection_mode()
        self._opt_dxf_per.setVisible(fmt == "dxf" and not sel)  # não se aplica a seleção
        self._dpi_host.setVisible(fmt == "img")
        # a lista de chapas fica SEMPRE interativa: mexer nela troca para o modo
        # "Chapas marcadas" (antes ela era desabilitada e nao dava p/ desmarcar).
        self._update_dims()
        self._update_preview()

    def _update_dims(self) -> None:
        if self._selection_mode():
            _, (w, h) = self._sel_export
        else:
            idxs = self._checked_indices()
            if not idxs:
                self._dims.setText("")
                return
            if len(idxs) > 1:
                self._dims.setText(f"Exportar: {len(idxs)} chapas")
                return
            s = self._w._effective_sheets()[idxs[0]]
            w, h = s.material.width, s.used_length
        self._dims.setText(
            f"Tamanho: {units.fmt_len(w, with_unit=False)} x {units.fmt_len(h)}"
        )

    def _update_preview(self, *_) -> None:
        if self._selection_mode():
            pm = self._w._selection_thumbnail(360)
            if pm.isNull():
                self._preview.setText("Seleção vazia.")
            else:
                self._preview.setPixmap(pm)
            return
        idxs = self._checked_indices()
        if not idxs:
            self._preview.setText("Selecione ao menos uma chapa.")
            return
        self._preview.setPixmap(self._w._sheet_thumbnail(idxs[0], 360))

    def _do_export(self) -> None:
        fmt = self._current_format()
        if self._selection_mode():
            synthetic, _ = self._sel_export
            self.accept()
            if fmt == "pdf":
                self._w.export_pdf(sheets_override=synthetic)
            elif fmt == "faca":
                self._w.export_faca_pdf(sheets_override=synthetic)
            elif fmt == "img":
                self._w.export_image(sheets_override=synthetic, dpi=int(self._opt_dpi.value()))
            elif fmt == "dxf":
                self._w.export_dxf(sheets_override=synthetic)
            return
        idxs = self._checked_indices()
        if not idxs:
            QMessageBox.warning(self, "PrintNest", "Selecione ao menos uma chapa.")
            return
        self.accept()
        if fmt == "pdf":
            self._w.export_pdf(pages=idxs)
        elif fmt == "faca":
            self._w.export_faca_pdf(pages=idxs)
        elif fmt == "img":
            self._w.export_image(pages=idxs, dpi=int(self._opt_dpi.value()))
        elif fmt == "dxf":
            if self._opt_dxf_per.isChecked():
                self._w.export_dxf_per_sheet(pages=idxs)
            else:
                self._w.export_dxf(pages=idxs)


def _guard_export(method):
    """Decorator das ações de exportar: QUALQUER falha vira dialogo amigavel.

    Sem isso, um erro de disco/permissao/caminho (inclusive as exceções novas
    do PyMuPDF >= 1.26) subia cru e, no executavel (sem console), o clique em
    Exportar simplesmente "não fazia nada" (bug QA-02). Última linha de defesa
    da UI — os exportadores continuam levantando erros tipados normalmente.
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:  # última defesa: mostrar, nunca silenciar
            QMessageBox.critical(self, "PrintNest", f"Falha ao exportar:\n{exc}")
            return None
    return wrapper


class MainWindow(QMainWindow):
    """Tela única do MVP PrintNest, organizada por categorias."""

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
        # MaxRects = maximo aproveitamento (preenche os vaos). O grid (em linhas)
        # só e usado na faca compartilhada, que precisa das peças alinhadas.
        self._nesting_uc = RunGridNestingUseCase(MaxRectsPacker())
        self._grid_nesting_uc = RunGridNestingUseCase()

        self._paths: list[str] = []
        self._base_artworks: list = []
        self._sources: dict[str, tuple[str, int]] = {}
        self._origins: dict[str, str] = {}  # id da arte -> caminho original (quantidade)
        self._pixmaps: dict[tuple[str, int], QPixmap] = {}
        self._thumb_cache: dict[str, QIcon] = {}
        self._loaded = False
        self._suspend_relayout = False  # agrupa várias mudancas num só relayout
        self._suspend_undo = False  # ao gerar/abrir, não registra passo de desfazer
        self._faca_on = False  # faca só e gerada ao clicar "Gerar Faca"/"Gerar Produção"
        self._move_before = None  # snapshot do arranjo no inicio de um arraste
        self._guides: list[tuple[bool, float]] = []  # (horizontal, valor_mm)
        self._guide_preview_item = None
        # faca por arquivo: caminho -> params proprios (override). Sem override,
        # o arquivo segue o padrão do painel Documento.
        self._file_overrides: dict[str, dict] = {}
        # tamanho por arquivo: caminho -> Size (mm) desejado. Sem entrada, o
        # arquivo mantem o tamanho original importado. Aplicado na arte base
        # antes da faca (escala arte + contornos); vale para todas as cópias.
        self._file_sizes: dict[str, Size] = {}
        # rotação POR PECA: artwork_id -> giro extra (0/90/180/270) somado ao
        # giro do arquivo. Permite girar só uma peça (ex.: a sobra solta) para
        # encaixar melhor no nesting, sem mexer nas outras cópias/páginas.
        self._piece_rotations: dict[str, int] = {}
        # centralizar o conteudo na LARGURA da chapa (margens iguais). A chapa
        # cresce/diminui no comprimento conforme adiciona/remove peças.
        self._center_on_sheet = True
        self._pbar_loading = False  # evita loop ao popular a barra de propriedades
        self._faca_corner = "round"  # canto da faca (contorno): round/miter/bevel
        self._ct_loading = False  # evita loop ao sincronizar a toolbar de contorno
        # abas de trabalho (multi-projeto, estilo CorelDRAW): cada aba guarda um
        # snapshot completo da sessao; trocar de aba salva a atual e restaura a outra.
        self._sessions: list = []
        self._active_tab = 0
        self._switching_tab = False
        self._tab_counter = 1
        self._ps_loading = False  # evita reentrancia ao carregar os campos
        # recorte de página (por arquivo/página): caminho -> {página: (l,t,r,b) mm}.
        # Aplicado "assando" um PDF recortado em cache; o resto do fluxo não muda.
        self._page_crops: dict[str, dict[int, tuple]] = {}
        self._baked_crops: dict = {}      # (caminho, assinatura) -> PDF recortado em cache
        self._crop_cache: dict[str, str] = {}  # PDF recortado -> caminho original
        # faca "pelo contorno" de PDF: detecta o contorno da página rasterizada.
        self._contour_detector = Cv2ImageImporter()
        self._pdf_contours: dict = {}  # (caminho, página) -> contorno detectado
        # faca "do cliente" (vetor do PDF): usa o contorno vetorial enviado.
        self._vector_extractor = PyMuPdfVectorExtractor()
        self._vector_generator = VectorContourGenerator()
        self._vector_contours: dict = {}  # (caminho, página) -> contorno vetorial | None
        self._faca_notice: tuple[str, str] | None = None  # (nivel, texto) da detecção
        self._selected_path: str | None = None
        self._selected_is_image = False
        self._pf_loading = False        # carregando controles da peça (não gravar)
        self._keep_tab = False          # não trocar de aba durante reselecao
        self._result: ProductionResult | None = None
        self._thread: QThread | None = None
        self._worker: ProductionWorker | None = None
        self._piece_items: list = []
        self._decor_items: list = []  # itens decorativos da cena (evita GC)
        self._resize_handles: list = []  # alças de redimensionar (peça selecionada)
        self._resize_preview = None      # retângulo tracejado durante o arraste
        self._ghost_items: list = []  # previews "fantasma" da aba Transformar
        self._transform_mode = "dup"  # último preview: "dup" ou "grid"
        self._suppress_ghost = False  # não redesenhar fantasmas durante o "aplicar"
        self._undo = QUndoStack(self)
        self._undo.setUndoLimit(0)  # ilimitado (CorelDRAW): só zera ao gerar/abrir/novo
        self._fit_next = True  # ajusta o zoom só após gerar; preserva no relayout
        self._snap = SnapConfig()
        self._project_store = ProjectStore()
        self._project_path: str | None = None

        # unidade definida ANTES de montar a UI, para os campos já nascerem na
        # unidade certa (LengthSpin le units.unit() ao ser criado).
        units.set_unit(getattr(settings, "unit", units.CM))

        self.setWindowTitle("PrintNest Premium")
        self._build_ui()
        self._load_settings()
        self._update_property_bar()  # mostra o Projeto (material) já na abertura
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
        abrir = self._act("Abrir Projeto...", self.open_project, "Ctrl+O",
                          "Abre um projeto .printnest salvo")
        salvar = self._act("Salvar Projeto", self.save_project, "Ctrl+S",
                           "Salva o projeto atual")
        salvar_como = self._act("Salvar Como...", self.save_project_as, "Ctrl+Shift+S",
                                "Salva o projeto em um novo arquivo")
        fechar_aba = self._act("Fechar trabalho",
                               lambda: self._close_tab(self._tabbar.currentIndex()),
                               "Ctrl+W", "Fecha a aba de trabalho atual")
        add = self._act("Adicionar arquivos...", self.add_pdfs, "Ctrl+I",
                        "Importa arquivos (PDF/imagens) para a lista")
        substituir = self._act("Substituir arquivo selecionado...", self.replace_selected, None,
                               "Troca o arquivo da linha selecionada (ex.: arquivo não encontrado)")
        gerar = self._act("Gerar Produção", self.generate, "F5",
                          "Importa, gera a faca e organiza o nesting")
        gerar_faca = self._act("Gerar Faca", self._regenerate_faca, "Shift+F5",
                               "Recria a faca das peças (refaz a detecção da faca do cliente)")
        fit = self._act("Ajustar a tela", self._fit_view, "F4",
                        "Enquadra todo o trabalho na tela (F4 ou Ctrl+0)")
        fit.setShortcuts([QKeySequence("F4"), QKeySequence("Ctrl+0")])
        undo = self._act("Desfazer", self._undo.undo, "Ctrl+Z",
                         "Desfaz a última ação (mover, excluir, duplicar, repetir)")
        redo = self._act("Refazer", self._undo.redo, "Ctrl+Y", "Refaz a ação desfeita")
        redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        rot_l = self._act("Girar 90 a esquerda", lambda: self._rotate_selected(-90), "Ctrl+[",
                          "Gira o arquivo selecionado 90 graus anti-horario (re-encaixa)")
        rot_r = self._act("Girar 90 a direita", lambda: self._rotate_selected(90), "Ctrl+]",
                          "Gira o arquivo selecionado 90 graus horario (re-encaixa)")
        grp = self._act("Agrupar", self._group_selected, "Ctrl+G",
                        "Agrupa as peças selecionadas")
        ungrp = self._act("Desagrupar", self._ungroup_selected, "Ctrl+U",
                          "Desagrupa as peças")
        sel_all = self._act("Selecionar tudo", self._select_all, "Ctrl+A",
                            "Seleciona todas as peças na área de trabalho")
        excluir = self._act("Excluir selecionado", self._delete_selected, "Del",
                            "Exclui as peças selecionadas do arranjo")
        organizar = self._act("Organizar (nesting)", self._organize, "Ctrl+L",
                              "Reorganiza as peças na chapa mantendo a quantidade atual")
        reset = self._act("Resetar arranjo", self._reset_arrangement, None,
                          "Refaz o nesting do zero (descarta ajustes manuais)")
        rem = self._act("Remover PDF selecionado", self.remove_selected, None,
                        "Remove o PDF selecionado da lista")
        dup = self._act("Duplicar", self._duplicate_selected, "Ctrl+D",
                        "Duplica as peças selecionadas com um pequeno deslocamento")
        dup_qty = self._act("Duplicar só esta página...", self._duplicate_selected_qty,
                            "Ctrl+Shift+C",
                            "Duplica SO a(s) página(s) selecionada(s) na quantidade "
                            "escolhida e re-encaixa (não duplica o PDF inteiro)")
        step = self._act("Repetir em grade...", self._step_repeat_dialog, "Ctrl+Shift+D",
                         "Cria várias cópias em linhas e colunas (step and repeat)")
        # atalhos de uma letra (padrão CorelDRAW): T/B/L/R/C/E. Seguros: campos
        # de texto/número tem prioridade sobre eles enquanto digitando.
        al_l = self._act("Alinhar a esquerda", lambda: self._align("left"), "L",
                         "Alinha as bordas esquerdas das peças selecionadas")
        al_r = self._act("Alinhar a direita", lambda: self._align("right"), "R",
                         "Alinha as bordas direitas")
        al_t = self._act("Alinhar ao topo", lambda: self._align("top"), "T",
                         "Alinha as bordas superiores")
        al_b = self._act("Alinhar a base", lambda: self._align("bottom"), "B",
                         "Alinha as bordas inferiores")
        al_cx = self._act("Centralizar na vertical", lambda: self._align("hcenter"), "C",
                          "Alinha os centros numa mesma linha vertical")
        al_cy = self._act("Centralizar na horizontal", lambda: self._align("vcenter"), "E",
                          "Alinha os centros numa mesma linha horizontal")
        dist_h = self._act("Distribuir na horizontal", lambda: self._distribute("h"), None,
                           "Espaca as peças igualmente na horizontal")
        dist_v = self._act("Distribuir na vertical", lambda: self._distribute("v"), None,
                           "Espaca as peças igualmente na vertical")
        snap_act = QAction("Encaixar (snap)", self)
        snap_act.setCheckable(True)
        snap_act.setChecked(self._snap.enabled)
        snap_act.setShortcut(QKeySequence("Alt+Q"))
        snap_act.setToolTip("Liga/desliga o encaixe ao arrastar peças")
        snap_act.toggled.connect(self._set_snap)
        self._snap_action = snap_act
        center_act = QAction("Centralizar na chapa", self)
        center_act.setCheckable(True)
        center_act.setChecked(self._center_on_sheet)
        center_act.setToolTip(
            "Mantem o conteudo centralizado na largura da chapa (margens iguais)"
        )
        center_act.toggled.connect(self._set_center_on_sheet)
        self._center_action = center_act
        to_front = self._act("Trazer para frente", self._bring_to_front, "Shift+PgUp",
                             "Coloca as peças selecionadas a frente das demais")
        to_back = self._act("Enviar para tras", self._send_to_back, "Shift+PgDown",
                            "Envia as peças selecionadas para tras das demais")
        exp_center = self._act("Centro de Exportação...", self._open_export_center, "Ctrl+E",
                               "Escolhe as chapas (com previa) e o formato de exportação")
        exp_pdf = self._act("Exportar PDF de impressao...", self.export_pdf, "Ctrl+P",
                            "Gera o PDF de impressao (Imprimir)")
        exp_dxf = self._act("Exportar DXF (único)...", self.export_dxf, None,
                            "Gera um DXF com todas as chapas")
        exp_dxf_n = self._act("Exportar DXF por chapa...", self.export_dxf_per_sheet, None,
                              "Gera um arquivo DXF para cada chapa")
        exp_faca_pdf = self._act("Exportar Faca (PDF)...", self.export_faca_pdf, None,
                                 "Gera um PDF só com a faca (linhas de corte)")
        exp_img = self._act("Exportar Imagem (PNG/JPEG)...", self.export_image, None,
                            "Rasteriza a impressao em imagem, no DPI escolhido")
        sair = self._act("Sair", self.close, None, "Fecha o programa")
        sobre = self._act("Sobre", self._show_about, None, "Sobre o PrintNest")

        bar = self.menuBar()
        m_arq = bar.addMenu("&Arquivo")
        for action in (novo, abrir, salvar, salvar_como, fechar_aba,
                       None, add, substituir,
                       None, exp_center,
                       None, exp_pdf, exp_dxf, exp_dxf_n, exp_faca_pdf, exp_img,
                       None, sair):
            m_arq.addSeparator() if action is None else m_arq.addAction(action)
        obj_props = self._act("Propriedades do objeto", self._show_object_props,
                              "Alt+Return",
                              "Abre a aba Objeto (medidas e faca da peça selecionada)")
        copiar = self._act("Copiar", self._copy_selected, "Ctrl+C",
                           "Copia as peças selecionadas")
        colar = self._act("Colar", self._paste_clipboard, "Ctrl+V",
                          "Cola as peças copiadas (deslocadas; Ctrl+D continua a serie)")
        m_edit = bar.addMenu("&Editar")
        for action in (undo, redo, None, copiar, colar, None,
                       rot_l, rot_r, None, sel_all, dup, dup_qty, step,
                       grp, ungrp, None, obj_props, None, excluir, reset, rem):
            m_edit.addSeparator() if action is None else m_edit.addAction(action)
        m_org = bar.addMenu("&Organizar")
        for action in (organizar, center_act, None, grp, ungrp, None, to_front, to_back,
                       None, al_l, al_r, al_t, al_b, al_cx, al_cy,
                       None, dist_h, dist_v, None, snap_act):
            m_org.addSeparator() if action is None else m_org.addAction(action)
        limpar_guias = self._act("Limpar guias", self._clear_guides, None,
                                  "Remove todas as guias da área de trabalho")
        # zoom e navegacao (padrão CorelDRAW): F2/F3, Shift+F2/F4, H, Alt+setas
        zoom_in = self._act("Zoom +", lambda: self._zoom_step(1.15), "F2",
                            "Aproxima a visualização")
        zoom_out = self._act("Zoom −", lambda: self._zoom_step(1 / 1.15), "F3",
                             "Afasta a visualização")
        zoom_page = self._act("Zoom na página", self._zoom_page, "Shift+F4",
                              "Enquadra a primeira chapa na tela")
        zoom_sel = self._act("Zoom na seleção", self._zoom_selection, "Shift+F2",
                             "Enquadra as peças selecionadas na tela")
        hand = QAction("Ferramenta mao (pan)", self)
        hand.setCheckable(True)
        hand.setShortcut(QKeySequence("H"))
        hand.setToolTip("Arrastar a tela com o botão esquerdo (o do meio sempre faz pan)")
        hand.toggled.connect(self._set_hand_tool)
        for dx, dy, keys in ((-60, 0, "Alt+Left"), (60, 0, "Alt+Right"),
                             (0, -60, "Alt+Up"), (0, 60, "Alt+Down")):
            pan = self._act(f"Pan {keys}", lambda dx=dx, dy=dy: self._pan_view(dx, dy),
                            keys, "Desloca a visualização")
            pan.setVisible(False)  # só atalho (não aparece em menu)
            self.addAction(pan)

        m_exib = bar.addMenu("E&xibir")
        m_exib.addAction(fit)
        for action in (zoom_in, zoom_out, zoom_page, zoom_sel, None, hand, None,
                       limpar_guias):
            m_exib.addSeparator() if action is None else m_exib.addAction(action)
        m_ferr = bar.addMenu("&Ferramentas")
        m_ferr.addAction(gerar)
        m_ferr.addAction(gerar_faca)

        # Opções (ao lado de Ajuda): unidade de medida (cm/mm)
        m_opt = bar.addMenu("O&pções")  # Alt+P (Alt+O já e do menu Organizar; QA-09)
        um = m_opt.addMenu("Unidade de medida")
        self._unit_group = QActionGroup(self)
        self._unit_group.setExclusive(True)
        self._act_unit_cm = QAction("Centímetros (cm)", self, checkable=True)
        self._act_unit_cm.setData(units.CM)
        self._act_unit_mm = QAction("Milímetros (mm)", self, checkable=True)
        self._act_unit_mm.setData(units.MM)
        for a in (self._act_unit_cm, self._act_unit_mm):
            self._unit_group.addAction(a)
            a.triggered.connect(lambda _=False, act=a: self._on_unit_changed(act.data()))
            um.addAction(a)
        # marca a unidade atual (já definida a partir das configurações)
        self._act_unit_mm.setChecked(units.unit() == units.MM)
        self._act_unit_cm.setChecked(units.unit() != units.MM)

        licenca = self._act("Licença...", self._show_license, None,
                             "Ativar / ver / transferir a licenca do PrintNest")
        m_ajuda = bar.addMenu("A&juda")
        m_ajuda.addAction(licenca)
        m_ajuda.addAction(sobre)

        # icones nas ações (aparecem no menu e na ribbon)
        for action, name in (
            (novo, "file-plus"), (abrir, "folder-open"), (salvar, "save"),
            (salvar_como, "save"), (add, "plus"), (substituir, "replace"),
            (gerar, "zap"), (gerar_faca, "scissors"),
            (fit, "maximize"), (undo, "undo-2"), (redo, "redo-2"),
            (rot_l, "rotate-ccw"), (rot_r, "rotate-cw"),
            (grp, "group"), (ungrp, "ungroup"), (sel_all, "layers"), (excluir, "trash-2"),
            (organizar, "grid-3x3"), (reset, "rotate-ccw"), (rem, "trash-2"),
            (dup, "copy"), (step, "grid-3x3"),
            (al_l, "align-horizontal-justify-start"), (al_r, "align-horizontal-justify-end"),
            (al_t, "align-vertical-justify-start"), (al_b, "align-vertical-justify-end"),
            (al_cx, "align-horizontal-justify-center"), (al_cy, "align-vertical-justify-center"),
            (dist_h, "align-horizontal-justify-center"),
            (dist_v, "align-vertical-justify-center"),
            (to_front, "align-vertical-justify-start"),
            (to_back, "align-vertical-justify-end"),
            (exp_center, "download"),
            (exp_pdf, "download"), (exp_dxf, "download"), (exp_dxf_n, "download"),
            (exp_faca_pdf, "download"), (exp_img, "image"),
        ):
            action.setIcon(icons.icon(name))

        # ações guardadas para habilitar/desabilitar conforme o estado
        self._act_generate = gerar
        self._export_actions = [exp_center, exp_pdf, exp_dxf, exp_dxf_n, exp_faca_pdf, exp_img]
        for action in self._export_actions:
            action.setEnabled(False)

        # toggle de réguas espelhando o checkbox de Exibição
        reguas = QAction("Réguas", self)
        reguas.setCheckable(True)
        reguas.setChecked(self._show_rulers.isChecked())
        reguas.setIcon(icons.icon("ruler"))
        reguas.toggled.connect(self._show_rulers.setChecked)

        # botão "Exibição" na barra: abre um popup com os controles de exibição
        disp_btn = QToolButton()
        disp_btn.setText("Exibição")
        disp_btn.setIcon(icons.icon("eye", theme.ICON, 18))
        disp_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        disp_btn.setPopupMode(QToolButton.InstantPopup)
        disp_btn.setCursor(Qt.PointingHandCursor)
        disp_btn.setToolTip("Unidade, modo de visualização, réguas e encaixe")
        disp_menu = QMenu(disp_btn)
        disp_action = QWidgetAction(disp_menu)
        disp_action.setDefaultWidget(self._display_panel)
        disp_menu.addAction(disp_action)
        disp_btn.setMenu(disp_menu)

        tb = ribbon_panel
        rb = QToolBar("Ribbon")
        rb.setObjectName("ribbon")
        rb.setIconSize(QSize(18, 18))
        ribbon_panel.populate_ribbon(rb, [
            ("Arquivo", [
                tb.tool_button(novo, "file-plus", show_text=False),
                tb.tool_button(abrir, "folder-open", show_text=False),
                tb.tool_button(salvar, "save", show_text=False),
                # "Adicionar arquivos" fica so na biblioteca (evita duplicidade);
                # continua no menu Arquivo e no atalho Ctrl+I.
            ]),
            ("Editar", [
                tb.tool_button(undo, "undo-2", show_text=False),
                tb.tool_button(redo, "redo-2", show_text=False),
                tb.tool_button(rot_l, "rotate-ccw", show_text=False),
                tb.tool_button(rot_r, "rotate-cw", show_text=False),
                tb.tool_button(dup, "copy", show_text=False),
                tb.tool_button(step, "grid-3x3", show_text=False),
                tb.tool_button(excluir, "trash-2", show_text=False),
            ]),
            ("Organizar", [
                tb.tool_button(organizar, "grid-3x3"),
                tb.tool_button(grp, "group", show_text=False),
                tb.tool_button(ungrp, "ungroup", show_text=False),
                tb.tool_button(to_front, "align-vertical-justify-start", show_text=False),
                tb.tool_button(to_back, "align-vertical-justify-end", show_text=False),
                tb.menu_button("Alinhar", "align-horizontal-justify-start",
                               [al_l, al_r, al_t, al_b, al_cx, al_cy], tip="Alinhar peças"),
                tb.menu_button("Distribuir", "align-horizontal-justify-center",
                               [dist_h, dist_v], tip="Distribuir igualmente"),
                tb.tool_button(snap_act, "magnet", show_text=False),
            ]),
            ("Produção", [
                self._faca_mode_ribbon_widget(),  # Tipo de faca ao lado do botão
                tb.tool_button(gerar_faca, "scissors", accent=True),  # botão azul principal
                tb.tool_button(exp_center, "download"),
                tb.menu_button("Mais...", "download",
                               [exp_pdf, exp_dxf, exp_dxf_n, exp_faca_pdf, exp_img],
                               tip="Exportar formato especifico"),
            ]),
            ("Exibir", [
                tb.tool_button(fit, "maximize"),
                self._view_mode_menu_button(),  # visualização ao lado de Ajustar
                disp_btn,
                tb.tool_button(reguas, "ruler", show_text=False),
            ]),
        ])
        self.addToolBar(rb)

    def _view_mode_menu_button(self) -> QToolButton:
        """Botão 'Visualização' na barra (ao lado de Ajustar à tela): um menu com
        os 4 modos. Espelha o mesmo _view_mode da barrinha flutuante do canvas —
        mudar num lado marca o outro (fonte única de estado)."""
        btn = QToolButton()
        btn.setText("Visualização")
        btn.setIcon(icons.icon("eye", theme.ICON, 18))
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setPopupMode(QToolButton.InstantPopup)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Modo de visualização do canvas")
        menu = QMenu(btn)
        self._view_mode_group = QActionGroup(self)
        self._view_mode_group.setExclusive(True)
        self._view_mode_actions = {}
        for i in range(self._view_mode.count()):
            data = self._view_mode.itemData(i)
            act = QAction(self._view_mode.itemText(i), self, checkable=True)
            act.setChecked(i == self._view_mode.currentIndex())
            act.triggered.connect(
                lambda _=False, d=data: self._view_mode.setCurrentIndex(
                    self._view_mode.findData(d)
                )
            )
            self._view_mode_group.addAction(act)
            self._view_mode_actions[data] = act
            menu.addAction(act)
        btn.setMenu(menu)
        self._view_mode.currentIndexChanged.connect(self._sync_view_mode_menu)
        return btn

    def _sync_view_mode_menu(self) -> None:
        act = self._view_mode_actions.get(self._view_mode.currentData())
        if act is not None:
            act.setChecked(True)

    def _faca_mode_ribbon_widget(self) -> QWidget:
        """Widget da barra: rotulo discreto + combo "Tipo de faca", colado ao
        botão Gerar Faca (decidir o tipo e gerar viram um gesto só). E o MESMO
        combo de sempre (self._faca_mode): estado, sessao e testes intactos."""
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(theme.SPACE_XS, 0, theme.SPACE_XS, 0)
        lay.setSpacing(theme.SPACE_SM)
        cap = QLabel("Tipo de faca")
        cap.setProperty("role", "caption")
        lay.addWidget(cap)
        # largura folgada: a opção mais longa ("Faca do cliente (vetor do PDF)")
        # precisa caber SEM reticências também fechada (auditoria QA #1)
        self._faca_mode.setMinimumWidth(200)
        self._faca_mode.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        lay.addWidget(self._faca_mode)
        return box

    def _show_license(self) -> None:
        """Ajuda -> Licenca: ativar/ver/transferir (nao bloqueia o uso aqui)."""
        from app.licensing.manager import LicenseManager
        from app.presentation.licensing_dialog import ActivationDialog
        from app.shared.config.paths import AppPaths
        ActivationDialog(LicenseManager(AppPaths.default()), self).exec()

    def _show_about(self) -> None:
        from app import __version__
        QMessageBox.about(
            self, "PrintNest Premium",
            f"<b>PrintNest Premium</b> — versão {__version__}<br><br>"
            "Preparação de produção gráfica: faca, nesting e "
            "exportação PDF/DXF.",
        )

    # ---- projeto (.printnest) ----
    def _update_title(self) -> None:
        from app import __version__
        name = Path(self._project_path).name if self._project_path else "Sem título"
        self.setWindowTitle(f"PrintNest Premium v{__version__} — {name}")

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
        """Restaura o estado do projeto SEM gerar produção (regra do projeto)."""
        for key, value in doc.settings.items():
            if key in PROJECT_SETTING_KEYS and hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self._load_settings()  # empurra os parametros para os widgets
        self._reset_project_state()
        self._populate_files(doc.files)

    def _reset_project_state(self) -> None:
        """Descarta a produção carregada (mantem parametros e widgets)."""
        self._loaded = False
        self._result = None
        self._base_artworks = []
        self._sources = {}
        self._pixmaps = {}
        self._piece_items = []
        self._scene.clear()
        self._undo.clear()
        self._set_exports_enabled(False)
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
        item.setForeground(QColor(theme.ERROR))
        item.setText(f"⚠ {item.text()}")
        item.setToolTip("Arquivo não encontrado. Use 'Substituir arquivo' ou remova a linha.")

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
        self._thumb_cache.pop(path, None)
        item = QTableWidgetItem(f"{Path(path).name}\n{self._file_type(path)}")
        item.setIcon(self._thumbnail(path))
        self._table.setItem(row, 0, item)
        if self._loaded:
            self._relayout()

    def new_project(self) -> None:
        self._project_path = None
        self._reset_project_state()
        self._faca_on = False      # volta ao modo "soltar sem faca"
        self._file_overrides = {}  # descarta facas personalizadas por arquivo
        self._file_sizes = {}      # descarta tamanhos personalizados por arquivo
        self._piece_rotations = {}  # descarta giros por peça
        self._page_crops = {}      # descarta recortes de página
        self._baked_crops = {}
        self._crop_cache = {}
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
                f"{len(missing)} arquivo(s) não encontrado(s) (marcados em vermelho).\n"
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
        self._toasts.success("Projeto salvo")
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
        """Reabre o último projeto ao iniciar (silencioso; não quebra se faltar)."""
        last = self._settings.last_project
        if last and Path(last).exists():
            # nunca impedir a abertura do programa por causa de um projeto ruim
            with contextlib.suppress(Exception):
                self.open_project(last)

    # ==================== Barra de Propriedades contextual (V2.0 Fase A) =======
    def _build_property_bar(self) -> QWidget:
        """Barra horizontal abaixo da ribbon que muda com a seleção (estilo Corel):
        sem seleção -> Projeto; 1 peça -> Objeto (X/Y editaveis, L/A, girar,
        duplicar/excluir); várias -> Grupo (contagem, tamanho, alinhar/distribuir).

        Só UI: reusa _nudge (mover, com undo), _rotate_selected, _align,
        _distribute, _duplicate_selected, _delete_selected, _group_selected.
        """
        bar = QFrame()
        bar.setObjectName("propBar")
        bar.setFixedHeight(40)
        bar.setStyleSheet(
            f"#propBar{{background:{theme.SURFACE_ALT}; border:1px solid {theme.BORDER};"
            f" border-radius:8px;}}"
        )
        outer = QHBoxLayout(bar)
        outer.setContentsMargins(theme.SPACE_MD, 2, theme.SPACE_MD, 2)
        self._pbar_stack = QStackedWidget()
        outer.addWidget(self._pbar_stack, 1)
        outer.addWidget(self._build_contour_tool())  # ferramenta Contorno (faca)

        def _tag(text: str) -> QLabel:
            lb = QLabel(text)
            lb.setStyleSheet(f"font-weight:700; color:{theme.ACCENT};")
            return lb

        def _sep() -> QLabel:
            lb = QLabel("·")
            lb.setStyleSheet(f"color:{theme.TEXT_MUTED};")
            return lb

        # --- página 0: PROJETO (sem seleção) ---
        proj = QWidget()
        pl = QHBoxLayout(proj)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(theme.SPACE_MD)
        self._pb_proj_material = QLabel("—")
        self._pb_proj_pecas = QLabel("—")
        self._pb_proj_chapas = QLabel("—")
        pl.addWidget(_tag("📄 Projeto"))
        pl.addWidget(_sep())
        pl.addWidget(QLabel("Chapa:"))
        pl.addWidget(self._pb_proj_material)
        pl.addWidget(_sep())
        pl.addWidget(QLabel("Peças:"))
        pl.addWidget(self._pb_proj_pecas)
        pl.addWidget(_sep())
        pl.addWidget(QLabel("Chapas:"))
        pl.addWidget(self._pb_proj_chapas)
        pl.addStretch()
        self._pbar_stack.addWidget(proj)

        # --- página 1: OBJETO (1 peça) ---
        obj = QWidget()
        ol = QHBoxLayout(obj)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(theme.SPACE_SM)
        # medidas L x A do objeto: editaveis (mudar o tamanho pela numeracao)
        self._pb_w = LengthSpin(1, 20000)
        self._pb_h = LengthSpin(1, 20000)
        for sp in (self._pb_w, self._pb_h):
            sp.setFixedWidth(90)
        self._pb_w.editingFinished.connect(lambda: self._pbar_resize("w"))
        self._pb_h.editingFinished.connect(lambda: self._pbar_resize("h"))
        # cadeado: mantem a proporção ao mudar L/A ou arrastar as alças.
        self._pb_lock = QPushButton()
        self._pb_lock.setIcon(icons.icon("lock", theme.ICON))
        self._pb_lock.setCheckable(True)
        self._pb_lock.setChecked(True)
        self._pb_lock.setFixedSize(28, 28)
        self._pb_lock.setToolTip("Manter proporção ao redimensionar (arrastar as alças).")
        self._pb_lock.toggled.connect(lambda on: self._ps_lock.setChecked(on))
        b_rl = QPushButton()
        b_rl.setIcon(icons.icon("rotate-ccw", theme.ICON))
        b_rl.setToolTip("Girar -90° (só a peça)")
        b_rl.clicked.connect(lambda: self._rotate_selected(-90))
        b_rr = QPushButton()
        b_rr.setIcon(icons.icon("rotate-cw", theme.ICON))
        b_rr.setToolTip("Girar +90° (só a peça)")
        b_rr.clicked.connect(lambda: self._rotate_selected(90))
        b_dup = QPushButton("  Duplicar")
        b_dup.setIcon(icons.icon("copy", theme.ICON))
        b_dup.clicked.connect(self._duplicate_selected)
        b_del = QPushButton("  Excluir")
        b_del.setIcon(icons.icon("trash-2", theme.ICON))
        b_del.clicked.connect(self._delete_selected)
        ol.addWidget(_tag("⬚ Objeto"))
        ol.addWidget(_sep())
        ol.addWidget(QLabel("L"))
        ol.addWidget(self._pb_w)
        ol.addWidget(self._pb_lock)
        ol.addWidget(QLabel("A"))
        ol.addWidget(self._pb_h)
        ol.addWidget(_sep())
        ol.addWidget(b_rl)
        ol.addWidget(b_rr)
        ol.addStretch()
        ol.addWidget(b_dup)
        ol.addWidget(b_del)
        self._pbar_stack.addWidget(obj)

        # --- página 2: GRUPO (várias peças) ---
        grp = QWidget()
        gl = QHBoxLayout(grp)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(theme.SPACE_SM)
        self._pb_grp_count = QLabel("—")
        self._pb_grp_size = QLabel("—")
        b_align = QPushButton("  Alinhar")
        b_align.setIcon(icons.icon("align-horizontal-justify-start", theme.ICON))
        m_align = QMenu(b_align)
        for label, mode in (
            ("À esquerda", "left"), ("Centralizar horizontal", "hcenter"),
            ("À direita", "right"), ("Ao topo", "top"),
            ("Centralizar vertical", "vcenter"), ("À base", "bottom"),
        ):
            m_align.addAction(label, lambda _=False, m=mode: self._align(m))
        b_align.setMenu(m_align)
        b_dist = QPushButton("  Distribuir")
        b_dist.setIcon(icons.icon("align-horizontal-justify-center", theme.ICON))
        m_dist = QMenu(b_dist)
        m_dist.addAction("Na horizontal", lambda: self._distribute("h"))
        m_dist.addAction("Na vertical", lambda: self._distribute("v"))
        b_dist.setMenu(m_dist)
        b_group = QPushButton("  Agrupar")
        b_group.setIcon(icons.icon("group", theme.ICON))
        b_group.clicked.connect(self._group_selected)
        gl.addWidget(_tag("▦ Grupo"))
        gl.addWidget(_sep())
        gl.addWidget(self._pb_grp_count)
        gl.addWidget(_sep())
        gl.addWidget(self._pb_grp_size)
        gl.addStretch()
        gl.addWidget(b_align)
        gl.addWidget(b_dist)
        gl.addWidget(b_group)
        self._pbar_stack.addWidget(grp)

        return bar

    def _build_contour_tool(self) -> QWidget:
        """Ferramenta 'Contorno' (faca), estilo CorelDRAW, fixa a direita da barra:
        Offset (mm) + Direção (externo/interno) + Cantos (redondo/ponta/chanfro).
        O offset controla a sangria da faca ao vivo; os cantos usam o join_style
        do offset. Não mexe em nesting/exportação."""
        w = QFrame()
        cl = QHBoxLayout(w)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(theme.SPACE_XS)
        tag = QLabel("✂ Contorno")
        tag.setStyleSheet(f"font-weight:700; color:{theme.ACCENT};")
        cl.addWidget(tag)

        self._ct_offset = LengthSpin(0, 100)
        self._ct_offset.setFixedWidth(90)
        self._ct_offset.setToolTip("Offset da faca: distância da linha de corte até a arte.")
        self._ct_offset.editingFinished.connect(self._apply_contour_offset)
        cl.addWidget(QLabel("Offset"))
        cl.addWidget(self._ct_offset)

        def _icon_btn(icon_name: str, tip: str, checked: bool = False) -> QPushButton:
            """Botão só-icone (estilo Corel): nome no tooltip, sem texto."""
            b = QPushButton()
            b.setIcon(icons.icon(icon_name, theme.ICON))
            b.setIconSize(QSize(18, 18))
            b.setCheckable(True)
            b.setChecked(checked)
            b.setFixedSize(30, 28)
            b.setToolTip(tip)
            return b

        self._ct_dir = QButtonGroup(self)
        b_out = _icon_btn("arrows-out", "Contorno externo\nFaca para FORA da arte (sangria).", True)
        b_in = _icon_btn("arrows-in", "Contorno interno\nFaca para DENTRO (recuo/vinco).")
        self._ct_dir.addButton(b_out, 1)   # externo (id 1; evita -1, sentinela do Qt)
        self._ct_dir.addButton(b_in, 2)    # interno
        self._ct_dir.buttonClicked.connect(lambda _: self._apply_contour_offset())
        cl.addWidget(b_out)
        cl.addWidget(b_in)

        sep = QLabel("·")
        sep.setStyleSheet(f"color:{theme.TEXT_MUTED};")
        cl.addWidget(sep)
        self._ct_corner = QButtonGroup(self)
        self._ct_corner_val = {}
        corners = (
            ("round", "corner-round",
             "Arredondar cantos\nCantos arredondados (padrão seguro para a lamina)."),
            ("miter", "corner-sharp",
             "Cantos com esquadria\nCanto vivo (ponta), limitado para não criar farpas."),
            ("bevel", "corner-bevel",
             "Chanfrar cantos\nCanto chanfrado (reto)."),
        )
        for i, (val, icon_name, tip) in enumerate(corners):
            b = _icon_btn(icon_name, tip, checked=(val == "round"))
            self._ct_corner.addButton(b, i)
            self._ct_corner_val[i] = val
            cl.addWidget(b)
        self._ct_corner.buttonClicked.connect(lambda _: self._apply_contour_corner())

        sep2 = QLabel("·")
        sep2.setStyleSheet(f"color:{theme.TEXT_MUTED};")
        cl.addWidget(sep2)
        self._ct_smooth = _spin(0, 5)
        self._ct_smooth.setFixedWidth(52)
        self._ct_smooth.setToolTip("Suavizar curvas da faca: 0 = reto, 5 = macio.")
        self._ct_smooth.valueChanged.connect(lambda _: self._apply_contour_smooth())
        cl.addWidget(QLabel("Suavizar"))
        cl.addWidget(self._ct_smooth)
        return w

    def _apply_contour_smooth(self) -> None:
        """Suavizar (barra) -> grava no campo global do Documento e re-gera a faca."""
        if self._ct_loading:
            return
        self._auto_smooth.blockSignals(True)
        self._auto_smooth.setValue(int(self._ct_smooth.value()))
        self._auto_smooth.blockSignals(False)
        if self._loaded:
            self._relayout(renest=False)

    def _apply_contour_offset(self) -> None:
        """Toolbar Contorno -> grava a sangria (PDF + imagem) e re-gera a faca."""
        if self._ct_loading:
            return
        sign = 1 if self._ct_dir.checkedId() == 1 else -1
        val = float(self._ct_offset.value()) * sign
        self._offset.blockSignals(True)
        self._auto_offset.blockSignals(True)
        self._offset.setValue(val)
        self._auto_offset.setValue(val)
        self._offset.blockSignals(False)
        self._auto_offset.blockSignals(False)
        if self._loaded:
            self._relayout(renest=False)

    def _apply_contour_corner(self) -> None:
        self._faca_corner = self._ct_corner_val.get(self._ct_corner.checkedId(), "round")
        if self._loaded:
            self._relayout(renest=False)

    def _sync_contour_tool(self) -> None:
        """Reflete a sangria/cantos atuais na toolbar (ex.: ao abrir projeto)."""
        if not hasattr(self, "_ct_offset"):
            return
        self._ct_loading = True
        try:
            signed = float(self._offset.value())
            self._ct_offset.setValue(abs(signed))
            btn = self._ct_dir.button(1 if signed >= 0 else 2)
            if btn is not None:
                btn.setChecked(True)
            for i, val in self._ct_corner_val.items():
                if val == self._faca_corner:
                    b = self._ct_corner.button(i)
                    if b is not None:
                        b.setChecked(True)
            self._ct_smooth.setValue(int(self._auto_smooth.value()))
        finally:
            self._ct_loading = False

    def _update_property_bar(self) -> None:
        """Repinta a barra conforme a seleção atual (Projeto / Objeto / Grupo)."""
        if not hasattr(self, "_pbar_stack"):
            return
        self._sync_contour_tool()  # reflete offset/cantos atuais na toolbar
        try:
            pieces = self._selected_pieces()
        except RuntimeError:
            return
        self._pbar_loading = True
        try:
            if len(pieces) == 1:
                p = pieces[0]
                self._pbar_stack.setCurrentIndex(1)
                self._pb_w.setValue(p.rect().width())   # medida do objeto clicado
                self._pb_h.setValue(p.rect().height())
                self._pb_lock.setChecked(self._ps_lock.isChecked())
            elif len(pieces) > 1:
                self._pbar_stack.setCurrentIndex(2)
                self._pb_grp_count.setText(f"{len(pieces)} selecionados")
                r = self._selection_bbox_scene()
                if r is not None:
                    self._pb_grp_size.setText(
                        f"L {units.fmt_len(r.width(), with_unit=False)} × "
                        f"A {units.fmt_len(r.height())}"
                    )
            else:
                self._pbar_stack.setCurrentIndex(0)
                self._pb_proj_material.setText(
                    f"{units.fmt_len(float(self._width.value()), with_unit=False)} × "
                    f"{units.fmt_len(float(self._height.value()))}"
                )
                n = m = 0
                if self._result is not None:
                    m = len(self._result.sheets)
                    n = sum(s.item_count for s in self._result.sheets)
                self._pb_proj_pecas.setText(str(n))
                self._pb_proj_chapas.setText(str(m))
        finally:
            self._pbar_loading = False

    def _pbar_resize(self, which: str) -> None:
        """Muda o tamanho da peça pela numeracao (L/A da barra Objeto), reusando o
        redimensionar do painel Peça (respeita o cadeado / proporção)."""
        if self._pbar_loading or len(self._selected_pieces()) != 1:
            return
        if which == "w":
            self._ps_w.setValue(float(self._pb_w.value()))
        else:
            self._ps_h.setValue(float(self._pb_h.value()))

    # ---- alças de redimensionamento no canvas (arrastar com o mouse) ----
    def _update_resize_handles(self) -> None:
        """Mostra alças na peça quando ha UMA selecionada; some com o resto.

        As alças são FILHAS da peça (em coordenadas locais), entao seguem a peça
        ao mover/redimensionar, sem ficar para tras."""
        for h in self._resize_handles:
            with contextlib.suppress(RuntimeError, ValueError):
                h.setParentItem(None)
                self._scene.removeItem(h)
        self._resize_handles = []
        pieces = self._selected_pieces()
        if len(pieces) != 1:
            return
        p = pieces[0]
        w, h = p.rect().width(), p.rect().height()
        for axis, hx, hy in (
            ("wh", w, h), ("w", w, h / 2), ("h", w / 2, h),  # coords LOCAIS da peça
        ):
            handle = _ResizeHandle(self, p, axis)
            handle.setParentItem(p)  # filha da peça: segue o movimento
            handle.setPos(hx, hy)
            self._resize_handles.append(handle)

    def _clear_resize_preview(self) -> None:
        if self._resize_preview is not None:
            with contextlib.suppress(RuntimeError, ValueError):
                self._scene.removeItem(self._resize_preview)
            self._resize_preview = None

    def _begin_resize(self, piece) -> None:
        self._clear_resize_preview()
        pen = QPen(QColor(theme.ACCENT))
        pen.setStyle(Qt.DashLine)
        pen.setCosmetic(True)
        pen.setWidth(2)
        self._resize_preview = self._scene.addRect(piece.sceneBoundingRect(), pen)
        self._resize_preview.setZValue(1999)

    def _resize_dims(self, piece, scene_pos, axis):
        """(largura, altura) do footprint a partir do arraste, ancorado no topo-
        esquerda; aplica proporção quando o cadeado esta ligado."""
        w = max(2.0, scene_pos.x() - piece.scenePos().x()) if axis in ("wh", "w")\
            else piece.rect().width()
        h = max(2.0, scene_pos.y() - piece.scenePos().y()) if axis in ("wh", "h")\
            else piece.rect().height()
        if self._ps_lock.isChecked() and piece.rect().height() > 0:
            ratio = piece.rect().width() / piece.rect().height()
            if axis == "h":
                w = h * ratio
            else:
                h = w / ratio
        return w, h

    def _update_resize_preview(self, piece, scene_pos, axis) -> None:
        if self._resize_preview is None:
            return
        w, h = self._resize_dims(piece, scene_pos, axis)
        self._resize_preview.setRect(piece.scenePos().x(), piece.scenePos().y(), w, h)

    def _end_resize(self, piece, scene_pos, axis) -> None:
        self._clear_resize_preview()
        path = self._path_of(piece.artwork_id)
        base = next(
            (b for b in self._base_artworks if self._path_of(b.id) == path), None
        )
        art = {a.id: a for a in self._result.artworks}.get(piece.artwork_id)\
            if self._result else None
        if not path or base is None or art is None:
            return
        cur_w, cur_h = piece.rect().width(), piece.rect().height()
        if cur_w <= 0 or cur_h <= 0:
            return
        fw, fh = self._resize_dims(piece, scene_pos, axis)
        # footprint -> tamanho da ARTE (mesma proporção footprint/arte)
        aw = art.size.width * (fw / cur_w)
        ah = art.size.height * (fh / cur_h)
        try:
            new_size = Size(aw, ah)
        except ValidationError:
            return
        if abs(aw - base.size.width) < 1e-6 and abs(ah - base.size.height) < 1e-6:
            self._file_sizes.pop(path, None)
        else:
            self._file_sizes[path] = new_size
        self._keep_tab = True
        try:
            self._relayout(renest=False)
            self._reselect_path(path)
        finally:
            self._keep_tab = False

    # ==================== Abas de trabalho (multi-projeto) ====================
    # Widgets de configuração que fazem parte de cada projeto (salvos por aba).
    # Modos de faca (usado no combo do Documento e no override por peça). O valor
    # e o que fica gravado em params["mode"]. "auto" decide sozinho pelo tipo da
    # arte (JPG opaco -> retângulo; PNG com transparência -> contorno).
    _FACA_MODES = (
        ("Automático (recomendado)", "auto"),
        ("Retângulo (corte reto)", "rect"),
        ("Contorno justo", "contour"),
        ("Contorno suave (arredonda)", "contour_smooth"),
        ("Contorno simplificado", "contour_simplify"),
        ("Faca do cliente (vetor do PDF)", "vector"),
    )
    _CONTOUR_MODES = ("contour", "contour_smooth", "contour_simplify")

    _SESSION_WIDGETS = (
        ("_width", "spin"), ("_height", "spin"), ("_spacing", "spin"),
        ("_spacing_v", "spin"), ("_offset", "spin"), ("_crop", "spin"),
        ("_faca_mode", "combo"), ("_rotation", "combo"), ("_shared", "combo"),
        ("_auto_sensitivity", "spin"), ("_auto_smooth", "spin"),
        ("_auto_offset", "spin"), ("_auto_ignore_white", "check"),
        ("_reg_type", "combo"), ("_reg_margin", "spin"), ("_reg_diameter", "spin"),
        ("_mk_distance", "spin"), ("_mk_size", "spin"), ("_mk_thickness", "spin"),
        ("_import_box", "combo"), ("_view_mode", "combo"), ("_center_check", "check"),
    )

    def _build_tab_bar(self) -> QWidget:
        """Barra de abas (estilo CorelDRAW): cada aba e um projeto independente."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)  # "+" colado na aba/X
        self._tabbar = QTabBar()
        self._tabbar.setTabsClosable(True)
        self._tabbar.setExpanding(False)
        self._tabbar.setDocumentMode(True)
        self._tabbar.addTab("Sem título 1")
        self._sessions = [None]  # aba ativa: estado vive nos widgets/atributos
        self._tabbar.currentChanged.connect(self._on_tab_changed)
        self._tabbar.tabCloseRequested.connect(self._close_tab)
        lay.addWidget(self._tabbar)
        plus = QToolButton()
        plus.setText("+")
        plus.setToolTip("Novo trabalho (aba)")
        plus.setFixedSize(34, 38)
        plus.setCursor(Qt.PointingHandCursor)
        # tamanho da fonte NO stylesheet (setFont e ignorado quando ha QSS):
        # glifo grande e azul do tema, puxado para a esquerda (colado na aba/X).
        plus.setStyleSheet(
            f"QToolButton{{color:{theme.ACCENT}; border:none; background:transparent;"
            " font-size:26px; font-weight:400; padding:0 0 5px 0; margin-left:-8px;}"
            f"QToolButton:hover{{color:{theme.ACCENT_HOVER};}}"
        )
        plus.clicked.connect(self._new_tab)
        lay.addWidget(plus)
        lay.addStretch()
        return w

    def _capture_widget_values(self) -> dict:
        out = {}
        for name, kind in self._SESSION_WIDGETS:
            w = getattr(self, name, None)
            if w is None:
                continue
            out[name] = (
                w.value() if kind == "spin"
                else w.currentIndex() if kind == "combo"
                else w.isChecked()
            )
        return out

    def _restore_widget_values(self, vals: dict) -> None:
        for name, kind in self._SESSION_WIDGETS:
            if name not in vals:
                continue
            w = getattr(self, name, None)
            if w is None:
                continue
            w.blockSignals(True)
            try:
                if kind == "spin":
                    w.setValue(vals[name])
                elif kind == "combo":
                    w.setCurrentIndex(vals[name])
                else:
                    w.setChecked(vals[name])
            finally:
                w.blockSignals(False)

    def _snapshot_session(self) -> dict:
        """Fotografa TODO o estado do projeto atual (para guardar na aba)."""
        return {
            "paths": list(self._paths),
            "quantities": self._quantities(),
            "result": self._result,
            "base_artworks": list(self._base_artworks),
            "sources": dict(self._sources),
            "origins": dict(self._origins),
            "pixmaps": dict(self._pixmaps),
            "file_sizes": dict(self._file_sizes),
            "page_crops": {k: dict(v) for k, v in self._page_crops.items()},
            "baked_crops": dict(self._baked_crops),
            "crop_cache": dict(self._crop_cache),
            "file_overrides": {k: dict(v) for k, v in self._file_overrides.items()},
            "piece_rotations": dict(self._piece_rotations),
            "faca_on": self._faca_on,
            "loaded": self._loaded,
            "project_path": self._project_path,
            "center_on_sheet": self._center_on_sheet,
            "faca_corner": self._faca_corner,
            "guides": [list(g) for g in self._guides],
            "widgets": self._capture_widget_values(),
        }

    def _blank_session(self) -> dict:
        """Sessao de um projeto NOVO (vazio), herdando as configs atuais."""
        s = self._snapshot_session()
        s.update(
            paths=[], quantities={}, result=None, base_artworks=[], sources={},
            origins={}, pixmaps={}, file_sizes={}, page_crops={}, baked_crops={},
            crop_cache={}, file_overrides={}, piece_rotations={}, faca_on=False,
            loaded=False, project_path=None, guides=[],
        )
        return s

    def _rebuild_table(self, paths: list, quantities: dict) -> None:
        """Recria as linhas da biblioteca a partir dos caminhos + quantidades."""
        self._table.setRowCount(0)
        for path in paths:
            row = self._table.rowCount()
            self._table.insertRow(row)
            item = QTableWidgetItem(f"{Path(path).name}\n{self._file_type(path)}")
            item.setIcon(self._thumbnail(path))
            self._table.setItem(row, 0, item)
            spin = QuantityStepper(1, 100000, int(quantities.get(path, 1)))
            spin.valueChanged.connect(lambda _: self._relayout(from_table=True))
            self._table.setCellWidget(row, 1, spin)
            self._table.setRowHeight(row, 46)

    def _apply_session(self, s: dict) -> None:
        """Restaura uma sessao inteira (troca de aba) e redesenha."""
        # o clipboard de peças e por trabalho: colar numa aba posições copiadas
        # de outra (ids homonimos) inseriria peça no lugar errado (QA-12).
        self._piece_clipboard = []
        self._paste_count = 0
        self._suspend_relayout = True
        try:
            self._restore_widget_values(s["widgets"])
            self._paths = list(s["paths"])
            self._rebuild_table(s["paths"], s["quantities"])
            self._result = s["result"]
            self._base_artworks = list(s["base_artworks"])
            self._sources = dict(s["sources"])
            self._origins = dict(s["origins"])
            self._pixmaps = dict(s["pixmaps"])
            self._file_sizes = dict(s["file_sizes"])
            self._page_crops = {k: dict(v) for k, v in s["page_crops"].items()}
            self._baked_crops = dict(s["baked_crops"])
            self._crop_cache = dict(s["crop_cache"])
            self._file_overrides = {k: dict(v) for k, v in s["file_overrides"].items()}
            self._piece_rotations = dict(s["piece_rotations"])
            self._faca_on = s["faca_on"]
            self._loaded = s["loaded"]
            self._project_path = s["project_path"]
            self._center_on_sheet = s["center_on_sheet"]
            self._faca_corner = s["faca_corner"]
            self._guides = [list(g) for g in s["guides"]]
            self._pdf_contours = {}
            self._vector_contours = {}
        finally:
            self._suspend_relayout = False
        self._undo.clear()  # desfazer reinicia ao trocar de aba
        if self._result is not None:
            self._draw_preview()
        else:
            self._piece_items = []
            self._decor_items = []
            self._scene.clear()
        self._update_property_bar()
        self._update_title()
        self._set_exports_enabled(self._result is not None)

    def _on_tab_changed(self, index: int) -> None:
        if self._switching_tab or index < 0 or index == self._active_tab:
            return
        self._switching_tab = True
        try:
            self._sessions[self._active_tab] = self._snapshot_session()  # salva a atual
            self._active_tab = index
            self._apply_session(self._sessions[index])  # restaura a alvo
        finally:
            self._switching_tab = False

    def _new_tab(self) -> None:
        """Cria um projeto novo numa aba nova e vai para ela."""
        self._sessions[self._active_tab] = self._snapshot_session()  # salva a atual
        self._tab_counter += 1
        self._sessions.append(self._blank_session())
        idx = self._tabbar.count()
        self._switching_tab = True
        self._tabbar.addTab(f"Sem título {self._tab_counter}")
        self._active_tab = idx
        self._switching_tab = False
        self._apply_session(self._sessions[idx])
        self._switching_tab = True
        self._tabbar.setCurrentIndex(idx)
        self._switching_tab = False

    def _close_tab(self, index: int) -> None:
        if self._tabbar.count() <= 1:
            return  # sempre resta uma aba
        going_active = index == self._active_tab
        if going_active:
            target = index - 1 if index > 0 else index + 1
            self._active_tab = index  # evita salvar a que vai fechar
            self._apply_session(self._sessions[target])
        del self._sessions[index]
        self._switching_tab = True
        self._tabbar.removeTab(index)
        self._active_tab = self._tabbar.currentIndex()
        self._switching_tab = False

    # ---- construcao da UI ----
    def _build_ui(self) -> None:
        """Monta a janela: biblioteca | área de trabalho | propriedades, com
        faixa de aviso no topo e barra de status no rodape. A ribbon (ações) e
        montada depois, em _build_menu_toolbar."""
        self._toasts = ToastManager(self)
        self._status = QLabel("")  # compat interno (mensagens antigas); não exibido
        self._status.hide()

        library = self._build_library_panel()
        work = self._build_work_area()
        properties = self._build_properties_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(library)
        splitter.addWidget(work)
        splitter.addWidget(properties)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([300, 780, 320])
        splitter.setChildrenCollapsible(False)

        self._alert = Alert()
        self._progress = QProgressBar()
        self._progress.setMaximumHeight(4)
        self._progress.setTextVisible(False)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(theme.SPACE_SM, theme.SPACE_SM, theme.SPACE_SM, 0)
        root.setSpacing(theme.SPACE_SM)
        root.addWidget(self._build_tab_bar())        # abas de trabalho (multi-projeto)
        root.addWidget(self._build_property_bar())  # barra contextual (Projeto/Objeto/Grupo)
        root.addWidget(self._alert)
        root.addWidget(self._progress)
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self._status_ctl = StatusBarController(self.statusBar())
        self._status_ctl.set_mode(self._view_mode.currentText())
        self._view_mode.currentIndexChanged.connect(
            lambda _: self._status_ctl.set_mode(self._view_mode.currentText())
        )
        self._scene.selectionChanged.connect(self._on_selection_changed)
        self._view.cursor_moved.connect(self._status_ctl.set_cursor)
        self._view.view_changed.connect(
            lambda: self._status_ctl.set_zoom(self._view.zoom_factor())
        )

        self._apply_tooltips()
        self._on_selection_changed()

    def _build_work_area(self) -> QWidget:
        """Área de trabalho central: canvas com zoom/pan e réguas em mm."""
        self._scene = QGraphicsScene()
        self._view = ZoomableGraphicsView(self._scene)
        self._view.drag_started.connect(self._begin_move)
        self._view.drag_finished.connect(self._end_move)
        self._view.nudge.connect(self._nudge)
        self._view.library_drop.connect(self._on_library_drop)

        work = QWidget()
        grid = QGridLayout(work)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self._corner = QWidget()
        self._corner.setFixedSize(RULER_SIZE, RULER_SIZE)
        self._corner.setStyleSheet(f"background:{theme.SURFACE_ALT};")
        self._h_ruler = Ruler(self._view, horizontal=True)
        self._v_ruler = Ruler(self._view, horizontal=False)
        grid.addWidget(self._corner, 0, 0)
        grid.addWidget(self._h_ruler, 0, 1)
        grid.addWidget(self._v_ruler, 1, 0)
        grid.addWidget(self._view, 1, 1)
        self._view.view_changed.connect(self._h_ruler.update)
        self._view.view_changed.connect(self._v_ruler.update)

        self._overlay = MeasureOverlay(self._view.viewport())
        self._view.view_changed.connect(self._position_overlay)

        # barrinha flutuante de exibição (arrastável) no canto do canvas: dona do
        # combo de modo de visualização (_view_mode canônico). Fica no canto
        # superior esquerdo por padrão, longe da caixa de medidas (canto direito).
        self._display_bar = FloatingDisplayBar(self._view.viewport())
        self._view_mode = self._display_bar.combo
        self._view_mode.addItem("Impressão + Corte", "both")
        self._view_mode.addItem("Só Impressão", "print")
        self._view_mode.addItem("Só Corte", "cut")
        self._view_mode.addItem("Tela dividida (impressão / corte)", "split")
        self._view_mode.currentIndexChanged.connect(lambda _: self._refresh_preview())
        self._display_bar.adjustSize()
        self._display_bar.move(12, 12)
        self._display_bar.show()

        # demais controles de Exibição (réguas, snap) no popup do botão da barra
        self._display_panel = self._build_display_controls()

        for ruler in (self._h_ruler, self._v_ruler):
            ruler.guide_preview.connect(self._on_guide_preview)
            ruler.guide_dropped.connect(self._on_guide_dropped)
        return work

    # ---- guias (arrastar da régua, estilo CorelDRAW) ----
    @staticmethod
    def _guide_pen() -> QPen:
        pen = QPen(QColor(theme.ACCENT))  # azul único da marca (nada de azul-Windows)
        pen.setStyle(Qt.DashLine)
        pen.setCosmetic(True)  # espessura/tracejado constantes em qualquer zoom
        return pen

    def _guides_extent(self) -> tuple[float, float, float, float]:
        """Retângulo (x0, y0, x1, y1) que as guias atravessam, com margem."""
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return -1000.0, -1000.0, 1000.0, 1000.0
        m = max(200.0, rect.width() * 0.25, rect.height() * 0.25)
        return rect.left() - m, rect.top() - m, rect.right() + m, rect.bottom() + m

    def _make_guide_line(self, is_h: bool, value: float, pen: QPen):
        """Linha simples (usada só na pre-visualização do arraste)."""
        x0, y0, x1, y1 = self._guides_extent()
        if is_h:
            return self._scene.addLine(x0, value, x1, value, pen)
        return self._scene.addLine(value, y0, value, y1, pen)

    def _make_guide_item(self, record) -> GuideItem:
        """Cria a guia permanente (selecionavel/arrastavel) a partir do registro."""
        is_h, value = record[0], record[1]
        x0, y0, x1, y1 = self._guides_extent()
        if is_h:
            item = GuideItem(record, x0, value, x1, value, self._guide_pen())
        else:
            item = GuideItem(record, value, y0, value, y1, self._guide_pen())
        self._scene.addItem(item)
        return item

    def _on_guide_preview(self, is_h: bool, value: float) -> None:
        if self._guide_preview_item is not None:
            self._scene.removeItem(self._guide_preview_item)
            self._guide_preview_item = None
        if self._result is None:
            return
        self._guide_preview_item = self._make_guide_line(is_h, value, self._guide_pen())

    def _on_guide_dropped(self, is_h: bool, value: float, inside: bool) -> None:
        if self._guide_preview_item is not None:
            self._scene.removeItem(self._guide_preview_item)
            self._guide_preview_item = None
        if inside and self._result is not None:
            record = [bool(is_h), float(value)]
            self._guides.append(record)
            self._make_guide_item(record)

    def _draw_guides(self) -> None:
        """Redesenha as guias guardadas (a cena e limpa a cada preview)."""
        for record in self._guides:
            self._make_guide_item(record)

    def _clear_guides(self) -> None:
        self._guides = []
        for item in [it for it in self._scene.items() if isinstance(it, GuideItem)]:
            self._scene.removeItem(item)

    def _position_overlay(self) -> None:
        """Reposiciona a caixinha de medidas no canto superior direito do canvas."""
        if not hasattr(self, "_overlay") or not self._overlay.isVisible():
            return
        vp = self._view.viewport()
        m = 10
        self._overlay.move(max(m, vp.width() - self._overlay.width() - m), m)

    def _update_overlay(self) -> None:
        """Atualiza a caixinha de medidas conforme a seleção (ou a chapa)."""
        if not hasattr(self, "_overlay"):
            return
        try:
            selected = self._scene.selectedItems()
        except RuntimeError:
            return
        pieces = [it for it in selected if isinstance(it, PieceItem)]
        by_id = {a.id: a for a in self._result.artworks} if self._result else {}
        if len(pieces) == 1 and by_id.get(pieces[0].artwork_id) is not None:
            art = by_id[pieces[0].artwork_id]
            m = measurements.piece_metrics(art)
            self._overlay.show_lines(
                "Peça",
                f"Faca: {units.fmt_len(m.width, with_unit=False)} x {units.fmt_len(m.height)}",
                f"Arte: {units.fmt_len(art.size.width, with_unit=False)} "
                f"x {units.fmt_len(art.size.height)}",
            )
        elif len(pieces) > 1:
            boxes = [
                (p.pos().x(), p.pos().y(), p.rect().width(), p.rect().height())
                for p in pieces
            ]
            g = measurements.group_metrics(boxes)
            self._overlay.show_lines(
                f"Grupo ({g.count})",
                f"{units.fmt_len(g.width, with_unit=False)} x {units.fmt_len(g.height)}",
            )
        elif self._result and self._result.sheets:
            s = self._result.sheets[0]
            self._overlay.show_lines(
                "Chapa",
                f"{units.fmt_len(s.material.width, with_unit=False)} "
                f"x {units.fmt_len(s.used_length)}",
                f"{len(self._result.sheets)} chapa(s)",
            )
        else:
            self._overlay.hide()
            return
        self._position_overlay()

    def _build_properties_panel(self) -> QWidget:
        """Painel de propriedades com abas fixas: 'Documento' (chapa/faca/etc.) e
        'Seleção' (peça ou grupo). As abas ficam sempre visiveis, entao as
        configurações nunca somem: clicar numa peça só muda para a aba Seleção,
        e basta clicar em 'Documento' para voltar."""
        document = QWidget()
        dl = QVBoxLayout(document)
        dl.setContentsMargins(0, theme.SPACE_XS, 0, theme.SPACE_SM)
        dl.setSpacing(theme.SPACE_SM)  # 8px entre cards (compacto)
        self._doc_layout = dl  # usado pelo Modo Compacto
        self._doc_cards = []   # cards do documento (para o Modo Compacto)

        # Modo Compacto (para notebooks): reduz espaçamentos/altura dos campos.
        self._compact_check = QCheckBox("Modo Compacto")
        self._compact_check.setToolTip(
            "Reduz os espaçamentos e a altura dos campos, mantendo a legibilidade.\n"
            "Ideal para telas menores (notebooks)."
        )
        self._compact_check.toggled.connect(self._apply_compact_mode)
        dl.addWidget(self._compact_check)

        dl.addWidget(self._build_resumo_card())          # resumo da produção (topo, fixo)
        dl.addWidget(self._build_producao_card())        # 1 - Produção (aberto)
        dl.addWidget(self._build_acabamento_card())      # 2 - Acabamento (recolhido)
        dl.addWidget(self._build_imagens_card())         # 3 - Imagens (recolhido)
        dl.addWidget(self._build_registro_card())        # 4 - Marcas de registro (recolhido)
        dl.addWidget(self._build_avancado_card())        # 5 - Avançado (recolhido)
        dl.addStretch()
        self._doc_widget = document  # usado pelo Modo Compacto p/ achar os campos
        doc_scroll = QScrollArea()
        doc_scroll.setWidgetResizable(True)
        doc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        doc_scroll.setWidget(document)

        # aba Seleção: pilha interna (vazio / peça / grupo)
        self._sel_stack = QStackedWidget()
        hint = QLabel("Clique numa peça na área de trabalho para ver medidas e ações.")
        hint.setWordWrap(True)
        hint.setProperty("role", "caption")
        hint.setAlignment(Qt.AlignTop)
        hint_wrap = QWidget()
        hl = QVBoxLayout(hint_wrap)
        hl.setContentsMargins(theme.SPACE_SM, theme.SPACE_SM, theme.SPACE_SM, 0)
        hl.addWidget(hint)
        hl.addStretch()
        self._sel_stack.addWidget(hint_wrap)              # 0 = sem seleção
        self._sel_stack.addWidget(self._build_piece_page())  # 1 = peça
        self._sel_stack.addWidget(self._build_group_page())  # 2 = grupo

        self._props_tabs = QTabWidget()
        self._props_tabs.setObjectName("inspectorTabs")  # barra de abas destacada
        self._props_tabs.addTab(doc_scroll, "Documento")
        self._props_tabs.addTab(self._sel_stack, "Seleção")
        self._props_tabs.addTab(self._build_object_page(), "Objeto")
        self._transform_page = self._build_transform_page()
        self._props_tabs.addTab(self._transform_page, "Transformar")
        # ao sair da aba Transformar, some com os fantasmas
        self._props_tabs.currentChanged.connect(lambda _: self._refresh_transform_preview())

        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(theme.SPACE_XS, 0, 0, 0)
        wl.setSpacing(theme.SPACE_SM)
        wl.addWidget(self._props_tabs, 1)
        wrap.setMinimumWidth(280)
        wrap.setMaximumWidth(400)
        return wrap

    # ==================== Aba "Transformar" (duplicação inteligente) ==========
    def _build_transform_page(self) -> QWidget:
        """Aba 'Transformar' (estilo CorelDRAW): duplicar por posição (X/Y +
        cópias), gerar grade (colunas x linhas) e girar. Preview 'fantasma' em
        tempo real. Só mexe na camada de edicao: as cópias viram peças reais via
        _add_placed (entram no undo, no PDF, no DXF e no .printnest)."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_SM)

        cap = QLabel("Selecione peça(s) e escolha como multiplicar.")
        cap.setProperty("role", "caption")
        cap.setWordWrap(True)
        lay.addWidget(cap)

        # ---- Duplicar (posição) ----
        dup = CollapsibleCard("Duplicar (posição)")
        self._td_x = LengthSpin(-20000, 20000)
        self._td_x.setValue(100)
        self._td_y = LengthSpin(-20000, 20000)
        self._td_y.setValue(0)
        self._td_x.valueChanged.connect(lambda _: self._preview_duplicate())
        self._td_y.valueChanged.connect(lambda _: self._preview_duplicate())
        self._grid_fields(dup.body, [
            ("Deslocamento X", self._td_x, "Distância entre cópias no eixo X (mm)."),
            ("Deslocamento Y", self._td_y, "Distância entre cópias no eixo Y (mm)."),
        ])
        self._td_relative = QCheckBox("Posição relativa (cada cópia a partir da anterior)")
        self._td_relative.setChecked(True)
        self._td_relative.setToolTip(
            "Marcado: X/Y são o passo entre cópias (0, X, 2X, 3X...). Desmarcado: "
            "todas as cópias vão para a MESMA posição (X, Y) informada."
        )
        self._td_relative.toggled.connect(lambda _: self._preview_duplicate())
        dup.body.addWidget(self._td_relative)
        self._td_copies = QuantityStepper(1, 1000, 1)
        self._td_copies.valueChanged.connect(lambda _: self._preview_duplicate())
        dup.body.addWidget(labeled("Cópias", self._td_copies))
        btn_dup = QPushButton("  Aplicar")
        btn_dup.setIcon(icons.icon("copy-plus", theme.ICON))
        btn_dup.clicked.connect(self._apply_transform_duplicate)
        dup.body.addWidget(btn_dup)
        lay.addWidget(dup)

        # ---- Grade (colunas x linhas) ----
        grid = CollapsibleCard("Grade (colunas x linhas)")
        self._tg_cols = _spin(1, 200)
        self._tg_cols.setValue(5)
        self._tg_rows = _spin(1, 200)
        self._tg_rows.setValue(4)
        self._tg_gap_h = LengthSpin(0, 20000)
        self._tg_gap_h.setValue(10)
        self._tg_gap_v = LengthSpin(0, 20000)
        self._tg_gap_v.setValue(10)
        for w in (self._tg_cols, self._tg_rows, self._tg_gap_h, self._tg_gap_v):
            w.valueChanged.connect(lambda _: self._preview_grid())
        self._grid_fields(grid.body, [
            ("Colunas", self._tg_cols, "Número de colunas."),
            ("Linhas", self._tg_rows, "Número de linhas."),
            ("Espaco H", self._tg_gap_h, "Espaçamento horizontal entre cópias (mm)."),
            ("Espaco V", self._tg_gap_v, "Espaçamento vertical entre cópias (mm)."),
        ])
        btn_grid = QPushButton("  Gerar Grade")
        btn_grid.setIcon(icons.icon("grid-3x3", theme.ICON))
        btn_grid.clicked.connect(self._apply_transform_grid)
        grid.body.addWidget(btn_grid)
        lay.addWidget(grid)

        # ---- Rotação ----
        rot = CollapsibleCard("Rotação", collapsed=True)
        row = QHBoxLayout()
        b_l = QPushButton("  -90")
        b_l.setIcon(icons.icon("rotate-ccw", theme.ICON))
        b_l.clicked.connect(lambda: self._rotate_selected(-90))
        b_r = QPushButton("  +90")
        b_r.setIcon(icons.icon("rotate-cw", theme.ICON))
        b_r.clicked.connect(lambda: self._rotate_selected(90))
        row.addWidget(b_l)
        row.addWidget(b_r)
        rot.body.addLayout(row)
        rot.body.addWidget(QLabel("Gira só a(s) peça(s) selecionada(s) e re-encaixa."))
        lay.addWidget(rot)

        lay.addStretch()
        return page

    def _transform_active(self) -> bool:
        """True se a aba Transformar esta em foco (para mostrar/limpar fantasmas)."""
        return (
            hasattr(self, "_transform_page")
            and self._props_tabs.currentWidget() is self._transform_page
        )

    def _clear_ghost(self) -> None:
        """Remove os previews fantasma da cena."""
        for it in self._ghost_items:
            with contextlib.suppress(RuntimeError, ValueError):
                self._scene.removeItem(it)  # pode já ter saido no scene.clear
        self._ghost_items = []

    def _draw_ghosts(self, rects: list) -> None:
        """Desenha cópias fantasma (tracejado, opacidade 40%) nas posições dadas.
        rects: lista de (x_cena, y_cena, largura, altura) em mm."""
        self._clear_ghost()
        pen = QPen(QColor(theme.ACCENT))
        pen.setStyle(Qt.DashLine)
        pen.setCosmetic(True)
        pen.setWidth(2)
        accent_soft = QColor(theme.ACCENT)
        accent_soft.setAlpha(40)  # azul do tema, bem leve
        brush = QBrush(accent_soft)
        for (sx, sy, w, h) in rects:
            it = self._scene.addRect(sx, sy, w, h, pen, brush)
            it.setOpacity(0.4)
            it.setZValue(1000)  # por cima das peças
            # transparente ao mouse: o clique passa direto para a peça embaixo
            # (senao o fantasma "rouba" o clique e não da pra selecionar/excluir).
            it.setAcceptedMouseButtons(Qt.NoButton)
            it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self._ghost_items.append(it)

    def _refresh_transform_preview(self) -> None:
        """Reaplica o preview conforme o último modo usado (ou limpa se inativo)."""
        if self._suppress_ghost:
            return  # durante o 'aplicar' o redraw não deve repintar fantasmas
        if not self._transform_active():
            self._clear_ghost()
            return
        if self._transform_mode == "grid":
            self._preview_grid()
        else:
            self._preview_duplicate()

    def _preview_duplicate(self) -> None:
        self._transform_mode = "dup"
        if not self._transform_active() or self._result is None:
            self._clear_ghost()
            return
        sel = self._selected_pieces()
        if not sel:
            self._clear_ghost()
            return
        dx = float(self._td_x.value())
        dy = float(self._td_y.value())
        copies = int(self._td_copies.value())
        relative = self._td_relative.isChecked()
        rects = []
        for piece in sel:
            w, h = piece.rect().width(), piece.rect().height()
            for k in range(1, copies + 1):
                if relative:
                    sx = piece.scenePos().x() + k * dx
                    sy = piece.scenePos().y() + k * dy
                else:
                    sx = piece.dx + dx
                    sy = piece.dy + dy
                rects.append((sx, sy, w, h))
        self._draw_ghosts(rects)

    def _preview_grid(self) -> None:
        self._transform_mode = "grid"
        if not self._transform_active() or self._result is None:
            self._clear_ghost()
            return
        sel = self._selected_pieces()
        if not sel:
            self._clear_ghost()
            return
        cols, rows = int(self._tg_cols.value()), int(self._tg_rows.value())
        sh, sv = float(self._tg_gap_h.value()), float(self._tg_gap_v.value())
        rects = []
        for piece in sel:
            w, h = piece.rect().width(), piece.rect().height()
            for c in range(cols):
                for r in range(rows):
                    if c == 0 and r == 0:
                        continue
                    rects.append((
                        piece.scenePos().x() + c * (w + sh),
                        piece.scenePos().y() + r * (h + sv),
                        w, h,
                    ))
        self._draw_ghosts(rects)

    def _apply_transform_duplicate(self) -> None:
        if self._result is None:
            return
        sel = self._selected_pieces()
        if not sel:
            self._toasts.info("Selecione a(s) peça(s) para duplicar.")
            return
        dx = float(self._td_x.value())
        dy = float(self._td_y.value())
        copies = int(self._td_copies.value())
        relative = self._td_relative.isChecked()
        add: dict[int, list] = {}
        for piece in sel:
            bx = piece.scenePos().x() - piece.dx
            by = piece.scenePos().y() - piece.dy
            for k in range(1, copies + 1):
                if relative:
                    px, py = bx + k * dx, by + k * dy
                else:
                    px, py = dx, dy
                add.setdefault(piece.sheet_index, []).append(
                    PlacedItem(piece.artwork_id, Point2D(px, py))
                )
        self._clear_ghost()
        self._suppress_ghost = True
        try:
            self._add_placed(add, text="duplicar (transformar)")
        finally:
            self._suppress_ghost = False
        self._toasts.success(f"{len(sel)} peça(s) x {copies} cópia(s)")

    def _apply_transform_grid(self) -> None:
        if self._result is None:
            return
        sel = self._selected_pieces()
        if not sel:
            self._toasts.info("Selecione a(s) peça(s) para a grade.")
            return
        cols, rows = int(self._tg_cols.value()), int(self._tg_rows.value())
        if cols < 1 or rows < 1 or (cols == 1 and rows == 1):
            self._toasts.info("A grade precisa de mais de 1 celula.")
            return
        sh, sv = float(self._tg_gap_h.value()), float(self._tg_gap_v.value())
        add: dict[int, list] = {}
        for piece in sel:
            w, h = piece.rect().width(), piece.rect().height()
            bx = piece.scenePos().x() - piece.dx
            by = piece.scenePos().y() - piece.dy
            for c in range(cols):
                for r in range(rows):
                    if c == 0 and r == 0:
                        continue
                    add.setdefault(piece.sheet_index, []).append(
                        PlacedItem(piece.artwork_id, Point2D(bx + c * (w + sh), by + r * (h + sv)))
                    )
        self._clear_ghost()
        self._suppress_ghost = True
        try:
            self._add_placed(add, text="gerar grade")
        finally:
            self._suppress_ghost = False
        self._toasts.success(f"Grade {cols}x{rows} gerada")

    def _build_piece_page(self) -> QWidget:
        """Propriedades de uma peça: medidas + ações."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_SM)
        # As medidas da peça (L x A, X, Y) ficam na barra de cima (contexto
        # Objeto), estilo Corel — não repetimos aqui para não duplicar info.

        # ---- tamanho deste arquivo (redimensionar a arte) ----
        size_card = CollapsibleCard("Tamanho (redimensionar)")
        size_card.body.addWidget(QLabel("Largura"))
        self._ps_w = LengthSpin(1, 20000)
        # atualiza ao vivo enquanto digita; o reload do campo e bloqueado
        # enquanto ele tem foco (em _load_piece_size), para não apagar o que
        # o usuário esta digitando.
        self._ps_w.valueChanged.connect(lambda _: self._on_piece_size_changed("w"))
        size_card.body.addWidget(self._ps_w)
        size_card.body.addWidget(QLabel("Altura"))
        self._ps_h = LengthSpin(1, 20000)
        self._ps_h.valueChanged.connect(lambda _: self._on_piece_size_changed("h"))
        size_card.body.addWidget(self._ps_h)
        self._ps_lock = QCheckBox("Manter proporção")
        self._ps_lock.setChecked(True)
        self._ps_lock.setToolTip("Ao mudar um lado, ajusta o outro mantendo a proporção da arte")
        size_card.body.addWidget(self._ps_lock)
        self._ps_reset = QPushButton("  Voltar ao tamanho original")
        self._ps_reset.setIcon(icons.icon("rotate-ccw", theme.ICON))
        self._ps_reset.setToolTip("Remove o redimensionamento e volta ao tamanho importado")
        self._ps_reset.clicked.connect(self._reset_piece_size)
        size_card.body.addWidget(self._ps_reset)
        lay.addWidget(size_card)

        # ---- faca SO deste arquivo (override) ----
        faca = CollapsibleCard("Faca deste arquivo")
        self._pf_mode_label = QLabel("Tipo de faca")
        faca.body.addWidget(self._pf_mode_label)
        self._pf_mode = QComboBox()
        for label, data in self._FACA_MODES:
            self._pf_mode.addItem(label, data)
        self._pf_mode.currentIndexChanged.connect(lambda _: self._on_piece_faca_changed())
        faca.body.addWidget(self._pf_mode)
        faca.body.addWidget(QLabel("Sangria  ( + fora  /  − dentro )"))
        self._pf_offset = LengthSpin(-100, 100)
        self._pf_offset.valueChanged.connect(lambda _: self._on_piece_faca_changed())
        faca.body.addWidget(self._pf_offset)
        faca.body.addWidget(QLabel("Recorte da arte - cortar bordas"))
        self._pf_crop = LengthSpin(0, 100)
        self._pf_crop.valueChanged.connect(lambda _: self._on_piece_faca_changed())
        faca.body.addWidget(self._pf_crop)
        faca.body.addWidget(QLabel("Giro (graus)"))
        self._pf_rotation = QComboBox()
        self._pf_rotation.addItems(["0", "90", "180", "270"])
        self._pf_rotation.currentIndexChanged.connect(lambda _: self._on_piece_faca_changed())
        faca.body.addWidget(self._pf_rotation)
        self._pf_smooth_label = QLabel("Suavizar curvas (0 = reto, 5 = macio)")
        faca.body.addWidget(self._pf_smooth_label)
        self._pf_smooth = _spin(0, 5)
        self._pf_smooth.valueChanged.connect(lambda _: self._on_piece_faca_changed())
        faca.body.addWidget(self._pf_smooth)
        self._pf_reset = QPushButton("  Usar padrão do documento")
        self._pf_reset.setIcon(icons.icon("rotate-ccw", theme.ICON))
        self._pf_reset.setToolTip("Remove a faca personalizada e volta ao padrão do Documento")
        self._pf_reset.clicked.connect(self._reset_piece_faca)
        faca.body.addWidget(self._pf_reset)
        lay.addWidget(faca)

        lay.addWidget(self._actions_card([
            ("copy", "Duplicar", self._duplicate_selected),
            ("copy-plus", "Duplicar só esta página...", self._duplicate_selected_qty),
            ("trash-2", "Excluir", self._delete_selected),
        ]))
        lay.addStretch()
        return page

    def _build_group_page(self) -> QWidget:
        """Propriedades de várias peças: medidas do grupo + alinhar/distribuir."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_SM)
        card = CollapsibleCard("Medidas do grupo")
        self._gm_w = MeasureField("Largura total")
        self._gm_h = MeasureField("Altura total")
        self._gm_count = MeasureField("Quantidade")
        for field in (self._gm_w, self._gm_h, self._gm_count):
            card.body.addWidget(field)
        lay.addWidget(card)
        lay.addWidget(self._actions_card([
            ("align-horizontal-justify-start", "Alinhar esq.", lambda: self._align("left")),
            ("align-vertical-justify-start", "Alinhar topo", lambda: self._align("top")),
            ("group", "Agrupar", self._group_selected),
            ("trash-2", "Excluir", self._delete_selected),
        ]))
        lay.addStretch()
        return page

    def _actions_card(self, actions: list[tuple[str, str, object]]) -> QFrame:
        """Cartao com botões de ação (icone + texto)."""
        card = CollapsibleCard("Ações")
        for icon_name, text, slot in actions:
            btn = QPushButton(f"  {text}")
            btn.setIcon(icons.icon(icon_name, theme.ICON))
            btn.clicked.connect(lambda _=False, fn=slot: fn())
            card.body.addWidget(btn)
        return card

    def _build_object_page(self) -> QWidget:
        """Aba 'Objeto': lista os objetos da área de trabalho (clique seleciona) e
        oferece gerenciar objetos como no CorelDRAW: selecionar tudo, agrupar/
        desagrupar, ordem (frente/tras) e remover."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_SM)

        cap = QLabel("Objetos na área de trabalho (clique para selecionar)")
        cap.setProperty("role", "caption")
        cap.setWordWrap(True)
        lay.addWidget(cap)
        self._obj_list = QListWidget()
        self._obj_list.setSelectionMode(QListWidget.ExtendedSelection)
        self._obj_list.itemSelectionChanged.connect(self._on_object_list_selection)
        lay.addWidget(self._obj_list, 1)

        lay.addWidget(self._actions_card([
            ("layers", "Selecionar tudo", self._select_all),
            ("group", "Agrupar", self._group_selected),
            ("ungroup", "Desagrupar", self._ungroup_selected),
            ("align-vertical-justify-start", "Trazer para frente", self._bring_to_front),
            ("align-vertical-justify-end", "Enviar para tras", self._send_to_back),
            ("trash-2", "Remover", self._delete_selected),
        ]))
        return page

    def _refresh_object_list(self) -> None:
        """Reconstroi a lista de objetos a partir das peças atuais."""
        if not hasattr(self, "_obj_list"):
            return
        by_id = {a.id: a for a in self._result.artworks} if self._result else {}
        self._obj_rows = list(self._piece_items)
        self._obj_list.blockSignals(True)
        self._obj_list.clear()
        for i, piece in enumerate(self._obj_rows, 1):
            art = by_id.get(piece.artwork_id)
            name = art.name if art is not None else piece.artwork_id
            self._obj_list.addItem(QListWidgetItem(f"{i}. {name}"))
        self._obj_list.blockSignals(False)
        self._sync_object_list_selection()

    def _sync_object_list_selection(self) -> None:
        """Reflete a seleção do canvas na lista (sem disparar de volta)."""
        if not hasattr(self, "_obj_list"):
            return
        self._obj_list.blockSignals(True)
        try:
            for row, piece in enumerate(getattr(self, "_obj_rows", [])):
                item = self._obj_list.item(row)
                if item is not None:
                    item.setSelected(piece.isSelected())
        except RuntimeError:  # peça já deletada durante um redraw
            pass
        finally:
            self._obj_list.blockSignals(False)

    def _on_object_list_selection(self) -> None:
        """Seleciona no canvas as peças marcadas na lista."""
        rows = {self._obj_list.row(it) for it in self._obj_list.selectedItems()}
        self._scene.clearSelection()
        for row, piece in enumerate(getattr(self, "_obj_rows", [])):
            if row in rows:
                piece.setSelected(True)

    def _bring_to_front(self) -> None:
        """Coloca as peças selecionadas a frente das demais (ordem de empilhamento)."""
        pieces = [it for it in self._scene.selectedItems() if isinstance(it, PieceItem)]
        if not pieces:
            return
        others = [p for p in self._piece_items if p not in pieces]
        top = max((p.zValue() for p in others), default=0.0)
        for i, piece in enumerate(pieces, 1):
            piece.setZValue(top + i)

    def _send_to_back(self) -> None:
        """Envia as peças selecionadas para tras das demais."""
        pieces = [it for it in self._scene.selectedItems() if isinstance(it, PieceItem)]
        if not pieces:
            return
        others = [p for p in self._piece_items if p not in pieces]
        bottom = min((p.zValue() for p in others), default=0.0)
        for i, piece in enumerate(pieces, 1):
            piece.setZValue(bottom - i)

    def _on_selection_changed(self) -> None:
        """Atualiza a aba 'Seleção' conforme a seleção do canvas. As abas ficam
        sempre visiveis; ao selecionar uma peça, vai para a aba Seleção, e ao
        soltar a seleção volta para Documento."""
        if not hasattr(self, "_props_tabs"):
            return
        try:
            selected = self._scene.selectedItems()
        except RuntimeError:  # cena já destruida (fechando a janela)
            return
        pieces = [it for it in selected if isinstance(it, PieceItem)]
        cur = self._props_tabs.currentIndex()
        switch = not self._keep_tab  # durante reselecao não troca de aba
        if not pieces:
            self._sel_stack.setCurrentIndex(0)
            self._props_tabs.setTabText(1, "Seleção")
            if switch and cur == 1:  # só volta para Documento se estiver na Seleção
                self._props_tabs.setCurrentIndex(0)
        elif len(pieces) == 1:
            self._update_piece_page(pieces[0])
            self._sel_stack.setCurrentIndex(1)
            self._props_tabs.setTabText(1, "Peça")
            if switch and cur == 0:  # não tira o usuário da aba Objeto
                self._props_tabs.setCurrentIndex(1)
        else:
            self._update_group_page(pieces)
            self._sel_stack.setCurrentIndex(2)
            self._props_tabs.setTabText(1, f"Grupo ({len(pieces)})")
            if switch and cur == 0:
                self._props_tabs.setCurrentIndex(1)
        self._sync_object_list_selection()
        self._update_overlay()
        self._refresh_transform_preview()  # atualiza os fantasmas da aba Transformar
        self._update_property_bar()  # barra contextual (Projeto/Objeto/Grupo)
        self._update_resize_handles()  # alças de redimensionar (peça selecionada)

    def _update_piece_page(self, piece: PieceItem) -> None:
        # As medidas/posição da peça ficam na barra de cima (contexto Objeto);
        # aqui só carregamos a faca do arquivo, sem duplicar informacao.
        self._load_piece_faca(piece)

    def _load_piece_faca(self, piece: PieceItem) -> None:
        """Carrega no editor a faca do arquivo da peça (override ou padrão)."""
        path = self._path_of(piece.artwork_id)
        self._selected_path = path
        base = next((b for b in self._base_artworks if b.id == piece.artwork_id), None)
        self._selected_is_image = isinstance(base, ImageArtwork)
        p = self._params_for(path)
        self._pf_loading = True
        try:
            sangria = p["auto_offset"] if self._selected_is_image else p["offset"]
            self._pf_offset.setValue(sangria)
            self._pf_crop.setValue(p["crop"])
            self._pf_rotation.setCurrentText(str(p["rotation"]))
            self._pf_smooth.setValue(int(p["smooth"]))
            self._pf_mode.setCurrentIndex(max(0, self._pf_mode.findData(p.get("mode", "auto"))))
        finally:
            self._pf_loading = False
        # o tipo de faca agora vale para imagem também (retângulo/contorno/auto)
        self._pf_mode.setEnabled(True)
        self._pf_mode_label.setEnabled(True)
        # suavizar só faz sentido nas variacoes de contorno (não no retângulo).
        # 'auto' pode virar contorno numa imagem com transparência -> libera.
        mode = p.get("mode", "auto")
        contour_cut = mode in self._CONTOUR_MODES or (
            mode == "auto" and self._selected_is_image
        )
        self._pf_smooth.setEnabled(contour_cut)
        self._pf_smooth_label.setEnabled(contour_cut)
        self._pf_reset.setVisible(path in self._file_overrides)
        self._load_piece_size(path)

    def _load_piece_size(self, path) -> None:
        """Carrega no editor o tamanho do arquivo da peça (override ou original)."""
        # não sobrescreve o que o usuário esta digitando (reselecao após relayout
        # chama isto; sem o guard, o campo voltava ao valor antigo no meio da digitacao).
        if self._ps_w.hasFocus() or self._ps_h.hasFocus():
            return
        base = next((b for b in self._base_artworks if self._path_of(b.id) == path), None)
        if base is None:
            return
        target = self._file_sizes.get(path, base.size)
        self._ps_loading = True
        try:
            self._ps_w.setValue(target.width)
            self._ps_h.setValue(target.height)
        finally:
            self._ps_loading = False
        self._ps_reset.setVisible(path in self._file_sizes)

    def _on_piece_faca_changed(self) -> None:
        """Grava a faca personalizada do arquivo selecionado e recalcula."""
        if self._pf_loading or not self._selected_path:
            return
        path = self._selected_path
        p = dict(self._params_for(path))
        sangria = float(self._pf_offset.value())
        if self._selected_is_image:
            p["auto_offset"] = sangria
        else:
            p["offset"] = sangria
        p["crop"] = float(self._pf_crop.value())
        p["rotation"] = int(self._pf_rotation.currentText())
        p["smooth"] = int(self._pf_smooth.value())
        p["mode"] = self._pf_mode.currentData()
        self._file_overrides[path] = p
        self._keep_tab = True
        try:
            self._relayout(renest=False)
            self._reselect_path(path)
        finally:
            self._keep_tab = False

    def _reset_piece_faca(self) -> None:
        """Remove a faca personalizada do arquivo: volta ao padrão do Documento."""
        if not self._selected_path:
            return
        path = self._selected_path
        self._file_overrides.pop(path, None)
        self._keep_tab = True
        try:
            self._relayout(renest=False)
            self._reselect_path(path)
        finally:
            self._keep_tab = False

    def _on_piece_size_changed(self, which: str) -> None:
        """Grava o tamanho desejado do arquivo selecionado e recalcula.

        Com 'Manter proporção' marcado, mudar um lado ajusta o outro pela
        proporção da arte original. Se o tamanho voltar ao original, o
        redimensionamento e removido (volta a seguir o arquivo importado).
        """
        if self._ps_loading or not self._selected_path:
            return
        path = self._selected_path
        base = next((b for b in self._base_artworks if self._path_of(b.id) == path), None)
        if base is None:
            return
        w = float(self._ps_w.value())
        h = float(self._ps_h.value())
        if self._ps_lock.isChecked():
            ratio = base.size.width / base.size.height
            self._ps_loading = True
            try:
                if which == "w":
                    h = w / ratio
                    self._ps_h.setValue(h)
                else:
                    w = h * ratio
                    self._ps_w.setValue(w)
            finally:
                self._ps_loading = False
        try:
            new_size = Size(w, h)
        except ValidationError:
            return
        if (
            abs(w - base.size.width) < 1e-6
            and abs(h - base.size.height) < 1e-6
        ):
            self._file_sizes.pop(path, None)
        else:
            self._file_sizes[path] = new_size
        self._keep_tab = True
        try:
            self._relayout(renest=False)
            self._reselect_path(path)
        finally:
            self._keep_tab = False

    def _reset_piece_size(self) -> None:
        """Remove o redimensionamento do arquivo: volta ao tamanho importado."""
        if not self._selected_path:
            return
        path = self._selected_path
        if path not in self._file_sizes:
            return
        self._file_sizes.pop(path, None)
        self._keep_tab = True
        try:
            self._relayout(renest=False)
            self._reselect_path(path)
        finally:
            self._keep_tab = False

    def _reselect_path(self, path) -> None:
        """Reseleciona a 1a peça do arquivo (mantem a aba Seleção após relayout)."""
        self._scene.clearSelection()
        for piece in self._piece_items:
            if self._path_of(piece.artwork_id) == path:
                piece.setSelected(True)
                break

    def _update_group_page(self, pieces: list[PieceItem]) -> None:
        boxes = [
            (p.pos().x(), p.pos().y(), p.rect().width(), p.rect().height()) for p in pieces
        ]
        g = measurements.group_metrics(boxes)
        self._gm_w.set_value(units.fmt_len(g.width))
        self._gm_h.set_value(units.fmt_len(g.height))
        self._gm_count.set_value(str(g.count))

    def _apply_tooltips(self) -> None:
        self._table.setToolTip("Arquivos e a quantidade de cópias de cada um")
        self._import_box.setToolTip(
            "Caixa de Mídia mantem a sangria; Caixa de Apara corta no traco de corte do PDF"
        )
        self._rotation.setToolTip("Gira todos os arquivos (graus)")
        self._width.setToolTip("Largura da chapa de material (mm)")
        self._height.setToolTip("Altura da chapa (mm). 0 = chapa única (comprimento aberto)")
        self._spacing.setToolTip("Espaco entre as peças (mm)")
        self._crop.setToolTip("Corta as bordas da arte (remove faixa branca) (mm)")
        self._shared.setToolTip("Faca por peça (quadrados) ou compartilhada (grade fora a fora)")
        self._reg_type.setToolTip("Tipo de marca de registro para a mesa de corte")
        self._mk_distance.setToolTip("Mimaki: distância do quadro até o conteudo (mm)")
        self._mk_size.setToolTip("Mimaki: tamanho das marcas em L (mm)")
        self._mk_thickness.setToolTip("Mimaki: espessura das marcas (mm)")
        self._view_mode.setToolTip("O que mostrar: impressao, corte, ambos ou tela dividida")
        self._show_rulers.setToolTip("Mostra/esconde as réguas (mm)")
        self._snap_check.setToolTip(
            "Encaixe magnetico: a peça gruda nas bordas/centro das outras e da chapa (Alt+Q)"
        )

    def _build_library_panel(self) -> QWidget:
        """Biblioteca de arquivos (esquerda): cada linha tem miniatura, nome,
        medida, páginas, tipo e quantidade. Dona do _table (contrato dos testes:
        col 0 = item com nome/⚠, col 1 = QuantityStepper)."""
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, theme.SPACE_XS, 0)
        lay.setSpacing(theme.SPACE_SM)

        # logo completa (simbolo + nome PRINTNEST PRO) no topo do painel
        logo_path = resource_path("assets/printnest.png")
        if logo_path.exists():
            pm = QPixmap(str(logo_path))
            if not pm.isNull():
                logo = QLabel()
                logo.setPixmap(pm.scaledToWidth(200, Qt.SmoothTransformation))
                logo.setAlignment(Qt.AlignHCenter)  # centraliza sobre o botão "+ Adicionar"
                logo.setContentsMargins(0, 2, 0, 4)
                lay.addWidget(logo)

        header = QLabel("Biblioteca")
        header.setStyleSheet(f"font-weight:600; color:{theme.TEXT};")
        lay.addWidget(header)

        self._btn_add = QPushButton("  Adicionar arquivos")
        self._btn_add.setIcon(icons.icon("plus", theme.ICON_ON_ACCENT))
        self._btn_add.setProperty("accent", "true")
        self._btn_add.clicked.connect(lambda: self.add_pdfs())
        lay.addWidget(self._btn_add)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Arquivo", "Qtd"])
        self._table.verticalHeader().setVisible(False)
        self._table.setColumnWidth(0, 210)
        self._table.setColumnWidth(1, 78)  # coluna Qtd estreita (campo pequeno)
        self._table.setIconSize(QSize(44, 44))  # miniatura maior (alvo/legibilidade)
        self._table.setWordWrap(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setDragEnabled(True)  # arrastar arquivo para a área de trabalho
        self._table.setDragDropMode(QAbstractItemView.DragOnly)
        self._table.itemSelectionChanged.connect(self._update_selection_info)
        lay.addWidget(self._table, 1)

        self._btn_crop = QPushButton("  Recortar...")
        self._btn_crop.setIcon(icons.icon("replace", theme.ICON))
        self._btn_crop.setToolTip(
            "Corta as bordas do arquivo selecionado (PDF ou imagem): arraste as\n"
            "bordas na previa. No PDF, vale para todas as páginas ou as que escolher."
        )
        self._btn_crop.clicked.connect(self._crop_pages_dialog)
        lay.addWidget(self._btn_crop)

        self._btn_remove = QPushButton("  Remover selecionado")
        self._btn_remove.setIcon(icons.icon("trash-2", theme.ICON))
        self._btn_remove.clicked.connect(lambda: self.remove_selected())
        lay.addWidget(self._btn_remove)

        cap_box = QLabel("Cortar para (caixa do PDF)")
        cap_box.setProperty("role", "caption")
        lay.addWidget(cap_box)
        self._import_box = QComboBox()
        self._import_box.addItem("Caixa de Mídia (sangria)", "media")
        self._import_box.addItem("Caixa de Apara (corte)", "trim")
        lay.addWidget(self._import_box)

        # "Rotacionar arquivo (graus)" saiu da UI (a rotação vive por peça: aba
        # Objeto e Ctrl+[ / Ctrl+]). O combo continua existindo (oculto) para o
        # estado/sessão e a lógica de giro global seguirem funcionando.
        self._rotation = QComboBox(panel)
        self._rotation.addItems(["0", "90", "180", "270"])
        self._rotation.currentIndexChanged.connect(lambda _: self._relayout())
        self._rotation.hide()

        self._sel_info = QLabel("Selecione um arquivo")
        self._sel_info.setWordWrap(True)
        self._sel_info.setProperty("role", "caption")
        lay.addWidget(self._sel_info)

        panel.setMinimumWidth(260)
        panel.setMaximumWidth(420)
        return panel

    # ---- aba Documento: cards modernos (UI). NAO altera o motor. ----
    def _doc_card(self, title: str, accent: str, *, collapsed: bool = False) -> CollapsibleCard:
        card = CollapsibleCard(title, collapsed=collapsed, accent=accent)
        self._doc_cards.append(card)
        return card

    @staticmethod
    def _grid_fields(body, rows) -> None:
        """Adiciona campos numa grade de 2 colunas (menos altura, mais organizado).
        rows: lista de (rotulo, widget, tooltip)."""
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(theme.SPACE_MD)
        grid.setVerticalSpacing(theme.SPACE_MD)  # 12px entre campos (grade de 8)
        for i, (label, widget, tip) in enumerate(rows):
            if tip:
                widget.setToolTip(tip)
            grid.addWidget(labeled(label, widget), i // 2, i % 2)
        body.addLayout(grid)

    def _build_resumo_card(self) -> CollapsibleCard:
        """Resumo da produção (somente leitura), atualizado automaticamente."""
        card = CollapsibleCard("Resumo da produção", accent="resumo")
        self._sum_material = MeasureField("Material")
        self._sum_pecas = MeasureField("Peças")
        self._sum_chapas = MeasureField("Chapas")
        self._sum_area = MeasureField("Área utilizada")
        self._sum_faca = MeasureField("Faca")
        self._sum_reg = MeasureField("Registro")
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(theme.SPACE_MD)
        grid.setVerticalSpacing(theme.SPACE_SM)
        fields = [self._sum_material, self._sum_pecas, self._sum_chapas,
                  self._sum_area, self._sum_faca, self._sum_reg]
        for i, f in enumerate(fields):
            grid.addWidget(f, i // 2, i % 2)
        card.body.addLayout(grid)
        return card

    def _build_producao_card(self) -> CollapsibleCard:
        """Secao 1 - Produção (sempre aberta): o que se usa 95% do tempo."""
        card = self._doc_card("Produção", "produção")
        self._width = LengthSpin(1, 20000)
        self._width.valueChanged.connect(lambda _: self._relayout())
        self._height = LengthSpin(0, 20000)
        self._height.valueChanged.connect(lambda _: self._relayout())
        self._grid_fields(card.body, [
            ("Largura da chapa", self._width,
             "Largura útil da chapa/bobina onde as peças são encaixadas."),
            ("Altura (0 = única)", self._height,
             "Altura da chapa. 0 = chapa única (cresce conforme o conteudo)."),
        ])
        self._spacing = LengthSpin(-500, 500)
        self._spacing.valueChanged.connect(lambda _: self._relayout())
        self._spacing_v = LengthSpin(-500, 500)
        self._spacing_v.valueChanged.connect(lambda _: self._relayout())
        self._grid_fields(card.body, [
            ("Espaçamento horizontal", self._spacing,
             "Espaco entre as peças na MESMA linha. Negativo aproxima/sobrepoe\n"
             "os retângulos (útil p/ peça redonda, fecha o vão branco)."),
            ("Espaçamento vertical", self._spacing_v,
             "Espaco entre as LINHAS (para cima/baixo). Negativo aproxima."),
        ])
        self._center_check = QCheckBox("Manter centralizado na chapa")
        self._center_check.setChecked(self._center_on_sheet)
        self._center_check.setToolTip(
            "Ligado: o conteudo fica centralizado na chapa automaticamente.\n"
            "DESMARQUE para posicionar/arrastar as peças livremente na página."
        )
        self._center_check.toggled.connect(self._set_center_on_sheet)
        card.body.addWidget(self._center_check)
        self._offset = LengthSpin(-100, 100)
        self._offset.setToolTip(
            "Sangria da faca de PDF (vale nos 3 modos: retângulo, pelo contorno e\n"
            "faca do cliente). Positivo afasta a faca para FORA da arte (sangria);\n"
            "negativo recolhe para DENTRO (recuo). Para imagens, use o campo próprio."
        )
        self._offset.valueChanged.connect(lambda _: self._relayout(renest=False))
        card.body.addWidget(labeled("Sangria da faca (PDF)  ( + fora  /  − dentro )", self._offset))
        return card

    def _build_acabamento_card(self) -> CollapsibleCard:
        """Secao 2 - Acabamento (recolhida): recorte e tipo de faca."""
        card = self._doc_card("Acabamento", "acabamento", collapsed=True)
        self._crop = LengthSpin(0, 100)
        self._crop.valueChanged.connect(lambda _: self._relayout(renest=False))
        card.body.addWidget(self._labeled_tip(
            "Recorte da arte (cortar bordas)", self._crop,
            "Corta as bordas da arte (mm em cada lado) antes de gerar a faca."
        ))
        self._faca_mode = NoWheelComboBox()
        for label, data in self._FACA_MODES:
            self._faca_mode.addItem(label, data)
        self._faca_mode.setToolTip(
            "Automático: escolhe sozinho - JPG/fundo solido vira retângulo,\n"
            "imagem com transparência (PNG) corta no formato (recorte).\n"
            "Retângulo: corta a caixa por fora (corte reto), vale p/ imagem também.\n"
            "Contorno justo: corta no formato do desenho (rasteriza).\n"
            "Contorno suave: idem, arredondando os cantos/serrilhado.\n"
            "Contorno simplificado: idem, com menos nos (faca mais leve).\n"
            "Faca do cliente: usa a linha de corte vetorial que veio no PDF."
        )
        self._faca_mode.currentIndexChanged.connect(lambda _: self._relayout(renest=False))
        # o combo "Tipo de faca" NAO fica neste card: ele mora na barra de cima,
        # colado ao botão "Gerar Faca" (escolher o tipo -> gerar, um gesto só).
        self._shared = NoWheelComboBox()
        self._shared.addItems(["Faca por peça (quadrados)", "Faca compartilhada (grade)"])
        self._shared.setToolTip(
            "Faca por peça: cada peça tem seu retângulo de corte.\n"
            "Faca compartilhada: bordas coladas viram uma só linha (grade)."
        )
        self._shared.currentIndexChanged.connect(lambda _: self._relayout(renest=False))
        card.body.addWidget(labeled("Modo da faca", self._shared))
        return card

    def _build_imagens_card(self) -> CollapsibleCard:
        """Secao 3 - Imagens (recolhida): faca automática de PNG/JPG/WEBP."""
        card = self._doc_card("Imagens", "imagens", collapsed=True)
        self._auto_sensitivity = _spin(0, 100)
        self._auto_smooth = _spin(0, 5)
        self._auto_smooth.valueChanged.connect(lambda _: self._relayout(renest=False))
        self._grid_fields(card.body, [
            ("Sensibilidade (0-100)", self._auto_sensitivity,
             "Sensibilidade da detecção do contorno em imagens (0-100)."),
            ("Suavizar curvas (0-5)", self._auto_smooth,
             "Suaviza o contorno da faca: 0 = reto, 5 = macio."),
        ])
        self._auto_offset = LengthSpin(-100, 100)
        self._auto_offset.setToolTip(
            "Sangria da faca da imagem: positivo afasta para FORA do desenho;\n"
            "negativo recolhe para DENTRO (recuo)."
        )
        self._auto_offset.valueChanged.connect(lambda _: self._relayout(renest=False))
        card.body.addWidget(labeled("Sangria da faca (imagem)", self._auto_offset))
        self._auto_ignore_white = QCheckBox("Remover fundo automático (imagens opacas)")
        self._auto_ignore_white.setToolTip(
            "Detecta a cor do fundo pela borda e a remove (branco, escuro ou colorido).\n"
            "Desmarcado: a faca fica no retângulo da imagem inteira."
        )
        card.body.addWidget(self._auto_ignore_white)
        return card

    def _build_registro_card(self) -> CollapsibleCard:
        """Secao 4 - Marcas de registro (recolhida)."""
        card = self._doc_card("Marcas de registro", "registro", collapsed=True)
        self._reg_type = NoWheelComboBox()
        self._reg_type.addItem("Nenhum", "none")
        self._reg_type.addItem("IECHO (bolinhas)", "circles")
        self._reg_type.addItem("Mimaki (marcas em L)", "mimaki")
        self._reg_type.addItem("Mimaki + IECHO", "both")  # cortar na Mimaki, refilar na IECHO
        self._reg_type.currentIndexChanged.connect(lambda _: self._relayout(renest=False))
        card.body.addWidget(labeled("Tipo de registro", self._reg_type))
        self._reg_margin = LengthSpin(0, 200)
        self._reg_diameter = LengthSpin(1, 50)
        self._grid_fields(card.body, [
            ("Bolinhas: afastamento", self._reg_margin,
             "Distância das bolinhas até as bordas da chapa (mm)."),
            ("Bolinhas: diâmetro", self._reg_diameter,
             "Diâmetro das bolinhas de registro (mm)."),
        ])
        self._mk_distance = LengthSpin(0, 200)
        self._mk_distance.valueChanged.connect(lambda _: self._relayout(renest=False))
        self._mk_size = LengthSpin(1, 100)
        self._mk_size.valueChanged.connect(lambda _: self._relayout(renest=False))
        self._grid_fields(card.body, [
            ("Mimaki: distância", self._mk_distance,
             "Distância do quadro (frame) até o conteudo (mm)."),
            ("Mimaki: tamanho", self._mk_size, "Tamanho das marcas em L (mm)."),
        ])
        self._mk_thickness = LengthSpin(0.1, 10)
        card.body.addWidget(self._labeled_tip(
            "Mimaki: espessura da marca", self._mk_thickness,
            "Espessura das marcas de registro (mm)."
        ))
        return card

    def _build_avancado_card(self) -> CollapsibleCard:
        """Secao 5 - Avançado (recolhida): ações tecnicas."""
        card = self._doc_card("Avançado", "avançado", collapsed=True)
        self._btn_reset_faca = QPushButton("  Restaurar padrões da faca")
        self._btn_reset_faca.setIcon(icons.icon("rotate-ccw", theme.ICON))
        self._btn_reset_faca.setToolTip(
            "Zera sangria, recuo, recorte, giro e suavização para a faca sair exata\n"
            "no contorno. Aplicado sozinho a cada novo arquivo importado."
        )
        self._btn_reset_faca.clicked.connect(self._reset_faca_defaults)
        card.body.addWidget(self._btn_reset_faca)
        return card

    @staticmethod
    def _labeled_tip(label: str, widget, tip: str):
        widget.setToolTip(tip)
        return labeled(label, widget)

    def _apply_compact_mode(self, on: bool) -> None:
        """Modo Compacto: reduz espaçamentos e a altura dos campos (notebooks)."""
        self._doc_layout.setSpacing(theme.SPACE_XS if on else theme.SPACE_SM)
        gap = theme.SPACE_XS if on else theme.SPACE_SM
        for card in self._doc_cards:
            card.body.setSpacing(gap)
        # altura dos campos (spins/combos) do documento
        spins = (self._doc_widget.findChildren(QDoubleSpinBox)
                 + self._doc_widget.findChildren(QSpinBox)
                 + self._doc_widget.findChildren(QComboBox))
        for sp in spins:
            sp.setMaximumHeight(24 if on else 16777215)

    def _update_resumo(self) -> None:
        """Atualiza o card 'Resumo da produção' (somente leitura)."""
        if not hasattr(self, "_sum_material"):
            return
        fields = (self._sum_material, self._sum_pecas, self._sum_chapas,
                  self._sum_area, self._sum_faca, self._sum_reg)
        r = self._result
        if r is None or not r.sheets:
            for f in fields:
                f.set_value("—")
            return
        mat = r.sheets[0].material
        total = sum(s.item_count for s in r.sheets)
        pct = round(max(
            measurements.sheet_metrics(s, r.artworks).used_pct for s in r.sheets
        ))
        height = float(self._height.value()) or max((s.used_length for s in r.sheets), default=0)
        off = float(self._offset.value())
        sinal = "+" if off >= 0 else "−"
        self._sum_material.set_value(
            f"{units.fmt_len(mat.width, with_unit=False)} x {units.fmt_len(height)}"
        )
        self._sum_pecas.set_value(str(total))
        self._sum_chapas.set_value(str(len(r.sheets)))
        self._sum_area.set_value(f"{pct}%")
        self._sum_faca.set_value(f"{sinal}{units.fmt_len(abs(off))}")
        self._sum_reg.set_value(self._reg_type.currentText())

    def _build_display_controls(self) -> QWidget:
        """Painel de Exibição (réguas, snap) usado no popup do botão 'Exibição'
        da barra de cima. O modo de visualização mora na barrinha flutuante do
        canvas (FloatingDisplayBar); a unidade, no menu 'Opções'."""
        panel = QWidget()
        panel.setObjectName("displayPopup")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(5)

        self._show_rulers = QCheckBox("Mostrar réguas")
        self._show_rulers.toggled.connect(lambda _: self._apply_rulers_visibility())
        lay.addWidget(self._show_rulers)
        self._snap_check = QCheckBox("Encaixar peças ao arrastar (snap)")
        self._snap_check.toggled.connect(self._set_snap)
        lay.addWidget(self._snap_check)

        panel.setMinimumWidth(232)
        return panel

    def _apply_rulers_visibility(self) -> None:
        visible = self._show_rulers.isChecked()
        self._h_ruler.setVisible(visible)
        self._v_ruler.setVisible(visible)
        self._corner.setVisible(visible)

    def _on_unit_changed(self, unit: str) -> None:
        """Troca a unidade (mm/cm) em todo o sistema: campos, réguas e medidas."""
        units.set_unit(unit)
        for spin in self.findChildren(LengthSpin):
            spin.refresh_unit()
        self._h_ruler.update()
        self._v_ruler.update()
        self._update_selection_info()  # medida do arquivo na biblioteca
        self._on_selection_changed()   # painel da peça/grupo + overlay
        if self._loaded:
            self._save_settings()

    # ---- settings ----
    def _load_settings(self) -> None:
        s = self._settings
        self._width.setValue(int(s.material_width))
        self._height.setValue(int(s.material_height))
        self._spacing.setValue(s.spacing)
        self._spacing_v.setValue(s.spacing_v)
        # campo único com sinal: deriva do par antigo (offset - recuo) p/ compat
        self._offset.setValue(s.offset - s.safety_inset)
        self._crop.setValue(s.crop)
        self._faca_mode.setCurrentIndex(max(0, self._faca_mode.findData(s.faca_mode)))
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
        units.set_unit(s.unit)
        if hasattr(self, "_act_unit_mm"):
            self._act_unit_mm.setChecked(s.unit == units.MM)
            self._act_unit_cm.setChecked(s.unit != units.MM)
        self._snap_check.setChecked(s.snap_enabled)
        self._set_snap(s.snap_enabled)
        self._view_mode.setCurrentIndex(max(0, self._view_mode.findData(s.view_mode)))
        self._import_box.setCurrentIndex(max(0, self._import_box.findData(s.import_box)))
        self._auto_sensitivity.setValue(int(s.auto_sensitivity))
        self._auto_ignore_white.setChecked(s.auto_ignore_white)
        self._auto_offset.setValue(s.auto_offset_external - s.auto_offset_internal)
        self._auto_smooth.setValue(int(s.auto_smooth))

    def _save_settings(self) -> None:
        s = self._settings
        s.material_width = float(self._width.value())
        s.material_height = float(self._height.value())
        s.spacing = float(self._spacing.value())
        s.spacing_v = float(self._spacing_v.value())
        # campo único com sinal -> guarda no 'offset' e zera o antigo 'safety_inset'
        s.offset = float(self._offset.value())
        s.safety_inset = 0.0
        s.crop = float(self._crop.value())
        s.faca_mode = self._faca_mode.currentData()
        s.rotation = self._rotation_value()
        s.shared_faca = self._shared.currentIndex() == 1
        s.reg_type = self._reg_type.currentData()
        s.reg_margin = float(self._reg_margin.value())
        s.reg_diameter = float(self._reg_diameter.value())
        s.mimaki_distance = float(self._mk_distance.value())
        s.mimaki_size = float(self._mk_size.value())
        s.mimaki_thickness = float(self._mk_thickness.value())
        s.show_rulers = self._show_rulers.isChecked()
        s.unit = units.unit()
        s.view_mode = self._view_mode.currentData()
        s.import_box = self._import_box.currentData()
        s.snap_enabled = self._snap.enabled
        s.auto_sensitivity = float(self._auto_sensitivity.value())
        s.auto_ignore_white = self._auto_ignore_white.isChecked()
        s.auto_offset_external = float(self._auto_offset.value())
        s.auto_offset_internal = 0.0
        s.auto_smooth = int(self._auto_smooth.value())
        self._store.save(s)

    # ---- helpers de leitura ----
    def _rotation_value(self) -> int:
        return int(self._rotation.currentText())

    def _reg(self) -> str:
        return self._reg_type.currentData()

    def _effective_offset(self) -> float:
        # campo único com sinal: +fora (sangria), -dentro (recuo)
        return float(self._offset.value())

    def _global_faca_params(self) -> dict:
        """Parametros de faca do painel Documento (padrão para arquivos novos)."""
        return {
            "offset": float(self._offset.value()),       # faca PDF (retangular)
            "auto_offset": float(self._auto_offset.value()),  # faca de imagem
            "crop": float(self._crop.value()),
            "rotation": self._rotation_value(),
            "smooth": int(self._auto_smooth.value()),
            "corner": self._faca_corner,  # canto do contorno: round/miter/bevel
            "mode": self._faca_mode.currentData(),  # ver _FACA_MODES (auto/rect/...)
        }

    def _params_for(self, path) -> dict:
        """Params de faca efetivos do arquivo: override próprio ou o padrão."""
        override = self._file_overrides.get(path)
        return dict(override) if override else self._global_faca_params()

    def _art_params(self, art_id) -> dict:
        """Params efetivos de UMA peça: os do arquivo + o giro próprio da peça.

        A rotação da peça (self._piece_rotations) soma ao giro do arquivo, sem
        afetar as outras páginas/cópias. Como toda a geometria (tamanho, faca,
        pixmap) sai daqui, girar uma peça se propaga ao nesting e a exportação.
        """
        params = self._params_for(self._path_of(art_id))
        extra = self._piece_rotations.get(art_id, 0)
        if extra:
            params["rotation"] = (int(params.get("rotation", 0)) + extra) % 360
        return params

    def _rotation_of(self, art_id) -> int:
        """Giro efetivo (graus) de uma peça: arquivo + giro próprio."""
        return int(self._art_params(art_id).get("rotation", 0))

    def _path_of(self, art_id) -> str | None:
        return self._origins.get(art_id) or self._sources.get(art_id, (None,))[0]

    def _faca_for(self, base):
        """Aplica a faca do arquivo (override ou padrão) a uma arte base.

        Antes da faca, aplica o tamanho desejado do arquivo (redimensionamento):
        escala a arte e os contornos pelos mesmos fatores, para a faca sair
        coerente em qualquer modo (retângulo, contorno, vetor ou imagem).
        """
        path = self._path_of(base.id)
        params = self._art_params(base.id)
        base, sx, sy = self._resized_base(base, path)
        if not self._faca_on:
            # modo "soltar sem faca": só a arte (com recorte/giro/tamanho), sem
            # gerar a faca. A faca surge ao clicar "Gerar Faca"/"Gerar Produção".
            return self._transform(base, params)
        is_img = isinstance(base, ImageArtwork)
        # imagem usa a "sangria de imagem" (auto_offset); PDF usa a sangria da faca.
        sangria = params["auto_offset"] if is_img else params["offset"]
        mode = self._resolve_faca_mode(params.get("mode", "auto"), base)
        if mode == "rect":  # corte reto por fora (vale p/ imagem e PDF)
            return self._faca_uc.execute(self._transform(base, params), sangria)
        if mode == "vector":  # faca do cliente (linha vetorial do PDF)
            raw = self._scaled_contour(self._pdf_vector_contour(base), sx, sy)
            return self._contour_faca(base, raw, params, params["offset"])
        # contorno (justo / suave / simplificado), para imagem ou PDF rasterizado
        if is_img:
            raw = base.raw_contour
        else:
            raw = self._scaled_contour(self._pdf_raster_contour(base), sx, sy)
        return self._contour_faca(base, raw, params, sangria, mode)

    def _resolve_faca_mode(self, mode: str, base) -> str:
        """Resolve o modo 'auto' pelo tipo da arte e valida o modo pedido.

        - PDF: 'auto' -> retângulo (corte reto da caixa).
        - Imagem opaca (JPG / fundo solido): 'auto' -> retângulo. Assim um JPG
          retangular sai quadrado, sem serrilhado do contorno.
        - Imagem com transparência (PNG alpha): 'auto' -> contorno (recorte).
        - 'vector' só faz sentido em PDF; numa imagem cai para contorno.
        """
        if isinstance(base, ImageArtwork):
            if mode == "vector":
                return "contour"
            if mode == "auto":
                return "contour" if base.image_kind == ImageKind.IMAGE_ALPHA else "rect"
            return mode
        if mode == "auto":
            return "rect"
        return mode

    def _resized_base(self, base, path):
        """Aplica o tamanho desejado do arquivo (se houver) a arte base.

        Retorna (arte, sx, sy): a arte com o novo tamanho e os fatores de escala
        para escalar contornos correspondentes. Para imagens, escala também o
        contorno bruto (raw_contour) junto com o tamanho.
        """
        target = self._file_sizes.get(path)
        if target is None:
            return base, 1.0, 1.0
        sx = target.width / base.size.width
        sy = target.height / base.size.height
        if isinstance(base, ImageArtwork) and base.raw_contour is not None:
            raw = self._scaled_contour(base.raw_contour, sx, sy)
            return replace(base, size=target, raw_contour=raw), sx, sy
        return replace(base, size=target), sx, sy

    @staticmethod
    def _scaled_contour(contour, sx, sy):
        """Escala um contorno de corte pelos fatores (sx, sy). None -> None."""
        if contour is None or (sx == 1.0 and sy == 1.0):
            return contour
        return CutContour(tuple(Point2D(p.x * sx, p.y * sy) for p in contour.points))

    def _pdf_vector_contour(self, base):
        """Faca do cliente: extrai o contorno vetorial do PDF (a linha de corte
        que o cliente já desenhou). Cacheado por (caminho, página). Se não houver
        vetor utilizavel, registra um aviso e cai no retângulo (raw=None)."""
        key = self._sources.get(base.id)
        if key is None:
            return None
        if key in self._vector_contours:
            return self._vector_contours[key]
        path, page = key
        try:
            rings = self._vector_extractor.extract_rings(path, page)
            contour = self._vector_generator.generate(rings)
            self._faca_notice = (
                "info",
                f"Faca do cliente detectada no vetor do PDF ({len(contour.points)} pontos).",
            )
        except Exception:  # sem vetor de corte utilizavel -> retângulo
            contour = None
            self._faca_notice = (
                "warning",
                "Não encontrei linha de corte vetorial no PDF; usei o retângulo. "
                "Verifique se o corte foi enviado como vetor.",
            )
        self._vector_contours[key] = contour
        return contour

    def _regenerate_faca(self) -> None:
        """Botão 'Gerar Faca': refaz a detecção da faca (contorno/cliente) e
        recalcula, sem precisar reimportar nem refazer o nesting do zero.

        Sem produção ainda: gera a produção JA com faca (assim o botão azul
        sempre funciona, ex.: depois de remover tudo e soltar outro arquivo)."""
        if not self._loaded:
            if self._paths:
                self.generate(blocking=True, faca=True)
            else:
                self._toasts.info("Adicione arquivos na biblioteca primeiro.")
            return
        self._pdf_contours = {}
        self._vector_contours = {}
        self._faca_on = True  # liga a faca (modo "soltar sem faca" -> gera agora)
        self._relayout(renest=False)  # gera a faca; mantem o arranjo manual
        self._toasts.success("Faca gerada")

    def _pdf_raster_contour(self, base):
        """Contorno de uma página de PDF: rasteriza e detecta (igual imagem).
        Cacheado por (caminho, página); recomputado a cada nova produção."""
        key = self._sources.get(base.id)
        if key is None:
            return None
        cached = self._pdf_contours.get(key)
        if cached is not None:
            return cached
        path, page = key
        try:
            data = self._renderer.render_png(
                path, page, dpi=PDF_CONTOUR_DPI, box=self._import_box.currentData()
            )
            contour = self._contour_detector.detect_contour_from_png(
                data, PDF_CONTOUR_DPI,
                sensitivity=float(self._auto_sensitivity.value()),
                ignore_white=self._auto_ignore_white.isChecked(),
            )
        except Exception:  # se falhar a detecção, cai no retângulo
            contour = None
        self._pdf_contours[key] = contour
        return contour

    def _contour_faca(self, base, raw_contour, params, sangria, mode="contour"):
        """Monta a faca a partir de um contorno (imagem, PDF rasterizado ou vetor
        do cliente): aplica recorte + giro + suavizar + sangria. A 'sangria' vem
        do chamador (PDF usa a "Sangria da faca"; imagem usa a sangria da imagem).
        Sem contorno utilizavel, cai no RETANGULO com a mesma sangria (igual ao
        modo retângulo), em vez de ignora-la.

        'mode' escolhe a variacao do contorno: 'contour' (justo, respeita os
        controles manuais), 'contour_smooth' (forca mais suavização, arredonda o
        serrilhado) ou 'contour_simplify' (forca mais simplificacao, menos nos)."""
        crop = params["crop"]
        rotation = params["rotation"]
        if raw_contour is None:
            # sem contorno: retângulo do tamanho da arte, COM a sangria aplicada
            return self._faca_uc.execute(self._transform(base, params), sangria)
        contour, w, h = crop_and_rotate_contour(
            raw_contour, crop, rotation, base.size.width, base.size.height
        )
        tol = self._density_tol()  # densidade: reduz nos/ruido antes de suavizar
        if mode == "contour_simplify":
            tol = max(tol, 0.6)  # variacao "simplificado": garante menos nos
        if tol > 0:
            contour = simplify_contour(contour, tol)
        smooth = int(params["smooth"])
        if mode == "contour_smooth":
            smooth = max(smooth, 3)  # variacao "suave": garante arredondamento
        if smooth > 0:
            contour = smooth_contour(contour, smooth)
        if sangria != 0:
            contour = offset_contour(contour, sangria, params.get("corner", "round"))
        return replace(base, size=Size(w, h), cut_contour=contour)

    def _density_tol(self) -> float:
        """Tolerancia de simplificacao (mm) a partir da 'Densidade da faca'.
        Densidade 10 = 0 (segue fiel, sem simplificar); menor = faca mais lisa."""
        if not hasattr(self, "_auto_density"):
            return 0.0
        d = int(self._auto_density.value())
        return max(0.0, (10 - d) * 0.12)

    def _transform(self, art, params: dict):
        """Aplica recorte (bordas) e rotação a uma arte (tamanho)."""
        crop = params["crop"]
        width = art.size.width - 2 * crop
        height = art.size.height - 2 * crop
        if params["rotation"] % 360 in (90, 270):
            width, height = height, width
        return replace(art, size=Size(width, height), cut_contour=None)

    def _reset_faca_defaults(self) -> None:
        """Volta as configurações de faca ao padrão seguro (faca exata no
        contorno: sem sangria, recuo, recorte, giro ou suavização).

        Chamado pelo botão 'Restaurar padrões' e automaticamente a cada novo
        arquivo importado, para a faca sempre sair certa, sem herdar valores
        antigos que deixavam a faca torta.
        """
        self._suspend_relayout = True
        try:
            self._offset.setValue(0)
            self._crop.setValue(0)
            self._auto_offset.setValue(0)
            self._auto_smooth.setValue(0)
            self._auto_sensitivity.setValue(50)
            self._auto_ignore_white.setChecked(True)
            self._faca_corner = "round"  # canto padrão seguro
            self._rotation.setCurrentIndex(0)  # 0 graus
            self._faca_mode.setCurrentIndex(0)  # Automático (padrão)
        finally:
            self._suspend_relayout = False
        self._relayout()

    def _reset_all_defaults(self) -> None:
        """Zera TODAS as configurações de layout/faca ao padrão seguro: alem da
        faca, zera o espaçamento horizontal e vertical (o -35 que sobrepunha as
        peças) e descarta tamanhos/facas personalizados por arquivo. Mantem o
        tamanho da chapa (material fisico da impressora).

        Chamado ao adicionar arquivo com a área de trabalho VAZIA, para nunca
        herdar valores antigos de outra sessao. Quando já ha arquivos na área,
        não zera (preserva as configurações atuais)."""
        self._suspend_relayout = True
        try:
            self._spacing.setValue(0)
            self._spacing_v.setValue(0)
            self._offset.setValue(0)
            self._crop.setValue(0)
            self._auto_offset.setValue(0)
            self._auto_smooth.setValue(0)
            self._auto_sensitivity.setValue(50)
            self._auto_ignore_white.setChecked(True)
            self._faca_corner = "round"  # canto padrão seguro
            self._rotation.setCurrentIndex(0)
            self._faca_mode.setCurrentIndex(0)
            self._reg_type.setCurrentIndex(0)  # SEM marcas por padrão (ligue quando quiser)
        finally:
            self._suspend_relayout = False
        self._file_overrides = {}
        self._file_sizes = {}
        self._piece_rotations = {}
        self._relayout()

    # ---- lista de arquivos ----
    def add_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar arquivos (PDF / imagem)", self._settings.last_dir,
            IMAGE_FILE_FILTER,
        )
        if paths:
            was_empty = not self._paths  # área de trabalho vazia ANTES deste add
            self.add_paths(paths)
            if was_empty:
                # área vazia: zera TUDO (inclui espaçamento) para não herdar
                # valores de outra sessao (ex.: o -35 que sobrepunha as peças).
                self._reset_all_defaults()
            else:
                # já ha arquivos: preserva as configurações atuais; só garante a
                # faca no padrão do novo arquivo.
                self._reset_faca_defaults()
            self._settings.last_dir = str(Path(paths[0]).parent)
            self._store.save(self._settings)

    def add_paths(self, paths: list[str]) -> None:
        for path in paths:
            # arquivo JA na biblioteca: NAO cria linha duplicada — soma +1 na
            # quantidade da linha existente. Duas linhas do mesmo caminho
            # colidiam nos ids/quantidades (indexados por caminho) e a produção
            # saia com quantidade ERRADA sem aviso (bug QA-04).
            if path in self._paths:
                row = self._paths.index(path)
                spin = self._table.cellWidget(row, 1)
                if spin is not None:
                    spin.setValue(min(spin.value() + 1, spin.maximum()))
                self._toasts.info(
                    f"{Path(path).name} já está na biblioteca — quantidade +1"
                )
                continue
            row = self._table.rowCount()
            self._table.insertRow(row)
            item = QTableWidgetItem(f"{Path(path).name}\n{self._file_type(path)}")
            item.setIcon(self._thumbnail(path))
            self._table.setItem(row, 0, item)
            spin = QuantityStepper(1, 100000, 1)
            spin.valueChanged.connect(lambda _: self._relayout(from_table=True))
            self._table.setCellWidget(row, 1, spin)
            self._table.setRowHeight(row, 52)  # linha com respiro (miniatura 44)
            self._paths.append(path)

    @staticmethod
    def _file_type(path: str) -> str:
        return Path(path).suffix.lstrip(".").upper() or "?"

    def _thumbnail(self, path: str) -> QIcon:
        """Miniatura do arquivo (1a página do PDF ou a própria imagem)."""
        cached = self._thumb_cache.get(path)
        if cached is not None:
            return cached
        pixmap = QPixmap()
        try:
            if Path(path).suffix.lower() == ".pdf":
                data = self._renderer.render_png(
                    path, 0, dpi=18, box=self._import_box.currentData()
                )
                pixmap.loadFromData(data, "PNG")
            else:
                pixmap = QPixmap(path)
        except Exception:  # miniatura e opcional; nunca quebra a importacao
            pixmap = QPixmap()
        if pixmap.isNull():
            result = icons.icon("image", theme.TEXT_MUTED, 40)
        else:
            result = QIcon(
                pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        self._thumb_cache[path] = result
        return result

    def _refresh_library_metadata(self) -> None:
        """Atualiza a 2a linha de cada arquivo na biblioteca com tipo, medida e
        páginas (após gerar a produção). Preserva linhas ausentes (⚠)."""
        info: dict[str, tuple[set, set]] = {}
        for art in self._base_artworks:
            src = self._sources.get(art.id)
            if src is None:
                continue
            pages, dims = info.setdefault(src[0], (set(), set()))
            pages.add(src[1])
            dims.add((round(art.size.width, 1), round(art.size.height, 1)))
        for row in range(min(self._table.rowCount(), len(self._paths))):
            item = self._table.item(row, 0)
            if item is None or item.text().startswith("⚠"):
                continue
            path = self._paths[row]
            meta = self._file_type(path)
            if path in info:
                pages, dims = info[path]
                if dims:
                    w, h = next(iter(dims))
                    meta += (
                        f" · {units.fmt_len(w, with_unit=False)}"
                        f"×{units.fmt_len(h)}"
                    )
                if len(pages) > 1:
                    meta += f" · {len(pages)} pag"
            item.setText(f"{Path(path).name}\n{meta}")

    def remove_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        path = self._paths[row]
        self._table.removeRow(row)
        del self._paths[row]
        # remove também da PRODUCAO: senao a arte continua na chapa mesmo saindo
        # da biblioteca (peça "presa" na tela, principalmente com um só arquivo).
        removed = {b.id for b in self._base_artworks if self._path_of(b.id) == path}
        if removed:
            self._base_artworks = [b for b in self._base_artworks if b.id not in removed]
            self._piece_items = [p for p in self._piece_items if p.artwork_id not in removed]
        if not self._base_artworks:
            # removeu tudo: limpa a produção para o proximo arquivo comecar do ZERO
            # (senao _result fica desatualizado e o proximo drop/gerar não funciona).
            self._result = None
            self._loaded = False
            self._scene.clear()
            self._decor_items = []
            self._piece_items = []
            self._status_ctl.set_production(0, 0)
            self._alert.clear()
            return
        self._relayout()

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
                sizes.append(
                    f"{units.fmt_len(art.size.width, with_unit=False)} "
                    f"x {units.fmt_len(art.size.height)}"
                )
        if sizes:
            self._sel_info.setText(f"{name}\n" + " | ".join(sizes))
        else:
            self._sel_info.setText(f"{name}\n(gere a produção para ver a medida)")

    def _quantities(self) -> dict[str, int]:
        """Quantidade por arquivo, lida da tabela (path -> qtd)."""
        result: dict[str, int] = {}
        for row in range(self._table.rowCount()):
            spin = self._table.cellWidget(row, 1)
            result[self._paths[row]] = spin.value() if spin else 1
        return result

    def _crop_pages_dialog(self) -> None:
        """Dialogo de recorte visual do arquivo selecionado (PDF ou imagem):
        arraste as bordas para cortar. Mesmo esquema para os dois."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._paths):
            QMessageBox.information(self, "PrintNest", "Selecione um arquivo na biblioteca.")
            return
        path = self._paths[row]
        is_pdf = Path(path).suffix.lower() == ".pdf"
        if is_pdf:
            try:
                import fitz
                total = fitz.open(path).page_count
            except Exception:
                QMessageBox.warning(self, "PrintNest", "Não foi possível abrir o PDF.")
                return
        else:
            total = 1  # imagem = uma "página"

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Recortar — {Path(path).name}")
        dlg.resize(760, 480)
        root = QVBoxLayout(dlg)
        body = QHBoxLayout()
        root.addLayout(body, 1)

        # --- coluna esquerda: campos ---
        left_col = QWidget()
        form = QFormLayout(left_col)
        titulo = (f"PDF com {total} página(s)." if is_pdf else "Imagem.")
        form.addRow(QLabel(f"{titulo}\nArraste as bordas ou digite (mm):"))
        spins = {}
        existing = self._page_crops.get(path, {})
        first = next(iter(existing.values()), (0.0, 0.0, 0.0, 0.0))
        for key, rotulo in (("top", "Cima"), ("bottom", "Baixo"),
                            ("left", "Esquerda"), ("right", "Direita")):
            sp = LengthSpin(0, 1000)
            idx = {"left": 0, "top": 1, "right": 2, "bottom": 3}[key]
            sp.setValue(first[idx])
            spins[key] = sp
            form.addRow(rotulo, sp)
        pages_edit = QLineEdit("todas")
        pages_edit.setToolTip("'todas' ou páginas especificas, ex.: 1,3-5")
        prev_page = QSpinBox()
        prev_page.setRange(1, total)
        if is_pdf:  # páginas só fazem sentido em PDF; imagem tem uma só
            form.addRow("Páginas", pages_edit)
            form.addRow("Pre-visualizar página", prev_page)
        body.addWidget(left_col)

        # --- coluna direita: pre-visualização ---
        preview = CropPreview()
        body.addWidget(preview, 1)

        # binding bidirecional campos <-> preview
        def push_to_preview():
            preview.set_crop(spins["left"].value(), spins["top"].value(),
                             spins["right"].value(), spins["bottom"].value())

        def pull_from_preview():
            for k, v in zip(("left", "top", "right", "bottom"), preview.crop(), strict=False):
                spins[k].blockSignals(True)
                spins[k].setValue(v)
                spins[k].blockSignals(False)

        def render_preview():
            try:
                data = self._renderer.render_png(
                    path, prev_page.value() - 1, dpi=110,
                    box=self._import_box.currentData(),
                )
                pm = QPixmap()
                pm.loadFromData(data, "PNG")
                if not pm.isNull():
                    preview.set_page(pm, pm.width() * 25.4 / 110.0, pm.height() * 25.4 / 110.0)
            except Exception:
                pass
            push_to_preview()

        for sp in spins.values():
            sp.valueChanged.connect(lambda _=0: push_to_preview())
        preview.crop_changed.connect(pull_from_preview)
        prev_page.valueChanged.connect(lambda _=0: render_preview())
        render_preview()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg
        )
        clear_btn = buttons.addButton("Remover recorte", QDialogButtonBox.DestructiveRole)
        root.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        clear_btn.clicked.connect(lambda: (self._clear_page_crop(path), dlg.reject()))
        if dlg.exec() != QDialog.Accepted:
            return

        left = float(spins["left"].value())
        top = float(spins["top"].value())
        right = float(spins["right"].value())
        bottom = float(spins["bottom"].value())
        spec = pages_edit.text().strip().lower()
        if spec in ("", "todas", "all"):
            pages = list(range(total))
        else:
            pages = self._parse_pages(spec, total)
        if not pages or (left == top == right == bottom == 0):
            self._clear_page_crop(path)
            return
        self._page_crops[path] = {pg: (left, top, right, bottom) for pg in pages}
        self._invalidate_crop_cache(path)
        if self._loaded:
            self.generate(blocking=True)
        self._toasts.success(f"Recorte aplicado a {len(pages)} página(s)")

    def _clear_page_crop(self, path: str) -> None:
        self._page_crops.pop(path, None)
        self._invalidate_crop_cache(path)
        if self._loaded:
            self.generate(blocking=True)

    def _invalidate_crop_cache(self, path: str) -> None:
        self._baked_crops = {k: v for k, v in self._baked_crops.items() if k[0] != path}
        self._crop_cache = {c: o for c, o in self._crop_cache.items() if o != path}

    # ---- recorte de página (bake em PDF recortado de cache) ----
    def _effective_paths(self) -> list:
        """Caminhos a importar: o PDF recortado (cache) quando houver recorte de
        página; senao o original. Mantem self._paths sempre com o ORIGINAL."""
        return [self._effective_path(p) for p in self._paths]

    def _effective_path(self, path: str) -> str:
        crops = self._page_crops.get(path)
        if not crops:
            return path
        sig = tuple(sorted((pg, tuple(v)) for pg, v in crops.items()))
        cached = self._baked_crops.get((path, sig))
        if cached and Path(cached).exists():
            return cached
        # mesmo esquema para PDF e imagem: gera uma versao recortada em cache
        if Path(path).suffix.lower() == ".pdf":
            out = self._bake_cropped_pdf(path, crops, sig)
        else:
            out = self._bake_cropped_image(path, crops, sig)
        if out is None:
            return path
        self._baked_crops[(path, sig)] = out
        self._crop_cache[out] = path
        return out

    def _bake_cropped_pdf(self, path: str, crops: dict, sig) -> str | None:
        """Gera um PDF recortado em cache (corta a mediabox de cada página pelos
        valores em mm). Só PDF; devolve o caminho ou None se falhar."""
        if Path(path).suffix.lower() != ".pdf":
            return None
        try:
            import fitz

            mm2pt = 72.0 / 25.4
            doc = fitz.open(path)
            for pg, (left, top, right, bottom) in crops.items():
                if not (0 <= pg < doc.page_count):
                    continue
                page = doc[pg]
                r = page.rect
                new = fitz.Rect(
                    r.x0 + left * mm2pt, r.y0 + top * mm2pt,
                    r.x1 - right * mm2pt, r.y1 - bottom * mm2pt,
                )
                if new.width > 1 and new.height > 1:
                    page.set_mediabox(new)
            cache = Path(tempfile.gettempdir()) / "printnest_crops"
            cache.mkdir(parents=True, exist_ok=True)
            out = str(cache / f"crop_{abs(hash((path, sig))) & 0xffffffff:08x}.pdf")
            doc.save(out)
            doc.close()
            return out
        except Exception:
            return None

    def _bake_cropped_image(self, path: str, crops: dict, sig) -> str | None:
        """Gera uma IMAGEM recortada em cache (corta as bordas em mm, usando o DPI
        da imagem). Mesmo esquema do PDF; devolve o caminho ou None se falhar."""
        try:
            from PIL import Image

            crop = crops.get(0) or next(iter(crops.values()), None)
            if crop is None:
                return None
            left, top, right, bottom = crop
            img = Image.open(path)
            w, h = img.size
            dpi = img.info.get("dpi", (96.0, 96.0))
            d = float(dpi[0]) if isinstance(dpi, (tuple, list)) else float(dpi)
            if d <= 0:
                d = 96.0
            ppm = d / 25.4  # pixels por mm
            box = (
                max(0, round(left * ppm)), max(0, round(top * ppm)),
                min(w, max(round(left * ppm) + 1, w - round(right * ppm))),
                min(h, max(round(top * ppm) + 1, h - round(bottom * ppm))),
            )
            cropped = img.crop(box)
            cache = Path(tempfile.gettempdir()) / "printnest_crops"
            cache.mkdir(parents=True, exist_ok=True)
            ext = Path(path).suffix.lower() or ".png"
            out = str(cache / f"cropimg_{abs(hash((path, sig))) & 0xffffffff:08x}{ext}")
            cropped.save(out, dpi=(d, d))
            return out
        except Exception:
            return None

    # ---- produção ----
    def _material(self) -> Material:
        return Material(
            name="MVP", width=float(self._width.value()),
            spacing=float(self._spacing.value()),
            spacing_y=float(self._spacing_v.value()),
        )

    def generate(self, *, blocking: bool = False, paths: list | None = None,
                 faca: bool = True) -> None:
        # paths=None -> todos os arquivos da biblioteca; uma lista -> só esses
        # (usado ao arrastar UM arquivo para a área de trabalho vazia).
        # faca=False -> monta a produção SO com a arte (sem faca); a faca e
        # gerada depois ao clicar "Gerar Faca" (arrastar = soltar sem faca).
        target_paths = paths if paths is not None else self._paths
        if not target_paths:
            QMessageBox.warning(self, "PrintNest", "Adicione ao menos um arquivo.")
            return
        self._faca_on = faca
        self._save_settings()
        material = self._material()
        offset = self._effective_offset()
        sheet_height = float(self._height.value())
        box = self._import_box.currentData()
        sensitivity = float(self._auto_sensitivity.value())
        ignore_white = self._auto_ignore_white.isChecked()
        self._fit_next = True  # ajusta o zoom uma vez após gerar
        eff_paths = [self._effective_path(p) for p in target_paths]  # recorte quando houver

        if blocking:
            result = self._pipeline.execute(
                eff_paths, material, offset, sheet_height, box,
                sensitivity=sensitivity, ignore_white=ignore_white,
            )
            unique = sorted(set(result.sources.values()))
            png_map = {key: self._renderer.render_png(key[0], key[1], box=box) for key in unique}
            self._load_production(result, png_map)
            return

        self._set_busy(True)
        self._thread = QThread()
        self._worker = ProductionWorker(
            self._pipeline, self._renderer, eff_paths,
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
        self._act_generate.setEnabled(not busy)
        self._btn_add.setEnabled(not busy)

    def closeEvent(self, event) -> None:
        """Fechar a janela DURANTE uma geracao: espera a thread terminar antes
        de destruir a janela (QA-08). Sem isso o Qt aborta o processo com
        "QThread: Destroyed while thread is still running" — visto como
        "o programa fechou sozinho" na máquina do usuário."""
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(10000)  # geracao normal termina em segundos
        super().closeEvent(event)

    def _set_exports_enabled(self, enabled: bool) -> None:
        for action in getattr(self, "_export_actions", []):
            action.setEnabled(enabled)

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)

    def _on_finished(self, bundle) -> None:
        self._set_busy(False)
        result, png_map = bundle
        self._load_production(result, png_map)

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "PrintNest", f"Falha ao gerar produção:\n{message}")

    def _load_production(self, result: ProductionResult, png_map: dict) -> None:
        self._base_artworks = result.artworks
        self._pdf_contours = {}  # recomputa contornos de PDF na nova produção
        self._vector_contours = {}  # recomputa facas vetoriais (cliente)
        self._sources = result.sources
        self._origins = dict(result.origins) or {
            art_id: src[0] for art_id, src in result.sources.items()
        }
        # recorte: origins volta ao caminho ORIGINAL (quantidade/projeto usam ele);
        # sources/render continuam apontando para o PDF recortado (mostra/exporta cortado)
        if self._crop_cache:
            self._origins = {
                aid: self._crop_cache.get(p, p) for aid, p in self._origins.items()
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
        self._set_exports_enabled(True)
        self._suspend_undo = True  # gerar = recomeco limpo (não vira passo de undo)
        try:
            self._relayout(from_table=True)  # gerar = quantidade da tabela
        finally:
            self._suspend_undo = False
        self._undo.clear()  # zera o histórico ao gerar uma nova produção
        self._update_selection_info()
        self._refresh_library_metadata()
        self._toasts.success("Produção gerada")

    def _relayout(self, *, renest: bool = True, from_table: bool = False) -> None:
        """Recalcula faca + nesting com os parametros atuais (tempo real).

        from_table=True: a quantidade vem da TABELA (gerar / mudar quantidade).
        from_table=False: mantem a contagem atual do arranjo (duplicatas manuais).

        renest=True (padrão): refaz o nesting do zero. Usado por mudancas de
        layout (chapa, espaçamento, quantidade) e ao gerar.
        renest=False: PRESERVA o arranjo manual atual (posições, duplicatas e
        chapas/áreas em branco), só trocando a geometria das artes. Usado por
        mudancas de geometria (giro, sangria, recorte, tamanho, faca): assim
        rotacionar NAO perde as cópias duplicadas nem o que foi organizado.

        NAO zera mais o histórico: o estado anterior e guardado como um passo de
        desfazer. Mudancas seguidas no mesmo parametro se fundem num passo só.
        """
        if not self._loaded or self._suspend_relayout:
            return
        before = None
        if self._result is not None and not self._suspend_undo:
            before = self._state_snapshot()
        self._faca_notice = None  # avisos de detecção (faca do cliente) são refeitos
        material = self._material()
        sheet_height = float(self._height.value())
        quantities = self._quantities()
        # 1. regenera a GEOMETRIA de cada arte base com os parametros atuais
        #    (faca/giro/tamanho, ou só a arte quando a faca esta desligada).
        try:
            by_id = {base.id: self._faca_for(base) for base in self._base_artworks}
        except ValidationError:
            self._alert.show_message(
                AlertLevel.ERROR, "Recorte/recuo grande demais para a peça."
            )
            return
        # 2. define as INSTANCIAS (quantas cópias de cada arte):
        #    - from_table/fresh: contagem da tabela (gerar / mudar quantidade);
        #    - senao: contagem ATUAL do arranjo (mantem duplicatas manuais).
        fresh = self._result is None or not self._piece_items
        if from_table or fresh:
            instances = []
            for base in self._base_artworks:
                qty = quantities.get(self._path_of(base.id), 0)
                fa = by_id.get(base.id)
                if fa is not None and qty > 0:
                    instances.extend([fa] * qty)
        else:
            instances = [
                by_id[it.artwork_id]
                for layout in self._effective_sheets()
                for it in layout.items
                if it.artwork_id in by_id
            ]
        if not instances:
            self._scene.clear()
            self._alert.show_message(
                AlertLevel.WARNING, "Nenhuma peça (verifique as quantidades)."
            )
            self._status_ctl.set_production(0, 0)
            return
        # 3. re-nesta (layout/giro: re-encaixa mantendo a contagem) ou preserva
        #    as posições atuais (ajuste de geometria: sangria/recorte/tamanho).
        if renest or fresh:
            # faca compartilhada precisa das peças alinhadas em grade; senao usa
            # MaxRects (maximo aproveitamento, preenche os vaos).
            uc = self._grid_nesting_uc if self._shared.currentIndex() == 1 else self._nesting_uc
            sheets = uc.execute_sheets(instances, material, sheet_height)
        else:
            sheets = self._preserve_arrangement(by_id, material)
        sheets = self._center_sheets(sheets, material, instances)  # centraliza na página
        self._result = ProductionResult(sheets=sheets, artworks=instances, sources=self._sources)
        self._draw_preview()
        total = sum(s.item_count for s in sheets)
        self._status.setText(f"{len(sheets)} chapa(s) | {total} peça(s)")
        self._update_status_and_alerts(sheets, total, instances, material)
        if before is not None:
            after = (sheets, instances)
            self._undo.push(
                SnapshotCommand(self, before, after, "ajustar", merge_id=RELAYOUT_MERGE_ID)
            )

    def _center_sheets(self, sheets, material, artworks):
        """Centraliza o conteudo de cada chapa na PAGINA: na largura (margens
        iguais) e na altura (dentro do comprimento da chapa). Desloca o bloco
        inteiro por igual, entao o arranjo relativo das peças não muda; o
        comprimento (used_length) da chapa e preservado. Sem efeito se a flag
        estiver desligada."""
        if not self._center_on_sheet:
            return sheets
        by_id = {a.id: a for a in artworks}
        out = []
        for layout in sheets:
            lefts, rights, tops, bottoms = [], [], [], []
            for it in layout.items:
                art = by_id.get(it.artwork_id)
                if art is None:
                    continue
                fp = artwork_footprint(art)
                lefts.append(it.position.x)
                rights.append(it.position.x + (fp.max_x - fp.min_x))
                tops.append(it.position.y)
                bottoms.append(it.position.y + (fp.max_y - fp.min_y))
            if not lefts:
                out.append(layout)
                continue
            content_w = max(rights) - min(lefts)
            content_h = max(bottoms) - min(tops)
            page_h = layout.used_length
            # centraliza; se não couber, encosta no canto (esquerda / topo)
            shift_x = (
                -min(lefts) if content_w >= material.width
                else (material.width - content_w) / 2.0 - min(lefts)
            )
            shift_y = (
                -min(tops) if content_h >= page_h
                else (page_h - content_h) / 2.0 - min(tops)
            )
            if abs(shift_x) < 0.01 and abs(shift_y) < 0.01:
                out.append(layout)
                continue
            items = [
                replace(
                    it,
                    position=Point2D(it.position.x + shift_x, it.position.y + shift_y),
                )
                for it in layout.items
            ]
            out.append(Layout(material, items, layout.used_length))
        return out

    def _preserve_arrangement(self, by_id, material):
        """Mantem o arranjo manual atual (posições, duplicatas e chapas/áreas em
        branco), apenas trocando a geometria das artes (nova faca/giro/tamanho).

        Placements que referenciam uma arte que sumiu (id removido) são
        descartados; o resto (inclusive cópias duplicadas, que compartilham o
        mesmo id) e mantido com a posição e o comprimento usado atuais."""
        sheets = []
        for layout in self._effective_sheets():
            items = [it for it in layout.items if it.artwork_id in by_id]
            sheets.append(Layout(material, items, layout.used_length))
        return sheets

    def _update_status_and_alerts(self, sheets, total, artworks, material) -> None:
        """Atualiza a barra de status e a faixa de avisos a partir da produção."""
        self._status_ctl.set_production(total, len(sheets))
        if sheets:
            pct = max(measurements.sheet_metrics(s, artworks).used_pct for s in sheets)
            self._status_ctl.set_area(pct)
        self._status_ctl.set_mode(self._view_mode.currentText())
        notices = messages.production_notices(
            shared_faca=self._shared.currentIndex() == 1,
            artworks=artworks,
            material=material,
        )
        if notices:
            first = notices[0]
            level = {"warning": AlertLevel.WARNING, "error": AlertLevel.ERROR}.get(
                first.level, AlertLevel.INFO
            )
            if first.code == "shared_faca_image":
                self._alert.show_message(
                    level, first.text, action_text="Trocar",
                    on_action=lambda: self._shared.setCurrentIndex(0),
                )
            else:
                self._alert.show_message(level, first.text)
        elif self._faca_notice is not None:
            level = {"warning": AlertLevel.WARNING, "error": AlertLevel.ERROR}.get(
                self._faca_notice[0], AlertLevel.INFO
            )
            self._alert.show_message(level, self._faca_notice[1])
        else:
            self._alert.clear()
        self._update_property_bar()  # mantem a barra Projeto (peças/chapas) em dia
        self._update_resumo()  # mantem o card "Resumo da produção" sincronizado

    def _refresh_preview(self) -> None:
        if self._result is not None:
            self._draw_preview()

    def _keep(self, item):
        """Mantem referência Python a um item decorativo da cena e o retorna.

        Sem isso, o PySide pode coletar o wrapper de itens criados por
        scene.addRect/addLine/addEllipse (que não tem pai nem referência) e o Qt
        acaba removendo o item orfao em interacoes como o laco de seleção —
        causava a chapa branca/linhas "sumirem" ao clicar no vazio."""
        self._decor_items.append(item)
        return item

    @staticmethod
    def _piece_sel_key(p) -> tuple:
        """Identidade estavel de uma peça (chapa, arte, posição) para reencontrar
        a seleção após um redesenho (desfazer/refazer não perdem a seleção)."""
        x = p.scenePos().x() - p.dx
        y = p.scenePos().y() - p.dy
        return (p.sheet_index, p.artwork_id, round(x, 1), round(y, 1))

    def _draw_preview(self) -> None:
        # guarda a seleção para restaurar após o redesenho (continuar empurrando
        # com as setas, desfazer/refazer sem perder o que estava selecionado).
        selected_keys = {
            self._piece_sel_key(p) for p in self._piece_items if p.isSelected()
        }
        self._piece_items = []
        self._obj_rows = []  # evita referenciar peças deletadas no scene.clear()
        self._guide_preview_item = None  # invalidado pelo scene.clear()
        # itens decorativos (chapa branca, marcas, linhas de corte): precisam de
        # referência Python, senao o PySide os coleta e o Qt remove o item orfao
        # durante o laco de seleção (a chapa "sumia" ao clicar no vazio).
        self._decor_items = []
        self._ghost_items = []  # scene.clear() apaga os fantasmas; zera as refs
        self._resize_handles = []  # idem para as alças de redimensionar
        self._resize_preview = None
        # NAO limpa o histórico aqui: senao excluir/duplicar/desfazer (que
        # redesenham) apagariam o próprio comando. O reset do histórico acontece
        # só quando o arranjo e regenerado (em _relayout).
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
        self._draw_guides()
        if self._fit_next:
            self._fit_view()
            self._fit_next = False
        else:
            self._view.view_changed.emit()  # mantem o zoom; atualiza réguas
        if selected_keys:
            # re-selecionar após o redraw NAO deve trocar de aba (ex.: mexer na
            # densidade/largura na aba Documento não pode jogar para a aba Peça).
            self._keep_tab = True
            try:
                for p in self._piece_items:
                    if self._piece_sel_key(p) in selected_keys:
                        p.setSelected(True)
            finally:
                self._keep_tab = False
        self._refresh_object_list()
        self._update_overlay()

    def _draw_sheets(self, *, draw_art: bool, draw_cut: bool, dy: float, interactive: bool) -> None:
        result = self._result
        by_id = {a.id: a for a in result.artworks}
        # cores do canvas SEMPRE pelos tokens do tema (QA-06: valores hardcoded
        # levemente diferentes dos tokens davam "drift" na área mais critica).
        sheet_brush = QBrush(QColor(theme.SHEET))  # chapa = página branca
        sheet_pen = QPen(QColor(theme.SHEET_BORDER))  # borda suave da chapa (mesa clara)
        sheet_pen.setCosmetic(True)
        material_pen = QPen(QColor(theme.BORDER_STRONG))  # contorno leve das peças vazias
        material_pen.setCosmetic(True)
        faca_pen = QPen(QColor(theme.CUT))
        faca_pen.setCosmetic(True)
        client_pen = QPen(QColor(theme.SUCCESS))  # faca do cliente (vetor) em verde
        client_pen.setCosmetic(True)
        # marcas de registro escuras no preview (a EXPORTACAO segue preto puro,
        # que a leitora optica le melhor — isso aqui e só visualização)
        mark_pen = QPen(QColor(theme.MARK))
        mark_pen.setCosmetic(True)
        mark_brush = QBrush(QColor(theme.MARK))
        empty_color = QColor(theme.EMPTY)
        empty_color.setAlpha(160)
        empty_brush = QBrush(empty_color)

        shared = self._shared.currentIndex() == 1
        reg = self._reg()
        cropped_cache: dict = {}
        # memoizacao por id DENTRO deste redesenho (QA-07): footprint e params
        # eram recalculados para CADA peça (centenas de vezes por operacao com
        # muitas cópias do mesmo arquivo) — por id, calcula uma vez só.
        fp_cache: dict = {}
        params_cache: dict = {}

        def fp_of(art):
            fp = fp_cache.get(art.id)
            if fp is None:
                fp = fp_cache[art.id] = artwork_footprint(art)
            return fp

        def params_of(art_id):
            p = params_cache.get(art_id)
            if p is None:
                p = params_cache[art_id] = self._art_params(art_id)
            return p

        # sombra da chapa SEM QGraphicsDropShadowEffect: o efeito rasteriza a
        # chapa inteira num buffer a cada repaint e TRAVA o zoom de perto.
        # Um retângulo deslocado atras da página da a mesma profundidade de
        # graca (vetor puro, custo constante em qualquer zoom).
        shadow_brush = QBrush(QColor(17, 24, 39, 26))
        for index, layout in enumerate(result.sheets):
            dx = index * (layout.material.width + SHEET_GAP_MM)
            off = max(1.5, layout.material.width * 0.004)  # ~4/1000 da largura
            self._keep(self._scene.addRect(
                dx + off, dy + off, layout.material.width, layout.used_length,
                QPen(Qt.NoPen), shadow_brush,
            ))
            sheet_rect = self._scene.addRect(
                dx, dy, layout.material.width, layout.used_length, sheet_pen, sheet_brush
            )
            self._keep(sheet_rect)
            for item in layout.items:
                art = by_id.get(item.artwork_id)
                if art is None:
                    continue
                fp = fp_of(art)
                piece = PieceItem(
                    fp.max_x - fp.min_x, fp.max_y - fp.min_y,
                    artwork_id=item.artwork_id, name=art.name, art_size=art.size,
                    sheet_index=index, dx=dx, dy=dy,
                )
                piece.setPos(dx + item.position.x, dy + item.position.y)
                # selecionavel em QUALQUER modo (inclusive tela dividida/só-corte):
                # da pra selecionar a peça/faca e exportar só ela com Ctrl+E.
                piece.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                if interactive:
                    piece.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                    piece.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
                    piece.snap = self._snap
                    piece.sheet_rect = (dx, dy, layout.material.width, layout.used_length)
                    self._piece_items.append(piece)
                else:
                    # não-interativas (split/corte): só selecionaveis. Precisam de
                    # referência Python, senao o PySide as coleta (sumiam ao clicar).
                    self._decor_items.append(piece)

                ax, ay = -fp.min_x, -fp.min_y  # origem da arte relativa a celula
                if draw_art:
                    p = params_of(item.artwork_id)
                    key = self._sources.get(item.artwork_id)
                    pixmap = self._pixmaps.get(key)
                    if pixmap is not None and not pixmap.isNull() and pixmap.width() > 0:
                        display = self._display_pixmap(
                            pixmap, p["crop"], p["rotation"], art.size, cropped_cache, key
                        )
                        child = QGraphicsPixmapItem(display, piece)
                        child.setScale(art.size.width / display.width())
                        child.setPos(ax, ay)
                    else:
                        rect = QGraphicsRectItem(ax, ay, art.size.width, art.size.height, piece)
                        rect.setBrush(empty_brush)
                        rect.setPen(material_pen)
                if draw_cut and art.has_cut and not shared:
                    is_client = (
                        self._params_for(self._path_of(item.artwork_id)).get("mode")
                        == "vector"
                    )
                    faca = art.cut_contour
                    poly = QPolygonF([QPointF(ax + p.x, ay + p.y) for p in faca.points])
                    poly_item = QGraphicsPolygonItem(poly, piece)
                    poly_item.setPen(client_pen if is_client else faca_pen)
                    poly_item.setBrush(Qt.NoBrush)
                self._scene.addItem(piece)

            if draw_cut and shared:
                for seg in shared_cut_segments(layout, result.artworks):
                    self._keep(self._scene.addLine(
                        dx + seg.start.x, dy + seg.start.y,
                        dx + seg.end.x, dy + seg.end.y, faca_pen,
                    ))
            # marcas de registro aparecem dos DOIS lados (impressao E corte): na
            # tela dividida elas saem tanto na metade de impressao quanto na de
            # corte, espelhando o que vai pra exportação.
            if draw_art or draw_cut:
                self._draw_marks(
                    layout, result.artworks, dx, dy, reg, mark_pen, mark_brush, faca_pen
                )

    def _fit_view(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if not rect.isEmpty():
            self._view.fitInView(rect, Qt.KeepAspectRatio)
            self._view.view_changed.emit()

    # ---- zoom e navegacao (atalhos padrão CorelDRAW) ----
    def _zoom_step(self, factor: float) -> None:
        """Zoom + / − centrado na visualização (F2 / F3)."""
        self._view.scale(factor, factor)
        self._view.view_changed.emit()

    def _zoom_page(self) -> None:
        """Enquadra a primeira chapa (Shift+F4). Sem produção, ajusta tudo."""
        r = self._result
        if r is not None and r.sheets:
            s = r.sheets[0]
            m = max(10.0, s.material.width * 0.03)
            rect = QRectF(-m, -m, s.material.width + 2 * m, s.used_length + 2 * m)
            self._view.fitInView(rect, Qt.KeepAspectRatio)
            self._view.view_changed.emit()
        else:
            self._fit_view()

    def _zoom_selection(self) -> None:
        """Enquadra as peças selecionadas (Shift+F2). Sem seleção, não faz nada."""
        try:
            items = self._scene.selectedItems()
        except RuntimeError:
            return
        if not items:
            return
        rect = items[0].sceneBoundingRect()
        for it in items[1:]:
            rect = rect.united(it.sceneBoundingRect())
        m = max(rect.width(), rect.height()) * 0.15 + 5.0
        self._view.fitInView(rect.adjusted(-m, -m, m, m), Qt.KeepAspectRatio)
        self._view.view_changed.emit()

    def _set_hand_tool(self, on: bool) -> None:
        """Ferramenta mao (H): botão esquerdo passa a arrastar a tela."""
        self._view.setDragMode(
            QGraphicsView.ScrollHandDrag if on else QGraphicsView.NoDrag
        )

    def _pan_view(self, dx: int, dy: int) -> None:
        """Desloca a visualização (Alt+setas)."""
        h = self._view.horizontalScrollBar()
        v = self._view.verticalScrollBar()
        h.setValue(h.value() + dx)
        v.setValue(v.value() + dy)

    def _show_object_props(self) -> None:
        """Alt+Enter: abre a aba Objeto do painel de propriedades."""
        for i in range(self._props_tabs.count()):
            if self._props_tabs.tabText(i) == "Objeto":
                self._props_tabs.setCurrentIndex(i)
                return

    # ---- edicao na área de trabalho (mover / agrupar / desfazer) ----
    def _begin_move(self) -> None:
        self._snap.dragging = True  # ativa o encaixe só durante o arraste
        # snapshot do arranjo ANTES do arraste (dados, não referencias de itens)
        self._move_before = self._snapshot_sheets() if self._result is not None else None

    def _end_move(self) -> None:
        self._snap.dragging = False
        before = self._move_before
        self._move_before = None
        if before is None:
            return
        after = self._effective_sheets()
        if self._arr_key(before) != self._arr_key(after):  # só registra se mudou
            self._commit_move(before, after, "mover")

    @staticmethod
    def _arr_key(sheets) -> list:
        """Chave comparavel do arranjo (posições das peças), para detectar mudanca."""
        return [
            (i, it.artwork_id, round(it.position.x, 3), round(it.position.y, 3))
            for i, layout in enumerate(sheets)
            for it in layout.items
        ]

    def _commit_move(self, before, after, text: str) -> None:
        """Registra um movimento no histórico SEM redesenhar (as peças já estao na
        posição final, movidas ao vivo): mantem a fluidez e a seleção. O redesenho
        só acontece ao desfazer/refazer."""
        arts = list(self._result.artworks)
        before_state, after_state = (before, arts), (after, arts)
        self._result = ProductionResult(sheets=after, artworks=arts, sources=self._sources)
        self._undo.push(SnapshotCommand(self, before_state, after_state, text))

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

    def _set_center_on_sheet(self, enabled) -> None:
        """Liga/desliga a centralizacao na chapa e re-encaixa para o efeito
        aparecer na hora (centraliza ao ligar, encosta no canto ao desligar).
        Desligado, da para arrastar/posicionar as peças livremente na página."""
        enabled = bool(enabled)
        self._center_on_sheet = enabled
        # mantem o menu (Organizar) e o checkbox (Produção) em sincronia
        if hasattr(self, "_center_action") and self._center_action.isChecked() != enabled:
            self._center_action.setChecked(enabled)
        if hasattr(self, "_center_check") and self._center_check.isChecked() != enabled:
            self._center_check.setChecked(enabled)
        if self._result is not None and self._loaded:
            self._relayout(renest=True)

    def _selected_movable(self) -> list:
        return [
            it for it in self._scene.selectedItems()
            if it.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        ]

    def _selected_pieces(self) -> list:
        """Peças selecionadas, abrindo grupos selecionados."""
        out: list = []
        for it in self._scene.selectedItems():
            if isinstance(it, QGraphicsItemGroup):
                out.extend(c for c in it.childItems() if isinstance(c, PieceItem))
            elif isinstance(it, PieceItem):
                out.append(it)
        return out

    def _nudge(self, dx: float, dy: float) -> None:
        """Empurra as peças selecionadas com as setas (mm), com desfazer."""
        items = self._selected_movable()
        if not items:
            return
        before = self._snapshot_sheets()
        for it in items:
            old = it.pos()
            it.setPos(old.x() + dx, old.y() + dy)
        after = self._effective_sheets()
        if self._arr_key(before) != self._arr_key(after):
            self._commit_move(before, after, "mover")

    def _align(self, mode: str) -> None:
        items = self._selected_movable()
        if len(items) < 2:
            return
        before = self._snapshot_sheets()
        rects = {it: it.sceneBoundingRect() for it in items}
        left = min(r.left() for r in rects.values())
        right = max(r.right() for r in rects.values())
        top = min(r.top() for r in rects.values())
        bottom = max(r.bottom() for r in rects.values())
        cx, cy = (left + right) / 2.0, (top + bottom) / 2.0
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
                it.setPos(old.x() + dx, old.y() + dy)
        after = self._effective_sheets()
        if self._arr_key(before) != self._arr_key(after):
            self._commit_move(before, after, "alinhar")

    def _distribute(self, axis: str) -> None:
        items = self._selected_movable()
        if len(items) < 3:
            return
        before = self._snapshot_sheets()
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
                it.setPos(old.x() + dx, old.y() + dy)
        after = self._effective_sheets()
        if self._arr_key(before) != self._arr_key(after):
            self._commit_move(before, after, "distribuir")

    def _add_placed(self, add_by_sheet: dict, *, text: str = "duplicar") -> None:
        """Acrescenta PlacedItems por chapa e redesenha (estende o comprimento usado).
        As peças novas viram a seleção (Ctrl+D/Ctrl+V em cadeia, como no Corel)."""
        if not add_by_sheet:
            return
        before = self._snapshot_sheets()
        by_id = {a.id: a for a in self._result.artworks}
        fp_cache: dict = {}  # footprint por id (QA-07: não recalcular por peça)
        sheets = []
        for index, layout in enumerate(self._effective_sheets()):
            items = list(layout.items) + add_by_sheet.get(index, [])
            used = layout.used_length
            for placed in items:
                art = by_id.get(placed.artwork_id)
                if art is None:
                    continue
                fp = fp_cache.get(art.id)
                if fp is None:
                    fp = fp_cache[art.id] = artwork_footprint(art)
                used = max(used, placed.position.y + (fp.max_y - fp.min_y))
            sheets.append(Layout(layout.material, items, used))
        self._commit_arrangement(before, sheets, text)
        self._select_pieces_at(add_by_sheet)

    def _select_pieces_at(self, add_by_sheet: dict) -> None:
        """Seleciona as peças recem-adicionadas (a cópia vira a nova seleção)."""
        targets = {
            (idx, p.artwork_id, round(p.position.x, 2), round(p.position.y, 2))
            for idx, placed in add_by_sheet.items()
            for p in placed
        }
        try:
            self._scene.clearSelection()
        except RuntimeError:
            return
        for piece in self._piece_items:
            key = (piece.sheet_index, piece.artwork_id,
                   round(piece.scenePos().x() - piece.dx, 2),
                   round(piece.scenePos().y() - piece.dy, 2))
            if key in targets:
                piece.setSelected(True)

    # ---- adicionar arquivo da biblioteca a produção já gerada (arrastar) ----
    def _on_library_drop(self, scene_pos) -> None:
        row = self._table.currentRow()
        if 0 <= row < len(self._paths):
            self._add_file_to_production(self._paths[row], scene_pos)

    def _add_file_to_production(self, path: str, scene_pos) -> None:
        """Adiciona um arquivo da biblioteca a produção na posição do drop, sem
        refazer o nesting das peças que já estao na chapa."""
        if self._result is None or not self._loaded:
            # ainda não gerou: o drop monta a produção com SOMENTE o arquivo
            # arrastado (não todos), e SEM faca (soltar sem faca). A faca surge
            # depois ao clicar "Gerar Faca". O usuário organiza dali.
            self.generate(blocking=True, paths=[path], faca=False)
            return
        bases = [b for b in self._base_artworks if self._path_of(b.id) == path]
        if not bases:  # arquivo ainda não importado -> importa agora
            bases = self._import_file_bases(path)
            if not bases:
                return
            self._base_artworks.extend(bases)
        faca_arts = [self._faca_for(b) for b in bases]
        current = list(self._result.artworks)
        have = {a.id for a in current}
        current.extend(fa for fa in faca_arts if fa.id not in have)
        self._result = ProductionResult(
            sheets=self._result.sheets, artworks=current,
            sources=self._sources, origins=self._origins,
        )
        index, base_pos = self._sheet_pos_at(scene_pos)
        qty = self._quantities().get(path, 1) or 1
        step = NUDGE_SUPER_MM
        placed, n = [], 0
        for fa in faca_arts:
            for _ in range(qty):
                placed.append(
                    PlacedItem(fa.id, Point2D(base_pos.x + n * step, base_pos.y + n * step))
                )
                n += 1
        self._add_placed({index: placed}, text="adicionar arquivo")
        self._relayout(renest=True)  # organiza (nesting) automaticamente, com ou sem faca
        self._toasts.success(f"{Path(path).name} adicionado a produção")

    def _import_file_bases(self, path: str) -> list:
        """Importa um único arquivo (sem refazer tudo) e registra fontes/pixmaps."""
        box = self._import_box.currentData()
        eff = self._effective_path(path)  # PDF recortado quando houver recorte
        try:
            result1 = self._pipeline.execute(
                [eff], self._material(), self._effective_offset(), 0.0, box,
                sensitivity=float(self._auto_sensitivity.value()),
                ignore_white=self._auto_ignore_white.isChecked(),
            )
        except Exception:  # arquivo inválido/ausente: não quebra a produção atual
            self._toasts.error(f"Falha ao importar {Path(path).name}")
            return []
        for art in result1.artworks:
            self._sources[art.id] = result1.sources[art.id]
            self._origins[art.id] = path  # mantem o caminho ORIGINAL (quantidade/projeto)
        for key in set(result1.sources.values()):
            if key not in self._pixmaps:
                try:
                    data = self._renderer.render_png(key[0], key[1], box=box)
                    pixmap = QPixmap()
                    pixmap.loadFromData(data, "PNG")
                    self._pixmaps[key] = pixmap
                except Exception:  # miniatura/render opcional; segue sem pixmap
                    pass
        return list(result1.artworks)

    def _sheet_pos_at(self, scene_pos):
        """Chapa e posição local (mm) sob o ponto da cena onde o arquivo foi solto."""
        x, y = scene_pos.x(), scene_pos.y()
        for index, layout in enumerate(self._result.sheets):
            dx = index * (layout.material.width + SHEET_GAP_MM)
            if dx <= x <= dx + layout.material.width:
                return index, Point2D(max(0.0, x - dx), max(0.0, y))
        return 0, Point2D(max(0.0, x), max(0.0, y))

    def _duplicate_selected(self) -> None:
        """Duplica as peças selecionadas com deslocamento diagonal (Corel: Ctrl+D).
        A cópia vira a nova seleção: segurar Ctrl+D duplica em cadeia."""
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

    # ---- copiar / colar peças (Corel: Ctrl+C, Ctrl+V, e Ctrl+D em cadeia) ----
    def _copy_selected(self) -> None:
        """Ctrl+C: guarda as peças selecionadas na 'área de transferencia'
        interna (chapa + posição). Não mexe no arranjo."""
        sel = self._selected_pieces()
        if not sel:
            return
        self._piece_clipboard = [
            (p.sheet_index, p.artwork_id,
             p.scenePos().x() - p.dx, p.scenePos().y() - p.dy)
            for p in sel
        ]
        self._paste_count = 0
        self._toasts.info(f"{len(sel)} peça(s) copiada(s) — Ctrl+V para colar")

    def _paste_clipboard(self) -> None:
        """Ctrl+V: cola as peças copiadas, deslocadas em diagonal. Colagens
        seguidas cascateiam; a cópia vira a seleção (Ctrl+D continua a serie)."""
        if self._result is None or not getattr(self, "_piece_clipboard", None):
            return
        self._paste_count = getattr(self, "_paste_count", 0) + 1
        off = NUDGE_SUPER_MM * self._paste_count
        valid_ids = {a.id for a in self._result.artworks}
        add: dict[int, list] = {}
        for sheet_index, art_id, x, y in self._piece_clipboard:
            if art_id not in valid_ids:
                continue  # a peça copiada já saiu desta produção
            add.setdefault(sheet_index, []).append(
                PlacedItem(art_id, Point2D(x + off, y + off))
            )
        if add:
            self._add_placed(add, text="colar")

    def _duplicate_selected_qty(self) -> None:
        """Duplica SO a(s) página(s)/peça(s) selecionada(s) numa quantidade
        escolhida e re-encaixa, sem mexer na quantidade das outras páginas.

        Resolve o caso do PDF com várias páginas: selecionar uma página e pedir
        N cópias dela, sem duplicar o documento inteiro (a quantidade da tabela
        e por arquivo e duplicaria todas as páginas)."""
        if self._result is None:
            return
        sel = self._selected_pieces()
        if not sel:
            QMessageBox.information(
                self, "PrintNest", "Selecione a(s) página(s) que quer duplicar."
            )
            return
        n, ok = QInputDialog.getInt(
            self, "Duplicar página",
            f"Quantas cópias a mais de cada peça selecionada ({len(sel)})?",
            1, 1, 500,
        )
        if not ok or n < 1:
            return
        before = self._state_snapshot()
        by_id = {a.id: a for a in self._result.artworks}
        # contagem ATUAL do arranjo (mantem o que já esta na chapa) + as cópias
        instances = [
            by_id[it.artwork_id]
            for layout in self._effective_sheets()
            for it in layout.items
            if it.artwork_id in by_id
        ]
        for piece in sel:
            art = by_id.get(piece.artwork_id)
            if art is not None:
                instances.extend([art] * n)
        material = self._material()
        uc = self._grid_nesting_uc if self._shared.currentIndex() == 1 else self._nesting_uc
        sheets = uc.execute_sheets(instances, material, float(self._height.value()))
        after = (sheets, instances)
        self._apply_state(after)
        self._undo.push(SnapshotCommand(self, before, after, "duplicar página"))
        self._update_status_and_alerts(
            sheets, sum(s.item_count for s in sheets), instances, material
        )
        self._toasts.success(f"{len(sel)} página(s) duplicada(s) (+{n} cada)")

    def _step_repeat(self, cols: int, rows: int, gap: float) -> None:
        """Cria cópias em grade das peças selecionadas (step and repeat)."""
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
        self._add_placed(add, text="repetir em grade")

    def _step_repeat_dialog(self) -> None:
        if self._result is None or not self._selected_pieces():
            QMessageBox.information(self, "PrintNest", "Selecione ao menos uma peça.")
            return
        cols, ok = QInputDialog.getInt(self, "Repetir em grade", "Colunas:", 2, 1, 200)
        if not ok:
            return
        rows, ok = QInputDialog.getInt(self, "Repetir em grade", "Linhas:", 1, 1, 200)
        if not ok:
            return
        gap, ok = QInputDialog.getDouble(
            self, "Repetir em grade", "Espaçamento entre cópias (mm):", 5.0, 0.0, 1000.0, 1
        )
        if not ok:
            return
        self._step_repeat(cols, rows, gap)

    def _effective_sheets(self) -> list:
        """Sheets refletindo movimentos manuais das peças (ou o nesting original)."""
        if not self._piece_items:
            return self._result.sheets
        moved: dict[int, list] = {}
        for piece in self._piece_items:
            # scenePos funciona mesmo se a peça estiver dentro de um grupo
            pos = Point2D(piece.scenePos().x() - piece.dx, piece.scenePos().y() - piece.dy)
            moved.setdefault(piece.sheet_index, []).append(PlacedItem(piece.artwork_id, pos))
        sheets = []
        for index, layout in enumerate(self._result.sheets):
            items = moved.get(index, [])  # vazio = todas as peças excluidas
            sheets.append(Layout(layout.material, items, layout.used_length))
        return sheets

    def _select_all(self) -> None:
        for piece in self._piece_items:
            piece.setSelected(True)

    # ---- histórico de arranjo (excluir/duplicar/repetir com Ctrl+Z) ----
    def _snapshot_sheets(self) -> list:
        """Copia o arranjo atual (chapas + PlacedItems) para o histórico."""
        return [
            Layout(layout.material, list(layout.items), layout.used_length)
            for layout in self._effective_sheets()
        ]

    def _state_snapshot(self):
        """Estado completo atual (chapas + artes + giros por peça) para o
        histórico de desfazer. Os giros por peça (_piece_rotations) PRECISAM
        estar no snapshot: sem isso, desfazer um giro deixava o dict "sujo" e
        o giro desfeito voltava sozinho no proximo recalculo (bug QA-01)."""
        return (
            self._snapshot_sheets(),
            list(self._result.artworks),
            dict(self._piece_rotations),
        )

    def _apply_state(self, state) -> None:
        """Reaplica um estado (chapas + artes + giros) e redesenha. Base de
        desfazer/refazer. Aceita estados antigos de 2 itens (sem giros)."""
        if self._result is None:
            return
        sheets, artworks, *rest = state
        if rest:
            self._piece_rotations = dict(rest[0])
        self._result = ProductionResult(
            sheets=sheets, artworks=artworks, sources=self._sources
        )
        self._draw_preview()
        total = sum(s.item_count for s in sheets)
        self._status.setText(f"{len(sheets)} chapa(s) | {total} peça(s)")
        self._status_ctl.set_production(total, len(sheets))

    def _commit_arrangement(self, before, after, text: str) -> None:
        """Aplica 'after' e registra o passo no histórico (Ctrl+Z desfaz).

        'before'/'after' são listas de Layout. As artes não mudam numa operacao
        de arranjo (mover/excluir/duplicar), entao o estado usa as artes atuais.
        """
        arts = list(self._result.artworks)
        rot = dict(self._piece_rotations)  # arranjo não muda giros: mesmo dict
        before_state, after_state = (before, arts, rot), (after, arts, rot)
        self._apply_state(after_state)
        self._undo.push(SnapshotCommand(self, before_state, after_state, text))

    def _delete_selected(self) -> None:
        # guias selecionadas saem na hora (sem mexer no arranjo das peças)
        guides = [it for it in self._scene.selectedItems() if isinstance(it, GuideItem)]
        for g in guides:
            if g.record in self._guides:
                self._guides.remove(g.record)
            self._scene.removeItem(g)
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
        before = self._snapshot_sheets()
        self._piece_items = [p for p in self._piece_items if p not in to_remove]
        # reconstroi as chapas a partir das peças RESTANTES. NAO usar
        # _effective_sheets() aqui: com a lista vazia (excluir a ULTIMA peça) ele
        # devolveria as chapas originais e a peça reaparecia.
        moved: dict[int, list] = {}
        for piece in self._piece_items:
            pos = Point2D(piece.scenePos().x() - piece.dx, piece.scenePos().y() - piece.dy)
            moved.setdefault(piece.sheet_index, []).append(
                PlacedItem(piece.artwork_id, pos)
            )
        after = [
            Layout(layout.material, moved.get(i, []), layout.used_length)
            for i, layout in enumerate(self._result.sheets)
        ]
        after = self._center_sheets(after, self._material(), self._result.artworks)
        self._commit_arrangement(before, after, "excluir")

    def _rotate_selected(self, delta: int) -> None:
        """Gira em +-90 graus SO a(s) peça(s) selecionada(s) e re-encaixa o
        nesting (mantendo a contagem) para a peça girada aproveitar o vão.

        Cada peça gira sozinha (por artwork_id): selecionar a sobra solta e
        girar não mexe nas outras páginas/cópias. Sem seleção, gira TODOS
        (rotação global do documento)."""
        if not self._loaded:
            self._toasts.info("Gere a produção primeiro (Gerar Produção).")
            return
        ids = {p.artwork_id for p in self._selected_pieces()}
        if ids:
            # snapshot ANTES de mutar os giros: o desfazer precisa restaurar o
            # dict antigo (bug QA-01: o snapshot dentro do _relayout já pegava
            # o giro novo e o Ctrl+Z não revertia _piece_rotations).
            before = self._state_snapshot() if self._result is not None else None
            for art_id in ids:
                atual = self._piece_rotations.get(art_id, 0)
                self._piece_rotations[art_id] = (atual + delta) % 360
            self._suspend_undo = True
            try:
                self._relayout(renest=True)  # re-encaixa girado, mantendo a contagem
            finally:
                self._suspend_undo = False
            if before is not None and self._result is not None:
                after = self._state_snapshot()
                self._undo.push(SnapshotCommand(self, before, after, "girar peça"))
            # o re-encaixe recria as peças noutra posição e a seleção (por posição)
            # se perdia -> re-seleciona pelo id para continuar girando/editando.
            self._reselect_by_artwork(ids)
            self._toasts.success(
                f"Girou {len(ids)} peça(s) {abs(delta)}°" if len(ids) > 1
                else f"Peça girada {abs(delta)}°"
            )
        else:
            # nada selecionado: gira todos (rotação global do documento)
            novo = (self._rotation_value() + delta) % 360
            self._rotation.setCurrentText(str(novo))  # dispara o relayout

    def _reselect_by_artwork(self, ids) -> None:
        """Re-seleciona as peças cujo artwork_id esta em `ids`. Usado após um
        re-encaixe (que recria as peças noutra posição) para manter o objeto
        selecionado — assim da para clicar de novo e continuar girando."""
        if not ids:
            return
        self._scene.clearSelection()
        for p in self._piece_items:
            if p.artwork_id in ids:
                p.setSelected(True)

    def _organize(self) -> None:
        """Reorganiza (nesting) mantendo a contagem atual do arranjo (inclui
        duplicatas). Botão 'Organizar' para o cliente reorganizar quando quiser."""
        if not self._loaded:
            self._toasts.info("Solte ou gere os arquivos primeiro.")
            return
        self._fit_next = True
        self._relayout(renest=True)
        self._toasts.success("Organizado")

    def _reset_arrangement(self) -> None:
        """Refaz o nesting do zero (descarta movimentos/exclusoes/duplicatas)."""
        self._fit_next = True
        self._relayout(from_table=True)

    def _draw_marks(self, layout, artworks, dx, dy, reg, mark_pen, mark_brush, faca_pen) -> None:
        if reg in ("circles", "both"):
            for mark in registration_marks(
                layout, artworks,
                margin_mm=float(self._reg_margin.value()),
                diameter_mm=float(self._reg_diameter.value()),
            ):
                self._keep(self._scene.addEllipse(
                    dx + mark.center.x - mark.radius, dy + mark.center.y - mark.radius,
                    mark.diameter, mark.diameter, mark_pen, mark_brush,
                ))
        if reg in ("mimaki", "both"):
            marks = mimaki_marks(
                layout, artworks,
                distance_mm=float(self._mk_distance.value()),
                mark_size_mm=float(self._mk_size.value()),
            )
            if marks is None:
                return
            f = marks.frame
            self._keep(self._scene.addRect(
                dx + f.min_x, dy + f.min_y, f.max_x - f.min_x, f.max_y - f.min_y, faca_pen
            ))
            for seg in marks.segments:
                self._keep(self._scene.addLine(
                    dx + seg.start.x, dy + seg.start.y,
                    dx + seg.end.x, dy + seg.end.y, mark_pen,
                ))

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
            # antes da rotação art_size pode estar trocado; reconstroi original
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

    # ---- exportação ----
    def _print_kwargs(self) -> dict:
        """Parametros de marca/recorte/rotação/caixa comuns ao PDF e a imagem."""
        return {
            "reg_type": self._reg(),
            "reg_margin_mm": float(self._reg_margin.value()),
            "reg_diameter_mm": float(self._reg_diameter.value()),
            "mimaki_distance_mm": float(self._mk_distance.value()),
            "mimaki_size_mm": float(self._mk_size.value()),
            "mimaki_thickness_mm": float(self._mk_thickness.value()),
            "crop_mm": float(self._crop.value()),
            "rotate": self._rotation_value(),
            # giro por peça: sobrepoe o giro padrão para peças giradas sozinhas
            "rotations": {
                a.id: self._rotation_of(a.id) for a in self._result.artworks
            } if self._result is not None else None,
            "box": self._import_box.currentData(),
        }

    # ---- Centro de Exportação (Ctrl+E) ----
    def _sheet_thumbnail(self, index: int, max_px: int = 150) -> QPixmap:
        """Renderiza uma miniatura da chapa (a partir da cena atual)."""
        sheets = self._effective_sheets()
        if not (0 <= index < len(sheets)):
            return QPixmap()
        layout = sheets[index]
        w = max(layout.material.width, 1.0)
        h = max(layout.used_length, 1.0)
        dx = index * (layout.material.width + SHEET_GAP_MM)
        scale = max_px / max(w, h)
        pm = QPixmap(max(1, int(w * scale)), max(1, int(h * scale)))
        pm.fill(Qt.white)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        try:
            self._scene.render(painter, QRectF(pm.rect()), QRectF(dx, 0.0, w, h))
        finally:
            painter.end()
        return pm

    def _selected_sheet_indices(self) -> list[int]:
        """Indices das chapas que tem alguma peça selecionada no canvas."""
        try:
            sel = self._scene.selectedItems()
        except RuntimeError:
            return []
        return sorted({it.sheet_index for it in sel if isinstance(it, PieceItem)})

    def _selection_bbox_scene(self):
        """Retângulo (cena) que envolve as peças selecionadas, ou None."""
        pieces = self._selected_pieces()
        if not pieces:
            return None
        xs0 = [p.scenePos().x() for p in pieces]
        ys0 = [p.scenePos().y() for p in pieces]
        xs1 = [p.scenePos().x() + p.rect().width() for p in pieces]
        ys1 = [p.scenePos().y() + p.rect().height() for p in pieces]
        return QRectF(min(xs0), min(ys0), max(xs1) - min(xs0), max(ys1) - min(ys0))

    def _selection_export_sheets(self):
        """Monta UMA chapa sintetica só com as peças selecionadas, recortada ao
        retângulo delas (sem espaco em branco). Retorna (sheets, (largura, altura))
        em mm, ou None se não houver seleção."""
        pieces = self._selected_pieces()
        if not pieces:
            return None
        box = self._selection_bbox_scene()
        w = max(box.width(), 1.0)
        h = max(box.height(), 1.0)
        placed = [
            PlacedItem(
                p.artwork_id,
                Point2D(p.scenePos().x() - box.x(), p.scenePos().y() - box.y()),
            )
            for p in pieces
        ]
        mat = Material(name="seleção", width=w)
        return [Layout(mat, placed, h)], (w, h)

    def _selection_thumbnail(self, max_px: int = 360) -> QPixmap:
        """Miniatura SO da regiao selecionada (mostra exatamente o que será
        exportado, no modo de visualização atual)."""
        box = self._selection_bbox_scene()
        if box is None or box.width() <= 0 or box.height() <= 0:
            return QPixmap()
        scale = max_px / max(box.width(), box.height())
        pm = QPixmap(max(1, int(box.width() * scale)), max(1, int(box.height() * scale)))
        pm.fill(Qt.white)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        try:
            self._scene.render(painter, QRectF(pm.rect()), box)
        finally:
            painter.end()
        return pm

    def _open_export_center(self) -> None:
        """Centro de Exportação: escolhe chapas (com previa) e formato (Ctrl+E)."""
        if self._result is None or not self._result.sheets:
            self._toasts.info("Gere a produção primeiro (Gerar Produção).")
            return
        ExportCenterDialog(self).exec()

    # ---- integracao externa (CorelDRAW / linha de comando) ----
    def _raise_to_front(self) -> None:
        """Restaura e traz a janela para a frente (ao receber arquivo externo)."""
        self.setWindowState(
            (self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive
        )
        self.show()
        self.raise_()
        self.activateWindow()

    def open_external_files(self, paths: list[str]) -> None:
        """Recebe arquivos de fora (macro do CorelDRAW ou linha de comando):
        adiciona a biblioteca, joga na produção (organizando) e traz a janela
        para a frente. Lista vazia apenas traz a janela para a frente."""
        valid = [str(Path(p)) for p in (paths or []) if Path(p).exists()]
        self._raise_to_front()
        if not valid:
            return
        novos = [p for p in valid if p not in self._paths]
        if novos:
            self.add_paths(novos)
        for p in valid:
            self._add_file_to_production(p, QPointF(20.0, 20.0))
        self._fit_view()  # enquadra para o arquivo recebido aparecer na tela
        self._toasts.success(f"{len(valid)} arquivo(s) recebido(s) do CorelDRAW")

    @_guard_export
    def export_pdf(self, path: str | None = None, pages=None, sheets_override=None) -> None:
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        sheets = sheets_override if sheets_override is not None else self._select_export_sheets(
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
            self._toasts.success("PDF de impressao exportado")

    @_guard_export
    def export_image(
        self, path: str | None = None, pages=None, dpi=None, image_format=None,
        sheets_override=None,
    ) -> None:
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        sheets = sheets_override if sheets_override is not None else self._select_export_sheets(
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
            self._toasts.success(f"{len(gerados)} imagem(ns) exportada(s) a {int(dpi)} DPI")

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
        """Escolhe quais chapas exportar. Retorna None se o usuário cancelar."""
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
        if reg in ("circles", "both"):
            # bolinhas continuam no corte (comportamento já validado)
            marks = registration_marks_sheets(
                sheets, artworks, sheet_width,
                margin_mm=float(self._reg_margin.value()),
                diameter_mm=float(self._reg_diameter.value()),
            )
        if reg in ("mimaki", "both"):
            # mantem o QUADRADO (frame) que posiciona as marcas em L, junto com a
            # faca; mas NAO leva as marcas de registro em L (mark_segments fica
            # vazio). As marcas em L seguem apenas no PDF de impressao.
            mk_list = mimaki_marks_sheets(
                sheets, artworks, sheet_width,
                distance_mm=float(self._mk_distance.value()),
                mark_size_mm=float(self._mk_size.value()),
            )
            contours = list(contours) + mimaki_frame_contours(mk_list)
        return contours, segments, marks, mark_segments

    @_guard_export
    def export_dxf(self, path: str | None = None, pages=None, sheets_override=None) -> None:
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        sheets = sheets_override if sheets_override is not None else self._select_export_sheets(
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
            self._toasts.success("DXF de corte exportado")

    @_guard_export
    def export_dxf_per_sheet(self, base_path: str | None = None, pages=None) -> None:
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
        sheets = self._select_export_sheets(self._effective_sheets(), pages, False, "DXF")
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
            self._toasts.success(f"{len(gerados)} DXF de corte exportado(s)")

    def _faca_pad(self) -> float:
        """Folga (mm) ao redor da faca para as marcas de registro caberem na
        página (mesma conta do PDF de impressao)."""
        reg = self._reg()
        pad = 0.0
        if reg in ("circles", "both"):
            pad = max(pad, float(self._reg_margin.value()) + float(self._reg_diameter.value()))
        if reg in ("mimaki", "both"):
            pad = max(pad, float(self._mk_distance.value()) + float(self._mk_thickness.value()))
        return pad

    @_guard_export
    def export_faca_pdf(self, path: str | None = None, pages=None, sheets_override=None) -> None:
        """Exporta a faca (linhas de corte) em PDF vetorial, uma página por chapa.
        Inclui as marcas de registro (bolinhas), igual ao DXF e a impressao."""
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        sheets = sheets_override if sheets_override is not None else self._select_export_sheets(
            self._effective_sheets(), pages, interactive, "Exportar Faca (PDF)"
        )
        if sheets is None:
            return
        if not sheets:
            if interactive:
                QMessageBox.warning(self, "PrintNest", "Nenhuma chapa selecionada.")
            return
        # faca vazia = PDF em branco indo para a máquina de corte (bug QA-03):
        # valida ANTES de pedir o nome do arquivo e NUNCA grava sem linhas.
        contours_all, segments_all, _mk, _ln = self._dxf_payload(sheets)
        if not contours_all and not segments_all:
            if interactive:
                QMessageBox.warning(
                    self, "PrintNest",
                    "Nenhuma faca para exportar.\n"
                    'Clique em "Gerar Faca" antes de exportar o corte.',
                )
            return
        if interactive:
            path, _ = QFileDialog.getSaveFileName(
                self, "Exportar Faca (PDF)",
                str(Path(self._settings.last_dir) / "FACA.pdf"), "PDF (*.pdf)",
            )
            if not path:
                return
        import fitz

        mm2pt = 72.0 / 25.4
        pad = self._faca_pad()  # folga para as marcas caberem na página
        doc = fitz.open()
        try:
            for sheet in sheets:
                page = doc.new_page(
                    width=(sheet.material.width + 2 * pad) * mm2pt,
                    height=(sheet.used_length + 2 * pad) * mm2pt,
                )
                contours, segments, marks, _mk = self._dxf_payload([sheet])
                pen = {"color": (0.86, 0.0, 0.0), "width": 0.5}  # faca (vermelho)
                for contour in contours:
                    pts = [
                        fitz.Point((p.x + pad) * mm2pt, (p.y + pad) * mm2pt)
                        for p in contour.points
                    ]
                    if len(pts) >= 2:
                        page.draw_polyline(pts + [pts[0]], **pen)  # fecha o contorno
                for seg in segments:
                    page.draw_line(
                        fitz.Point((seg.start.x + pad) * mm2pt, (seg.start.y + pad) * mm2pt),
                        fitz.Point((seg.end.x + pad) * mm2pt, (seg.end.y + pad) * mm2pt),
                        **pen,
                    )
                for mark in marks:  # bolinhas de registro: PRETO solido (igual impressao)
                    page.draw_circle(
                        fitz.Point((mark.center.x + pad) * mm2pt, (mark.center.y + pad) * mm2pt),
                        mark.radius * mm2pt, color=(0, 0, 0), fill=(0, 0, 0),
                    )
            doc.save(path)
        finally:
            doc.close()
        if interactive:
            self._toasts.success("Faca exportada em PDF")
