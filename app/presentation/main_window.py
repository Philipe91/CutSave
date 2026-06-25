from __future__ import annotations

import contextlib
import tempfile
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QLocale, QObject, QPointF, QRect, QRectF, QSize, Qt, QThread, Signal
from PySide6.QtGui import (
    QAction,
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
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
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
from app.domain.cut.contour_ops import crop_and_rotate_contour, offset_contour, smooth_contour
from app.domain.cut.vector import VectorContourGenerator
from app.domain.geometry import Point2D, Size
from app.domain.model.image_artwork import ImageArtwork
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter
from app.infrastructure.importers.pymupdf_vector_extractor import PyMuPdfVectorExtractor
from app.presentation import icons, measurements, messages, theme, units
from app.presentation.panels import ribbon as ribbon_panel
from app.presentation.panels.status_bar import StatusBarController
from app.presentation.widgets import Alert, AlertLevel, CollapsibleCard, MeasureField, ToastManager
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
# DPI para rasterizar a pagina de PDF ao detectar a faca "pelo contorno".
PDF_CONTOUR_DPI = 150
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
    cursor_moved = Signal(float, float)  # posicao do cursor (x, y) em mm na cena
    library_drop = Signal(QPointF)  # arquivo arrastado da biblioteca, soltou na cena

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        # esquerdo: seleciona item / move; em area vazia faz laco de selecao.
        # meio faz pan; roda da zoom.
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor(170, 170, 170))  # mesa cinza
        self.setMouseTracking(True)  # cursor reportado mesmo sem botao pressionado
        self.setAcceptDrops(True)  # aceita arquivos arrastados da biblioteca
        # laco seleciona tudo que ele TOCAR (nao precisa envolver por inteiro)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self._panning = False
        self._pan_last = None
        self._left_drag = False

    # ---- arrastar da biblioteca para a area de trabalho ----
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
        self.view_changed.emit()  # mantem reguas/overlay/guias em sincronia

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
            # sobe ate achar um item selecionavel (peca/guia); ignora os filhos
            # (imagem/faca) e a chapa. Em area "vazia" -> laco de selecao (marquee).
            target = self.itemAt(event.position().toPoint())
            sel = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            while target is not None and not (target.flags() & sel):
                target = target.parentItem()
            if target is not None:
                self.setDragMode(QGraphicsView.NoDrag)
                self._left_drag = True
            else:
                self.setDragMode(QGraphicsView.RubberBandDrag)
                self._left_drag = False
        super().mousePressEvent(event)
        # drag_started DEPOIS do super: o Qt ja selecionou a peca clicada, entao
        # o snapshot do desfazer (_begin_move) inclui a peca que vai ser movida.
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


class ArrangementCommand(QUndoCommand):
    """Desfazer/refazer de mudancas no arranjo (excluir, duplicar, repetir).

    Guarda o conjunto de chapas (PlacedItems) antes e depois da operacao e pede
    a janela para reaplicar e redesenhar. O primeiro 'redo' (disparado pelo push)
    e ignorado, pois a operacao ja foi aplicada quando o comando e empilhado.
    """

    def __init__(self, window, before, after, text: str) -> None:
        super().__init__(text)
        self._window = window
        self._before = before
        self._after = after
        self._applied = True  # ja aplicado antes do push

    def undo(self) -> None:
        self._window._apply_arrangement(self._before)

    def redo(self) -> None:
        if self._applied:
            self._applied = False
            return
        self._window._apply_arrangement(self._after)


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
    """Regua (mm) sincronizada com o view, no estilo de softwares de pre-impressao.

    Arrastar a partir da regua cria uma guia (igual CorelDRAW): da regua de cima
    (horizontal) nasce uma guia horizontal; da regua lateral, uma guia vertical.
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
        """Converte a posicao global do mouse no valor (mm) da cena e diz se
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
    """Caixinha flutuante no canto da area de trabalho com as medidas do que
    esta selecionado (peca/grupo) ou da chapa quando nada esta selecionado.

    Transparente a cliques (nao atrapalha selecao/arraste no canvas).
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
            " border:1px solid #cfd6dd; border-radius:8px;}"
            " QLabel{color:#2c3e50; font-size:12px;}"
            " QLabel#ovTitle{font-weight:600; color:#1f2d3d;}"
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


class CropPreview(QWidget):
    """Pre-visualizacao do recorte de pagina: mostra a pagina, sombreia o que
    sera cortado e deixa arrastar as 4 bordas para definir o corte (mm)."""

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
            p.fillRect(target, QColor(255, 255, 255))
        left, top, right, bottom = self._crop
        cx0, cy0 = ox + left * mmx, oy + top * mmy
        cx1, cy1 = ox + dw - right * mmx, oy + dh - bottom * mmy
        shade = QColor(210, 40, 40, 90)
        p.fillRect(QRectF(ox, oy, dw, top * mmy), shade)
        p.fillRect(QRectF(ox, cy1, dw, bottom * mmy), shade)
        p.fillRect(QRectF(ox, cy0, left * mmx, cy1 - cy0), shade)
        p.fillRect(QRectF(cx1, cy0, right * mmx, cy1 - cy0), shade)
        pen = QPen(QColor(0, 120, 215))
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
        self.setZValue(1_000_000)  # sempre acima das pecas (mesmo apos z-order)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.SizeVerCursor if self._is_h else Qt.SizeHorCursor)

    def shape(self):
        # area de clique mais larga que a linha fina (facilita selecionar)
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


class LengthSpin(QDoubleSpinBox):
    """Campo de comprimento que guarda MILIMETROS internamente, mas exibe e
    edita na unidade atual (mm/cm).

    value()/setValue() continuam em mm (todo o app e os testes dependem disso);
    so a apresentacao muda. A conversao acontece em textFromValue/valueFromText.
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
        self._thumb_cache: dict[str, QIcon] = {}
        self._loaded = False
        self._suspend_relayout = False  # agrupa varias mudancas num so relayout
        self._guides: list[tuple[bool, float]] = []  # (horizontal, valor_mm)
        self._guide_preview_item = None
        # faca por arquivo: caminho -> params proprios (override). Sem override,
        # o arquivo segue o padrao do painel Documento.
        self._file_overrides: dict[str, dict] = {}
        # recorte de pagina (por arquivo/pagina): caminho -> {pagina: (l,t,r,b) mm}.
        # Aplicado "assando" um PDF recortado em cache; o resto do fluxo nao muda.
        self._page_crops: dict[str, dict[int, tuple]] = {}
        self._baked_crops: dict = {}      # (caminho, assinatura) -> PDF recortado em cache
        self._crop_cache: dict[str, str] = {}  # PDF recortado -> caminho original
        # faca "pelo contorno" de PDF: detecta o contorno da pagina rasterizada.
        self._contour_detector = Cv2ImageImporter()
        self._pdf_contours: dict = {}  # (caminho, pagina) -> contorno detectado
        # faca "do cliente" (vetor do PDF): usa o contorno vetorial enviado.
        self._vector_extractor = PyMuPdfVectorExtractor()
        self._vector_generator = VectorContourGenerator()
        self._vector_contours: dict = {}  # (caminho, pagina) -> contorno vetorial | None
        self._faca_notice: tuple[str, str] | None = None  # (nivel, texto) da deteccao
        self._selected_path: str | None = None
        self._selected_is_image = False
        self._pf_loading = False        # carregando controles da peca (nao gravar)
        self._keep_tab = False          # nao trocar de aba durante reselecao
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

        # unidade definida ANTES de montar a UI, para os campos ja nascerem na
        # unidade certa (LengthSpin le units.unit() ao ser criado).
        units.set_unit(getattr(settings, "unit", units.CM))

        self.setWindowTitle("PrintNest Premium")
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
        abrir = self._act("Abrir Projeto...", self.open_project, "Ctrl+O",
                          "Abre um projeto .printnest salvo")
        salvar = self._act("Salvar Projeto", self.save_project, "Ctrl+S",
                           "Salva o projeto atual")
        salvar_como = self._act("Salvar Como...", self.save_project_as, "Ctrl+Shift+S",
                                "Salva o projeto em um novo arquivo")
        add = self._act("Adicionar arquivos...", self.add_pdfs, "Ctrl+I",
                        "Importa arquivos (PDF/imagens) para a lista")
        substituir = self._act("Substituir arquivo selecionado...", self.replace_selected, None,
                               "Troca o arquivo da linha selecionada (ex.: arquivo nao encontrado)")
        gerar = self._act("Gerar Producao", self.generate, "F5",
                          "Importa, gera a faca e organiza o nesting")
        gerar_faca = self._act("Gerar Faca", self._regenerate_faca, "Shift+F5",
                               "Recria a faca das pecas (refaz a deteccao da faca do cliente)")
        fit = self._act("Ajustar a tela", self._fit_view, "F4",
                        "Enquadra todo o trabalho na tela (F4 ou Ctrl+0)")
        fit.setShortcuts([QKeySequence("F4"), QKeySequence("Ctrl+0")])
        undo = self._act("Desfazer", self._undo.undo, "Ctrl+Z",
                         "Desfaz a ultima acao (mover, excluir, duplicar, repetir)")
        redo = self._act("Refazer", self._undo.redo, "Ctrl+Y", "Refaz a acao desfeita")
        redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        grp = self._act("Agrupar", self._group_selected, "Ctrl+G",
                        "Agrupa as pecas selecionadas")
        ungrp = self._act("Desagrupar", self._ungroup_selected, "Ctrl+U",
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
        to_front = self._act("Trazer para frente", self._bring_to_front, "Shift+PgUp",
                             "Coloca as pecas selecionadas a frente das demais")
        to_back = self._act("Enviar para tras", self._send_to_back, "Shift+PgDown",
                            "Envia as pecas selecionadas para tras das demais")
        exp_pdf = self._act("Exportar PDF de impressao...", self.export_pdf, "Ctrl+E",
                            "Gera o PDF de impressao")
        exp_dxf = self._act("Exportar DXF (unico)...", self.export_dxf, None,
                            "Gera um DXF com todas as chapas")
        exp_dxf_n = self._act("Exportar DXF por chapa...", self.export_dxf_per_sheet, None,
                              "Gera um arquivo DXF para cada chapa")
        exp_faca_pdf = self._act("Exportar Faca (PDF)...", self.export_faca_pdf, None,
                                 "Gera um PDF so com a faca (linhas de corte)")
        exp_img = self._act("Exportar Imagem (PNG/JPEG)...", self.export_image, None,
                            "Rasteriza a impressao em imagem, no DPI escolhido")
        sair = self._act("Sair", self.close, None, "Fecha o programa")
        sobre = self._act("Sobre", self._show_about, None, "Sobre o PrintNest")

        bar = self.menuBar()
        m_arq = bar.addMenu("&Arquivo")
        for action in (novo, abrir, salvar, salvar_como,
                       None, add, substituir,
                       None, exp_pdf, exp_dxf, exp_dxf_n, exp_faca_pdf, exp_img,
                       None, sair):
            m_arq.addSeparator() if action is None else m_arq.addAction(action)
        m_edit = bar.addMenu("&Editar")
        for action in (undo, redo, None, sel_all, dup, step, grp, ungrp,
                       None, excluir, reset, rem):
            m_edit.addSeparator() if action is None else m_edit.addAction(action)
        m_org = bar.addMenu("&Organizar")
        for action in (grp, ungrp, None, to_front, to_back,
                       None, al_l, al_r, al_t, al_b, al_cx, al_cy,
                       None, dist_h, dist_v, None, snap_act):
            m_org.addSeparator() if action is None else m_org.addAction(action)
        limpar_guias = self._act("Limpar guias", self._clear_guides, None,
                                  "Remove todas as guias da area de trabalho")
        m_exib = bar.addMenu("E&xibir")
        m_exib.addAction(fit)
        m_exib.addAction(limpar_guias)
        m_ferr = bar.addMenu("&Ferramentas")
        m_ferr.addAction(gerar)
        m_ferr.addAction(gerar_faca)
        bar.addMenu("A&juda").addAction(sobre)

        # icones nas acoes (aparecem no menu e na ribbon)
        for action, name in (
            (novo, "file-plus"), (abrir, "folder-open"), (salvar, "save"),
            (salvar_como, "save"), (add, "plus"), (substituir, "replace"),
            (gerar, "zap"), (gerar_faca, "scissors"),
            (fit, "maximize"), (undo, "rotate-ccw"), (redo, "rotate-cw"),
            (grp, "group"), (ungrp, "ungroup"), (sel_all, "layers"), (excluir, "trash-2"),
            (reset, "rotate-ccw"), (rem, "trash-2"), (dup, "copy"), (step, "grid-3x3"),
            (al_l, "align-horizontal-justify-start"), (al_r, "align-horizontal-justify-end"),
            (al_t, "align-vertical-justify-start"), (al_b, "align-vertical-justify-end"),
            (al_cx, "align-horizontal-justify-center"), (al_cy, "align-vertical-justify-center"),
            (dist_h, "align-horizontal-justify-center"),
            (dist_v, "align-vertical-justify-center"),
            (to_front, "align-vertical-justify-start"),
            (to_back, "align-vertical-justify-end"),
            (exp_pdf, "download"), (exp_dxf, "download"), (exp_dxf_n, "download"),
            (exp_faca_pdf, "download"), (exp_img, "image"),
        ):
            action.setIcon(icons.icon(name))

        # acoes guardadas para habilitar/desabilitar conforme o estado
        self._act_generate = gerar
        self._export_actions = [exp_pdf, exp_dxf, exp_dxf_n, exp_faca_pdf, exp_img]
        for action in self._export_actions:
            action.setEnabled(False)

        # toggle de reguas espelhando o checkbox de Exibicao
        reguas = QAction("Reguas", self)
        reguas.setCheckable(True)
        reguas.setChecked(self._show_rulers.isChecked())
        reguas.setIcon(icons.icon("ruler"))
        reguas.toggled.connect(self._show_rulers.setChecked)

        # botao "Exibicao" na barra: abre um popup com os controles de exibicao
        disp_btn = QToolButton()
        disp_btn.setText("Exibicao")
        disp_btn.setIcon(icons.icon("eye", theme.ICON, 18))
        disp_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        disp_btn.setPopupMode(QToolButton.InstantPopup)
        disp_btn.setCursor(Qt.PointingHandCursor)
        disp_btn.setToolTip("Unidade, modo de visualizacao, reguas e encaixe")
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
                tb.tool_button(add, "plus"),
            ]),
            ("Editar", [
                tb.tool_button(undo, "rotate-ccw", show_text=False),
                tb.tool_button(redo, "rotate-cw", show_text=False),
                tb.tool_button(dup, "copy", show_text=False),
                tb.tool_button(step, "grid-3x3", show_text=False),
                tb.tool_button(excluir, "trash-2", show_text=False),
            ]),
            ("Organizar", [
                tb.tool_button(grp, "group", show_text=False),
                tb.tool_button(ungrp, "ungroup", show_text=False),
                tb.tool_button(to_front, "align-vertical-justify-start", show_text=False),
                tb.tool_button(to_back, "align-vertical-justify-end", show_text=False),
                tb.menu_button("Alinhar", "align-horizontal-justify-start",
                               [al_l, al_r, al_t, al_b, al_cx, al_cy], tip="Alinhar pecas"),
                tb.menu_button("Distribuir", "align-horizontal-justify-center",
                               [dist_h, dist_v], tip="Distribuir igualmente"),
                tb.tool_button(snap_act, "magnet", show_text=False),
            ]),
            ("Producao", [
                tb.tool_button(gerar, "zap", accent=True),
                tb.tool_button(gerar_faca, "scissors"),
                tb.menu_button("Exportar", "download",
                               [exp_pdf, exp_dxf, exp_dxf_n, exp_faca_pdf, exp_img],
                               tip="Exportar producao"),
            ]),
            ("Exibir", [
                tb.tool_button(fit, "maximize"),
                disp_btn,
                tb.tool_button(reguas, "ruler", show_text=False),
            ]),
        ])
        self.addToolBar(rb)

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "PrintNest Premium",
            "PrintNest Premium - preparacao de producao grafica.\n"
            "Faca, nesting e exportacao PDF/DXF.",
        )

    # ---- projeto (.printnest) ----
    def _update_title(self) -> None:
        name = Path(self._project_path).name if self._project_path else "Sem titulo"
        self.setWindowTitle(f"PrintNest Premium — {name}")

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
        self._thumb_cache.pop(path, None)
        item = QTableWidgetItem(f"{Path(path).name}\n{self._file_type(path)}")
        item.setIcon(self._thumbnail(path))
        self._table.setItem(row, 0, item)
        if self._loaded:
            self._relayout()

    def new_project(self) -> None:
        self._project_path = None
        self._reset_project_state()
        self._file_overrides = {}  # descarta facas personalizadas por arquivo
        self._page_crops = {}      # descarta recortes de pagina
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
        """Reabre o ultimo projeto ao iniciar (silencioso; nao quebra se faltar)."""
        last = self._settings.last_project
        if last and Path(last).exists():
            # nunca impedir a abertura do programa por causa de um projeto ruim
            with contextlib.suppress(Exception):
                self.open_project(last)

    # ---- construcao da UI ----
    def _build_ui(self) -> None:
        """Monta a janela: biblioteca | area de trabalho | propriedades, com
        faixa de aviso no topo e barra de status no rodape. A ribbon (acoes) e
        montada depois, em _build_menu_toolbar."""
        self._toasts = ToastManager(self)
        self._status = QLabel("")  # compat interno (mensagens antigas); nao exibido
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
        """Area de trabalho central: canvas com zoom/pan e reguas em mm."""
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
        # controles de Exibicao: vivem no popup do botao da barra de cima
        self._display_panel = self._build_display_controls()

        for ruler in (self._h_ruler, self._v_ruler):
            ruler.guide_preview.connect(self._on_guide_preview)
            ruler.guide_dropped.connect(self._on_guide_dropped)
        return work

    # ---- guias (arrastar da regua, estilo CorelDRAW) ----
    @staticmethod
    def _guide_pen() -> QPen:
        pen = QPen(QColor(0, 120, 215))
        pen.setStyle(Qt.DashLine)
        pen.setCosmetic(True)  # espessura/tracejado constantes em qualquer zoom
        return pen

    def _guides_extent(self) -> tuple[float, float, float, float]:
        """Retangulo (x0, y0, x1, y1) que as guias atravessam, com margem."""
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return -1000.0, -1000.0, 1000.0, 1000.0
        m = max(200.0, rect.width() * 0.25, rect.height() * 0.25)
        return rect.left() - m, rect.top() - m, rect.right() + m, rect.bottom() + m

    def _make_guide_line(self, is_h: bool, value: float, pen: QPen):
        """Linha simples (usada so na pre-visualizacao do arraste)."""
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
        """Atualiza a caixinha de medidas conforme a selecao (ou a chapa)."""
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
                "Peca",
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
        'Selecao' (peca ou grupo). As abas ficam sempre visiveis, entao as
        configuracoes nunca somem: clicar numa peca so muda para a aba Selecao,
        e basta clicar em 'Documento' para voltar."""
        document = QWidget()
        dl = QVBoxLayout(document)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(theme.SPACE_SM)
        dl.addWidget(self._build_chapa_group())
        dl.addWidget(self._build_faca_group())
        dl.addWidget(self._build_registro_group())
        dl.addStretch()
        doc_scroll = QScrollArea()
        doc_scroll.setWidgetResizable(True)
        doc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        doc_scroll.setWidget(document)

        # aba Selecao: pilha interna (vazio / peca / grupo)
        self._sel_stack = QStackedWidget()
        hint = QLabel("Clique numa peca na area de trabalho para ver medidas e acoes.")
        hint.setWordWrap(True)
        hint.setProperty("role", "caption")
        hint.setAlignment(Qt.AlignTop)
        hint_wrap = QWidget()
        hl = QVBoxLayout(hint_wrap)
        hl.setContentsMargins(theme.SPACE_SM, theme.SPACE_SM, theme.SPACE_SM, 0)
        hl.addWidget(hint)
        hl.addStretch()
        self._sel_stack.addWidget(hint_wrap)              # 0 = sem selecao
        self._sel_stack.addWidget(self._build_piece_page())  # 1 = peca
        self._sel_stack.addWidget(self._build_group_page())  # 2 = grupo

        self._props_tabs = QTabWidget()
        self._props_tabs.addTab(doc_scroll, "Documento")
        self._props_tabs.addTab(self._sel_stack, "Selecao")
        self._props_tabs.addTab(self._build_object_page(), "Objeto")

        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(theme.SPACE_XS, 0, 0, 0)
        wl.setSpacing(theme.SPACE_SM)
        wl.addWidget(self._props_tabs, 1)
        wrap.setMinimumWidth(280)
        wrap.setMaximumWidth(400)
        return wrap

    def _build_piece_page(self) -> QWidget:
        """Propriedades de uma peca: medidas + acoes."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_SM)
        card = CollapsibleCard("Medidas da peca")
        self._pm_w = MeasureField("Largura")
        self._pm_h = MeasureField("Altura")
        self._pm_area = MeasureField("Area")
        self._pm_perim = MeasureField("Perimetro")
        self._pm_pos = MeasureField("Posicao (X, Y)")
        for field in (self._pm_w, self._pm_h, self._pm_area, self._pm_perim, self._pm_pos):
            card.body.addWidget(field)
        lay.addWidget(card)

        # ---- faca SO deste arquivo (override) ----
        faca = CollapsibleCard("Faca deste arquivo")
        self._pf_mode_label = QLabel("Faca de PDF")
        faca.body.addWidget(self._pf_mode_label)
        self._pf_mode = QComboBox()
        self._pf_mode.addItem("Retangulo (por fora)", "rect")
        self._pf_mode.addItem("Pelo contorno (rasteriza)", "contour")
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
        self._pf_reset = QPushButton("  Usar padrao do documento")
        self._pf_reset.setIcon(icons.icon("rotate-ccw", theme.ICON))
        self._pf_reset.setToolTip("Remove a faca personalizada e volta ao padrao do Documento")
        self._pf_reset.clicked.connect(self._reset_piece_faca)
        faca.body.addWidget(self._pf_reset)
        lay.addWidget(faca)

        lay.addWidget(self._actions_card([
            ("copy", "Duplicar", self._duplicate_selected),
            ("trash-2", "Excluir", self._delete_selected),
        ]))
        lay.addStretch()
        return page

    def _build_group_page(self) -> QWidget:
        """Propriedades de varias pecas: medidas do grupo + alinhar/distribuir."""
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
        """Cartao com botoes de acao (icone + texto)."""
        card = CollapsibleCard("Acoes")
        for icon_name, text, slot in actions:
            btn = QPushButton(f"  {text}")
            btn.setIcon(icons.icon(icon_name, theme.ICON))
            btn.clicked.connect(lambda _=False, fn=slot: fn())
            card.body.addWidget(btn)
        return card

    def _build_object_page(self) -> QWidget:
        """Aba 'Objeto': lista os objetos da area de trabalho (clique seleciona) e
        oferece gerenciar objetos como no CorelDRAW: selecionar tudo, agrupar/
        desagrupar, ordem (frente/tras) e remover."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_SM)

        cap = QLabel("Objetos na area de trabalho (clique para selecionar)")
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
        """Reconstroi a lista de objetos a partir das pecas atuais."""
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
        """Reflete a selecao do canvas na lista (sem disparar de volta)."""
        if not hasattr(self, "_obj_list"):
            return
        self._obj_list.blockSignals(True)
        try:
            for row, piece in enumerate(getattr(self, "_obj_rows", [])):
                item = self._obj_list.item(row)
                if item is not None:
                    item.setSelected(piece.isSelected())
        except RuntimeError:  # peca ja deletada durante um redraw
            pass
        finally:
            self._obj_list.blockSignals(False)

    def _on_object_list_selection(self) -> None:
        """Seleciona no canvas as pecas marcadas na lista."""
        rows = {self._obj_list.row(it) for it in self._obj_list.selectedItems()}
        self._scene.clearSelection()
        for row, piece in enumerate(getattr(self, "_obj_rows", [])):
            if row in rows:
                piece.setSelected(True)

    def _bring_to_front(self) -> None:
        """Coloca as pecas selecionadas a frente das demais (ordem de empilhamento)."""
        pieces = [it for it in self._scene.selectedItems() if isinstance(it, PieceItem)]
        if not pieces:
            return
        others = [p for p in self._piece_items if p not in pieces]
        top = max((p.zValue() for p in others), default=0.0)
        for i, piece in enumerate(pieces, 1):
            piece.setZValue(top + i)

    def _send_to_back(self) -> None:
        """Envia as pecas selecionadas para tras das demais."""
        pieces = [it for it in self._scene.selectedItems() if isinstance(it, PieceItem)]
        if not pieces:
            return
        others = [p for p in self._piece_items if p not in pieces]
        bottom = min((p.zValue() for p in others), default=0.0)
        for i, piece in enumerate(pieces, 1):
            piece.setZValue(bottom - i)

    def _on_selection_changed(self) -> None:
        """Atualiza a aba 'Selecao' conforme a selecao do canvas. As abas ficam
        sempre visiveis; ao selecionar uma peca, vai para a aba Selecao, e ao
        soltar a selecao volta para Documento."""
        if not hasattr(self, "_props_tabs"):
            return
        try:
            selected = self._scene.selectedItems()
        except RuntimeError:  # cena ja destruida (fechando a janela)
            return
        pieces = [it for it in selected if isinstance(it, PieceItem)]
        cur = self._props_tabs.currentIndex()
        switch = not self._keep_tab  # durante reselecao nao troca de aba
        if not pieces:
            self._sel_stack.setCurrentIndex(0)
            self._props_tabs.setTabText(1, "Selecao")
            if switch and cur == 1:  # so volta para Documento se estiver na Selecao
                self._props_tabs.setCurrentIndex(0)
        elif len(pieces) == 1:
            self._update_piece_page(pieces[0])
            self._sel_stack.setCurrentIndex(1)
            self._props_tabs.setTabText(1, "Peca")
            if switch and cur == 0:  # nao tira o usuario da aba Objeto
                self._props_tabs.setCurrentIndex(1)
        else:
            self._update_group_page(pieces)
            self._sel_stack.setCurrentIndex(2)
            self._props_tabs.setTabText(1, f"Grupo ({len(pieces)})")
            if switch and cur == 0:
                self._props_tabs.setCurrentIndex(1)
        self._sync_object_list_selection()
        self._update_overlay()

    def _update_piece_page(self, piece: PieceItem) -> None:
        by_id = {a.id: a for a in self._result.artworks} if self._result else {}
        art = by_id.get(piece.artwork_id)
        if art is not None:
            m = measurements.piece_metrics(art)
            self._pm_w.set_value(units.fmt_len(m.width))
            self._pm_h.set_value(units.fmt_len(m.height))
            self._pm_area.set_value(units.fmt_area(m.area))
            self._pm_perim.set_value(units.fmt_len(m.perimeter))
        x = piece.pos().x() - piece.dx
        y = piece.pos().y() - piece.dy
        self._pm_pos.set_value(units.fmt_xy(x, y))
        self._load_piece_faca(piece)

    def _load_piece_faca(self, piece: PieceItem) -> None:
        """Carrega no editor a faca do arquivo da peca (override ou padrao)."""
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
            self._pf_mode.setCurrentIndex(max(0, self._pf_mode.findData(p.get("mode", "rect"))))
        finally:
            self._pf_loading = False
        # modo da faca so vale para PDF (imagem ja corta pelo contorno)
        self._pf_mode.setEnabled(not self._selected_is_image)
        self._pf_mode_label.setEnabled(not self._selected_is_image)
        # suavizar vale para imagem e para PDF cortado pelo contorno
        contour_cut = self._selected_is_image or p.get("mode") == "contour"
        self._pf_smooth.setEnabled(contour_cut)
        self._pf_smooth_label.setEnabled(contour_cut)
        self._pf_reset.setVisible(path in self._file_overrides)

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
            self._relayout()
            self._reselect_path(path)
        finally:
            self._keep_tab = False

    def _reset_piece_faca(self) -> None:
        """Remove a faca personalizada do arquivo: volta ao padrao do Documento."""
        if not self._selected_path:
            return
        path = self._selected_path
        self._file_overrides.pop(path, None)
        self._keep_tab = True
        try:
            self._relayout()
            self._reselect_path(path)
        finally:
            self._keep_tab = False

    def _reselect_path(self, path) -> None:
        """Reseleciona a 1a peca do arquivo (mantem a aba Selecao apos relayout)."""
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
        self._table.setToolTip("Arquivos e a quantidade de copias de cada um")
        self._import_box.setToolTip(
            "Caixa de Midia mantem a sangria; Caixa de Apara corta no traco de corte do PDF"
        )
        self._rotation.setToolTip("Gira todos os arquivos (graus)")
        self._width.setToolTip("Largura da chapa de material (mm)")
        self._height.setToolTip("Altura da chapa (mm). 0 = chapa unica (comprimento aberto)")
        self._spacing.setToolTip("Espaco entre as pecas (mm)")
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

    def _section(self, title: str, color: str = "") -> tuple[CollapsibleCard, QVBoxLayout]:
        """Cartao moderno recolhivel (CollapsibleCard). 'color' e ignorado (legado)."""
        card = CollapsibleCard(title)
        return card, card.body

    def _build_library_panel(self) -> QWidget:
        """Biblioteca de arquivos (esquerda): cada linha tem miniatura, nome,
        medida, paginas, tipo e quantidade. Dona do _table (contrato dos testes:
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
                logo.setAlignment(Qt.AlignHCenter)  # centraliza sobre o botao "+ Adicionar"
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
        self._table.setColumnWidth(1, 84)
        self._table.setIconSize(QSize(48, 48))
        self._table.setWordWrap(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setDragEnabled(True)  # arrastar arquivo para a area de trabalho
        self._table.setDragDropMode(QAbstractItemView.DragOnly)
        self._table.itemSelectionChanged.connect(self._update_selection_info)
        lay.addWidget(self._table, 1)

        self._btn_crop = QPushButton("  Recortar paginas...")
        self._btn_crop.setIcon(icons.icon("replace", theme.ICON))
        self._btn_crop.setToolTip(
            "Corta as bordas das paginas do PDF selecionado (cima/baixo/esq/dir),\n"
            "em todas as paginas ou nas que voce escolher."
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
        self._import_box.addItem("Caixa de Midia (sangria)", "media")
        self._import_box.addItem("Caixa de Apara (corte)", "trim")
        lay.addWidget(self._import_box)

        cap_rot = QLabel("Rotacionar arquivo (graus)")
        cap_rot.setProperty("role", "caption")
        lay.addWidget(cap_rot)
        self._rotation = QComboBox()
        self._rotation.addItems(["0", "90", "180", "270"])
        self._rotation.currentIndexChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._rotation)

        self._sel_info = QLabel("Selecione um arquivo")
        self._sel_info.setWordWrap(True)
        self._sel_info.setProperty("role", "caption")
        lay.addWidget(self._sel_info)

        panel.setMinimumWidth(260)
        panel.setMaximumWidth(420)
        return panel

    def _build_chapa_group(self) -> QFrame:
        group, lay = self._section("Chapa / Material", "#16a085")
        lay.addWidget(QLabel("Largura da chapa"))
        self._width = LengthSpin(1, 20000)
        self._width.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._width)
        lay.addWidget(QLabel("Altura da chapa (0 = chapa unica)"))
        self._height = LengthSpin(0, 20000)
        self._height.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._height)
        lay.addWidget(QLabel("Espacamento horizontal  ( − junta as pecas )"))
        self._spacing = LengthSpin(-500, 500)
        self._spacing.setToolTip(
            "Espaco entre as pecas na MESMA linha. Negativo aproxima/sobrepoe\n"
            "os retangulos (util p/ peca redonda, fecha o vao branco)."
        )
        self._spacing.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._spacing)
        lay.addWidget(QLabel("Espacamento vertical  ( − junta as linhas )"))
        self._spacing_v = LengthSpin(-500, 500)
        self._spacing_v.setToolTip("Espaco entre as LINHAS (para cima/baixo). Negativo aproxima.")
        self._spacing_v.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._spacing_v)
        return group

    def _build_faca_group(self) -> QFrame:
        group, lay = self._section("Faca", "#c0392b")
        lay.addWidget(QLabel("Sangria da faca  ( + fora  /  − dentro )"))
        self._offset = LengthSpin(-100, 100)
        self._offset.setToolTip(
            "Um campo so: valor positivo afasta a faca para FORA da arte (sangria);\n"
            "valor negativo recolhe a faca para DENTRO (recuo de seguranca)."
        )
        self._offset.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._offset)
        lay.addWidget(QLabel("Recorte da arte - cortar bordas"))
        self._crop = LengthSpin(0, 100)
        self._crop.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._crop)
        lay.addWidget(QLabel("Faca de PDF"))
        self._faca_mode = QComboBox()
        self._faca_mode.addItem("Retangulo (por fora)", "rect")
        self._faca_mode.addItem("Pelo contorno (rasteriza)", "contour")
        self._faca_mode.addItem("Faca do cliente (vetor do PDF)", "vector")
        self._faca_mode.setToolTip(
            "Retangulo: corta a caixa do PDF (por fora).\n"
            "Pelo contorno: rasteriza a pagina e corta no formato do desenho\n"
            "(ex.: circulo), removendo o fundo branco.\n"
            "Faca do cliente: usa a linha de corte vetorial que veio no PDF."
        )
        self._faca_mode.currentIndexChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._faca_mode)
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
        self._auto_ignore_white = QCheckBox("Remover fundo automatico (imagens opacas)")
        self._auto_ignore_white.setToolTip(
            "Detecta a cor do fundo pela borda e a remove (branco, escuro ou colorido).\n"
            "Desmarcado: a faca fica no retangulo da imagem inteira."
        )
        lay.addWidget(self._auto_ignore_white)
        lay.addWidget(QLabel("Sangria da faca  ( + fora  /  − dentro )"))
        self._auto_offset = LengthSpin(-100, 100)
        self._auto_offset.setToolTip(
            "Um campo so: positivo afasta a faca para FORA do desenho (sangria);\n"
            "negativo recolhe para DENTRO (recuo)."
        )
        self._auto_offset.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._auto_offset)
        lay.addWidget(QLabel("Suavizar curvas (0 = reto, 5 = macio)"))
        self._auto_smooth = _spin(0, 5)
        self._auto_smooth.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._auto_smooth)

        self._btn_reset_faca = QPushButton("  Restaurar padroes da faca")
        self._btn_reset_faca.setIcon(icons.icon("rotate-ccw", theme.ICON))
        self._btn_reset_faca.setToolTip(
            "Zera offset, recuo, recorte, giro e suavizacao para a faca sair exata\n"
            "no contorno. Aplicado sozinho a cada novo arquivo importado."
        )
        self._btn_reset_faca.clicked.connect(self._reset_faca_defaults)
        lay.addWidget(self._btn_reset_faca)
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

        lay.addWidget(QLabel("Bolinhas: afastamento / diametro"))
        self._reg_margin = LengthSpin(0, 200)
        lay.addWidget(self._reg_margin)
        self._reg_diameter = LengthSpin(1, 50)
        lay.addWidget(self._reg_diameter)

        lay.addWidget(QLabel("Mimaki: distancia do quadro"))
        self._mk_distance = LengthSpin(0, 200)
        self._mk_distance.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._mk_distance)
        lay.addWidget(QLabel("Mimaki: tamanho da marca"))
        self._mk_size = LengthSpin(1, 100)
        self._mk_size.valueChanged.connect(lambda _: self._relayout())
        lay.addWidget(self._mk_size)
        lay.addWidget(QLabel("Mimaki: espessura da marca"))
        self._mk_thickness = LengthSpin(0.1, 10)
        lay.addWidget(self._mk_thickness)
        return group

    def _build_display_controls(self) -> QWidget:
        """Painel de Exibicao (unidade, modo de visualizacao, reguas, snap) usado
        no popup do botao 'Exibicao' da barra de cima."""
        panel = QWidget()
        panel.setObjectName("displayPopup")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(5)

        cap_u = QLabel("Unidade de medida")
        cap_u.setProperty("role", "caption")
        lay.addWidget(cap_u)
        self._unit_box = QComboBox()
        self._unit_box.addItem("Centimetros (cm)", units.CM)
        self._unit_box.addItem("Milimetros (mm)", units.MM)
        self._unit_box.currentIndexChanged.connect(
            lambda _: self._on_unit_changed(self._unit_box.currentData())
        )
        lay.addWidget(self._unit_box)

        cap_v = QLabel("Modo de visualizacao")
        cap_v.setProperty("role", "caption")
        lay.addWidget(cap_v)
        self._view_mode = QComboBox()
        self._view_mode.addItem("Impressao + Corte", "both")
        self._view_mode.addItem("So Impressao", "print")
        self._view_mode.addItem("So Corte", "cut")
        self._view_mode.addItem("Tela dividida (impressao / corte)", "split")
        self._view_mode.currentIndexChanged.connect(lambda _: self._refresh_preview())
        lay.addWidget(self._view_mode)

        self._show_rulers = QCheckBox("Mostrar reguas")
        self._show_rulers.toggled.connect(lambda _: self._apply_rulers_visibility())
        lay.addWidget(self._show_rulers)
        self._snap_check = QCheckBox("Encaixar pecas ao arrastar (snap)")
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
        """Troca a unidade (mm/cm) em todo o sistema: campos, reguas e medidas."""
        units.set_unit(unit)
        for spin in self.findChildren(LengthSpin):
            spin.refresh_unit()
        self._h_ruler.update()
        self._v_ruler.update()
        self._update_selection_info()  # medida do arquivo na biblioteca
        self._on_selection_changed()   # painel da peca/grupo + overlay
        if self._loaded:
            self._save_settings()

    # ---- settings ----
    def _load_settings(self) -> None:
        s = self._settings
        self._width.setValue(int(s.material_width))
        self._height.setValue(int(s.material_height))
        self._spacing.setValue(s.spacing)
        self._spacing_v.setValue(s.spacing_v)
        # campo unico com sinal: deriva do par antigo (offset - recuo) p/ compat
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
        self._unit_box.setCurrentIndex(max(0, self._unit_box.findData(s.unit)))
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
        # campo unico com sinal -> guarda no 'offset' e zera o antigo 'safety_inset'
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
        # campo unico com sinal: +fora (sangria), -dentro (recuo)
        return float(self._offset.value())

    def _global_faca_params(self) -> dict:
        """Parametros de faca do painel Documento (padrao para arquivos novos)."""
        return {
            "offset": float(self._offset.value()),       # faca PDF (retangular)
            "auto_offset": float(self._auto_offset.value()),  # faca de imagem
            "crop": float(self._crop.value()),
            "rotation": self._rotation_value(),
            "smooth": int(self._auto_smooth.value()),
            "mode": self._faca_mode.currentData(),  # "rect" | "contour" (PDF)
        }

    def _params_for(self, path) -> dict:
        """Params de faca efetivos do arquivo: override proprio ou o padrao."""
        override = self._file_overrides.get(path)
        return dict(override) if override else self._global_faca_params()

    def _path_of(self, art_id) -> str | None:
        return self._origins.get(art_id) or self._sources.get(art_id, (None,))[0]

    def _faca_for(self, base):
        """Aplica a faca do arquivo (override ou padrao) a uma arte base."""
        params = self._params_for(self._path_of(base.id))
        if isinstance(base, ImageArtwork):
            return self._image_faca(base, params)
        if params.get("mode") == "vector":  # faca do cliente (linha vetorial do PDF)
            return self._contour_faca(base, self._pdf_vector_contour(base), params)
        if params.get("mode") == "contour":  # PDF cortado pelo contorno (rasteriza)
            return self._contour_faca(base, self._pdf_raster_contour(base), params)
        return self._faca_uc.execute(self._transform(base, params), params["offset"])

    def _pdf_vector_contour(self, base):
        """Faca do cliente: extrai o contorno vetorial do PDF (a linha de corte
        que o cliente ja desenhou). Cacheado por (caminho, pagina). Se nao houver
        vetor utilizavel, registra um aviso e cai no retangulo (raw=None)."""
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
        except Exception:  # sem vetor de corte utilizavel -> retangulo
            contour = None
            self._faca_notice = (
                "warning",
                "Nao encontrei linha de corte vetorial no PDF; usei o retangulo. "
                "Verifique se o corte foi enviado como vetor.",
            )
        self._vector_contours[key] = contour
        return contour

    def _regenerate_faca(self) -> None:
        """Botao 'Gerar Faca': refaz a deteccao da faca (contorno/cliente) e
        recalcula, sem precisar reimportar nem refazer o nesting do zero."""
        if not self._loaded:
            self._toasts.info("Gere a producao primeiro (Gerar Producao).")
            return
        self._pdf_contours = {}
        self._vector_contours = {}
        self._relayout()
        self._toasts.success("Faca gerada")

    def _pdf_raster_contour(self, base):
        """Contorno de uma pagina de PDF: rasteriza e detecta (igual imagem).
        Cacheado por (caminho, pagina); recomputado a cada nova producao."""
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
        except Exception:  # se falhar a deteccao, cai no retangulo
            contour = None
        self._pdf_contours[key] = contour
        return contour

    def _contour_faca(self, base, raw_contour, params):
        """Monta a faca a partir de um contorno (imagem ou PDF rasterizado):
        aplica recorte + giro + suavizar + sangria. Sem contorno, usa o retangulo
        do proprio tamanho (recortado/girado)."""
        crop = params["crop"]
        rotation = params["rotation"]
        net_offset = params["auto_offset"]
        if raw_contour is not None:
            contour, w, h = crop_and_rotate_contour(
                raw_contour, crop, rotation, base.size.width, base.size.height
            )
            smooth = int(params["smooth"])
            if smooth > 0:
                contour = smooth_contour(contour, smooth)
            if net_offset != 0:
                contour = offset_contour(contour, net_offset)
            return replace(base, size=Size(w, h), cut_contour=contour)
        w = base.size.width - 2 * crop
        h = base.size.height - 2 * crop
        if rotation % 360 in (90, 270):
            w, h = h, w
        return replace(base, size=Size(w, h), cut_contour=None)

    def _transform(self, art, params: dict):
        """Aplica recorte (bordas) e rotacao a uma arte (tamanho)."""
        crop = params["crop"]
        width = art.size.width - 2 * crop
        height = art.size.height - 2 * crop
        if params["rotation"] % 360 in (90, 270):
            width, height = height, width
        return replace(art, size=Size(width, height), cut_contour=None)

    def _reset_faca_defaults(self) -> None:
        """Volta as configuracoes de faca ao padrao seguro (faca exata no
        contorno: sem sangria, recuo, recorte, giro ou suavizacao).

        Chamado pelo botao 'Restaurar padroes' e automaticamente a cada novo
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
            self._rotation.setCurrentIndex(0)  # 0 graus
            self._faca_mode.setCurrentIndex(0)  # retangulo (padrao)
        finally:
            self._suspend_relayout = False
        self._relayout()

    def _image_faca(self, base: ImageArtwork, params: dict):
        """Faca de uma imagem: contorno detectado, recortado/rotacionado igual a
        arte exibida (crop + rotacao), depois suavizado e com offset.

        Recorte e rotacao precisam valer para a faca tambem (o pixmap do preview
        e girado/cortado em _display_pixmap); senao a faca fica desalinhada e o
        tamanho usado no nesting/exportacao nao bate com a imagem girada.
        """
        return self._contour_faca(base, base.raw_contour, params)

    # ---- lista de arquivos ----
    def add_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar arquivos (PDF / imagem)", self._settings.last_dir,
            IMAGE_FILE_FILTER,
        )
        if paths:
            self.add_paths(paths)
            # arquivo novo sempre entra com a faca no padrao (evita herdar
            # offset/recuo/giro antigos que deixavam a faca torta).
            self._reset_faca_defaults()
            self._settings.last_dir = str(Path(paths[0]).parent)
            self._store.save(self._settings)

    def add_paths(self, paths: list[str]) -> None:
        for path in paths:
            row = self._table.rowCount()
            self._table.insertRow(row)
            item = QTableWidgetItem(f"{Path(path).name}\n{self._file_type(path)}")
            item.setIcon(self._thumbnail(path))
            self._table.setItem(row, 0, item)
            spin = QuantityStepper(1, 100000, 1)
            spin.valueChanged.connect(lambda _: self._relayout())
            self._table.setCellWidget(row, 1, spin)
            self._table.setRowHeight(row, 58)
            self._paths.append(path)

    @staticmethod
    def _file_type(path: str) -> str:
        return Path(path).suffix.lstrip(".").upper() or "?"

    def _thumbnail(self, path: str) -> QIcon:
        """Miniatura do arquivo (1a pagina do PDF ou a propria imagem)."""
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
        paginas (apos gerar a producao). Preserva linhas ausentes (⚠)."""
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
        self._table.removeRow(row)
        del self._paths[row]
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
            self._sel_info.setText(f"{name}\n(gere a producao para ver a medida)")

    def _quantities(self) -> dict[str, int]:
        """Quantidade por arquivo, lida da tabela (path -> qtd)."""
        result: dict[str, int] = {}
        for row in range(self._table.rowCount()):
            spin = self._table.cellWidget(row, 1)
            result[self._paths[row]] = spin.value() if spin else 1
        return result

    def _crop_pages_dialog(self) -> None:
        """Dialogo de recorte de paginas do PDF selecionado na biblioteca."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._paths):
            QMessageBox.information(self, "PrintNest", "Selecione um arquivo na biblioteca.")
            return
        path = self._paths[row]
        if Path(path).suffix.lower() != ".pdf":
            QMessageBox.information(
                self, "PrintNest",
                "O recorte de paginas e para PDF. Para imagens, use 'Recorte da arte'.",
            )
            return
        try:
            import fitz
            total = fitz.open(path).page_count
        except Exception:
            QMessageBox.warning(self, "PrintNest", "Nao foi possivel abrir o PDF.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Recortar paginas — {Path(path).name}")
        dlg.resize(760, 480)
        root = QVBoxLayout(dlg)
        body = QHBoxLayout()
        root.addLayout(body, 1)

        # --- coluna esquerda: campos ---
        left_col = QWidget()
        form = QFormLayout(left_col)
        form.addRow(QLabel(f"PDF com {total} pagina(s).\nArraste as bordas ou digite (mm):"))
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
        pages_edit.setToolTip("'todas' ou paginas especificas, ex.: 1,3-5")
        form.addRow("Paginas", pages_edit)
        prev_page = QSpinBox()
        prev_page.setRange(1, total)
        form.addRow("Pre-visualizar pagina", prev_page)
        body.addWidget(left_col)

        # --- coluna direita: pre-visualizacao ---
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
        self._toasts.success(f"Recorte aplicado a {len(pages)} pagina(s)")

    def _clear_page_crop(self, path: str) -> None:
        self._page_crops.pop(path, None)
        self._invalidate_crop_cache(path)
        if self._loaded:
            self.generate(blocking=True)

    def _invalidate_crop_cache(self, path: str) -> None:
        self._baked_crops = {k: v for k, v in self._baked_crops.items() if k[0] != path}
        self._crop_cache = {c: o for c, o in self._crop_cache.items() if o != path}

    # ---- recorte de pagina (bake em PDF recortado de cache) ----
    def _effective_paths(self) -> list:
        """Caminhos a importar: o PDF recortado (cache) quando houver recorte de
        pagina; senao o original. Mantem self._paths sempre com o ORIGINAL."""
        return [self._effective_path(p) for p in self._paths]

    def _effective_path(self, path: str) -> str:
        crops = self._page_crops.get(path)
        if not crops:
            return path
        sig = tuple(sorted((pg, tuple(v)) for pg, v in crops.items()))
        cached = self._baked_crops.get((path, sig))
        if cached and Path(cached).exists():
            return cached
        out = self._bake_cropped_pdf(path, crops, sig)
        if out is None:
            return path
        self._baked_crops[(path, sig)] = out
        self._crop_cache[out] = path
        return out

    def _bake_cropped_pdf(self, path: str, crops: dict, sig) -> str | None:
        """Gera um PDF recortado em cache (corta a mediabox de cada pagina pelos
        valores em mm). So PDF; devolve o caminho ou None se falhar."""
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

    # ---- producao ----
    def _material(self) -> Material:
        return Material(
            name="MVP", width=float(self._width.value()),
            spacing=float(self._spacing.value()),
            spacing_y=float(self._spacing_v.value()),
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
        eff_paths = self._effective_paths()  # PDFs recortados quando houver recorte

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
        QMessageBox.critical(self, "PrintNest", f"Falha ao gerar producao:\n{message}")

    def _load_production(self, result: ProductionResult, png_map: dict) -> None:
        self._base_artworks = result.artworks
        self._pdf_contours = {}  # recomputa contornos de PDF na nova producao
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
        self._relayout()
        self._update_selection_info()
        self._refresh_library_metadata()
        self._toasts.success("Producao gerada")

    def _relayout(self) -> None:
        """Recalcula faca + nesting com os parametros atuais (tempo real)."""
        if not self._loaded or self._suspend_relayout:
            return
        self._undo.clear()  # arranjo regenerado do zero: zera o historico
        self._faca_notice = None  # avisos de deteccao (faca do cliente) sao refeitos
        material = self._material()
        sheet_height = float(self._height.value())
        quantities = self._quantities()
        try:
            artworks = []
            for base in self._base_artworks:
                path = self._path_of(base.id)
                qty = quantities.get(path, 0)  # arquivo removido da tabela -> 0
                if qty <= 0:
                    continue
                artworks.extend([self._faca_for(base)] * qty)
        except ValidationError:
            self._alert.show_message(
                AlertLevel.ERROR, "Recorte/recuo grande demais para a peca."
            )
            return
        if not artworks:
            self._scene.clear()
            self._alert.show_message(
                AlertLevel.WARNING, "Nenhuma peca (verifique as quantidades)."
            )
            self._status_ctl.set_production(0, 0)
            return
        sheets = self._nesting_uc.execute_sheets(artworks, material, sheet_height)
        self._result = ProductionResult(sheets=sheets, artworks=artworks, sources=self._sources)
        self._draw_preview()
        total = sum(s.item_count for s in sheets)
        self._status.setText(f"{len(sheets)} chapa(s) | {total} peca(s)")
        self._update_status_and_alerts(sheets, total, artworks, material)

    def _update_status_and_alerts(self, sheets, total, artworks, material) -> None:
        """Atualiza a barra de status e a faixa de avisos a partir da producao."""
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

    def _refresh_preview(self) -> None:
        if self._result is not None:
            self._draw_preview()

    def _draw_preview(self) -> None:
        self._piece_items = []
        self._obj_rows = []  # evita referenciar pecas deletadas no scene.clear()
        self._guide_preview_item = None  # invalidado pelo scene.clear()
        # NAO limpa o historico aqui: senao excluir/duplicar/desfazer (que
        # redesenham) apagariam o proprio comando. O reset do historico acontece
        # so quando o arranjo e regenerado (em _relayout).
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
            self._view.view_changed.emit()  # mantem o zoom; atualiza reguas
        self._refresh_object_list()
        self._update_overlay()

    def _draw_sheets(self, *, draw_art: bool, draw_cut: bool, dy: float, interactive: bool) -> None:
        result = self._result
        by_id = {a.id: a for a in result.artworks}
        sheet_brush = QBrush(QColor(255, 255, 255))  # chapa = pagina branca
        material_pen = QPen(QColor(40, 40, 40))
        material_pen.setCosmetic(True)
        faca_pen = QPen(QColor(220, 0, 0))
        faca_pen.setCosmetic(True)
        client_pen = QPen(QColor(theme.SUCCESS))  # faca do cliente (vetor) em verde
        client_pen.setCosmetic(True)
        mark_pen = QPen(QColor(0, 90, 180))
        mark_pen.setCosmetic(True)
        mark_brush = QBrush(QColor(0, 90, 180))
        empty_brush = QBrush(QColor(200, 200, 200, 120))

        shared = self._shared.currentIndex() == 1
        reg = self._reg()
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
                    p = self._params_for(self._path_of(item.artwork_id))
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

    def _add_placed(self, add_by_sheet: dict, *, text: str = "duplicar") -> None:
        """Acrescenta PlacedItems por chapa e redesenha (estende o comprimento usado)."""
        if not add_by_sheet:
            return
        before = self._snapshot_sheets()
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
        self._commit_arrangement(before, sheets, text)

    # ---- adicionar arquivo da biblioteca a producao ja gerada (arrastar) ----
    def _on_library_drop(self, scene_pos) -> None:
        row = self._table.currentRow()
        if 0 <= row < len(self._paths):
            self._add_file_to_production(self._paths[row], scene_pos)

    def _add_file_to_production(self, path: str, scene_pos) -> None:
        """Adiciona um arquivo da biblioteca a producao na posicao do drop, sem
        refazer o nesting das pecas que ja estao na chapa."""
        if self._result is None or not self._loaded:
            # ainda nao gerou: o drop ja monta a producao (sem precisar clicar
            # em "Gerar Producao"). O usuario organiza e segue dali.
            self.generate(blocking=True)
            return
        bases = [b for b in self._base_artworks if self._path_of(b.id) == path]
        if not bases:  # arquivo ainda nao importado -> importa agora
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
        self._toasts.success(f"{Path(path).name} adicionado a producao")

    def _import_file_bases(self, path: str) -> list:
        """Importa um unico arquivo (sem refazer tudo) e registra fontes/pixmaps."""
        box = self._import_box.currentData()
        eff = self._effective_path(path)  # PDF recortado quando houver recorte
        try:
            result1 = self._pipeline.execute(
                [eff], self._material(), self._effective_offset(), 0.0, box,
                sensitivity=float(self._auto_sensitivity.value()),
                ignore_white=self._auto_ignore_white.isChecked(),
            )
        except Exception:  # arquivo invalido/ausente: nao quebra a producao atual
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
        """Chapa e posicao local (mm) sob o ponto da cena onde o arquivo foi solto."""
        x, y = scene_pos.x(), scene_pos.y()
        for index, layout in enumerate(self._result.sheets):
            dx = index * (layout.material.width + SHEET_GAP_MM)
            if dx <= x <= dx + layout.material.width:
                return index, Point2D(max(0.0, x - dx), max(0.0, y))
        return 0, Point2D(max(0.0, x), max(0.0, y))

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
        self._add_placed(add, text="repetir em grade")

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

    # ---- historico de arranjo (excluir/duplicar/repetir com Ctrl+Z) ----
    def _snapshot_sheets(self) -> list:
        """Copia o arranjo atual (chapas + PlacedItems) para o historico."""
        return [
            Layout(layout.material, list(layout.items), layout.used_length)
            for layout in self._effective_sheets()
        ]

    def _apply_arrangement(self, sheets) -> None:
        """Reaplica um arranjo (lista de Layout) e redesenha: usado por desfazer/refazer."""
        if self._result is None:
            return
        self._result = ProductionResult(
            sheets=sheets, artworks=self._result.artworks, sources=self._sources
        )
        self._draw_preview()
        total = sum(s.item_count for s in sheets)
        self._status.setText(f"{len(sheets)} chapa(s) | {total} peca(s)")
        self._status_ctl.set_production(total, len(sheets))

    def _commit_arrangement(self, before, after, text: str) -> None:
        """Aplica 'after' e registra o passo no historico (Ctrl+Z desfaz)."""
        self._apply_arrangement(after)
        self._undo.push(ArrangementCommand(self, before, after, text))

    def _delete_selected(self) -> None:
        # guias selecionadas saem na hora (sem mexer no arranjo das pecas)
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
        after = self._effective_sheets()
        self._commit_arrangement(before, after, "excluir")

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
            self._toasts.success("PDF de impressao exportado")

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
            # bolinhas continuam no corte (comportamento ja validado)
            marks = registration_marks_sheets(
                sheets, artworks, sheet_width,
                margin_mm=float(self._reg_margin.value()),
                diameter_mm=float(self._reg_diameter.value()),
            )
        elif reg == "mimaki":
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
            self._toasts.success("DXF de corte exportado")

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
            self._toasts.success(f"{len(gerados)} DXF de corte exportado(s)")

    def export_faca_pdf(self, path: str | None = None, pages=None) -> None:
        """Exporta a faca (linhas de corte) em PDF vetorial, uma pagina por chapa.
        Mesma geometria do DXF (so a faca, sem marcas de registro)."""
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        sheets = self._select_export_sheets(
            self._effective_sheets(), pages, interactive, "Exportar Faca (PDF)"
        )
        if sheets is None:
            return
        if not sheets:
            if interactive:
                QMessageBox.warning(self, "PrintNest", "Nenhuma chapa selecionada.")
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
        doc = fitz.open()
        try:
            for sheet in sheets:
                page = doc.new_page(
                    width=sheet.material.width * mm2pt, height=sheet.used_length * mm2pt
                )
                contours, segments, _marks, _mk = self._dxf_payload([sheet])
                pen = {"color": (0.86, 0.0, 0.0), "width": 0.5}
                for contour in contours:
                    pts = [fitz.Point(p.x * mm2pt, p.y * mm2pt) for p in contour.points]
                    if len(pts) >= 2:
                        page.draw_polyline(pts + [pts[0]], **pen)  # fecha o contorno
                for seg in segments:
                    page.draw_line(
                        fitz.Point(seg.start.x * mm2pt, seg.start.y * mm2pt),
                        fitz.Point(seg.end.x * mm2pt, seg.end.y * mm2pt), **pen,
                    )
            doc.save(path)
        finally:
            doc.close()
        if interactive:
            self._toasts.success("Faca exportada em PDF")
