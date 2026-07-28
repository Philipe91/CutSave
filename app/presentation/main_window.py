from __future__ import annotations

import contextlib
import functools
import math
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
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
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
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
    QApplication,
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
    QGraphicsPathItem,
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
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
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
    cartela_cut_frames,
    corner_l_segments,
    corner_l_segments_sheets,
    cross_mark_segments,
    cross_mark_segments_sheets,
    mimaki_frame_contours,
    mimaki_marks,
    mimaki_marks_for_frames,
    mimaki_marks_sheets,
    positioned_cut_contours,
    positioned_cut_contours_sheets,
    registration_marks,
    registration_marks_sheets,
    shared_cut_segments,
    shared_cut_segments_sheets,
    square_marks,
    square_marks_sheets,
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
    round_corners,
    simplify_contour,
    smooth_contour,
    weld_contours,
)
from app.domain.cut.curves import cubic_segments, has_curves
from app.domain.cut.shared import Segment as SharedSegment
from app.domain.cut.shared import merge_touching_rect_cuts
from app.domain.cut.vector import VectorContourGenerator, select_cut_rings
from app.domain.geometry import Point2D, Size
from app.domain.model.cut_contour import CutContour
from app.domain.model.image_artwork import ImageArtwork, ImageKind
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.domain.nesting.max_rects import MaxRectsPacker
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter
from app.infrastructure.importers.pdfium_vector_extractor import PdfiumVectorExtractor
from app.presentation import faca_icons, icons, measurements, messages, theme, units
from app.presentation.panels import ribbon as ribbon_panel
from app.presentation.panels.status_bar import StatusBarController
from app.presentation.widgets import (
    Alert,
    AlertLevel,
    CollapsibleCard,
    IconRailTabs,
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

# Fluxo de CARTELAS pausado (16/07/2026, decisão do Philipe: "tá dando
# trabalho demais — deixe para planos futuros"). O flag esconde TODAS as
# portas de entrada (aba lateral, botão azul, menu Arquivo, grupo da
# toolbar); o motor continua vivo e testado (app/domain/cut/cartela.py,
# app/application/use_cases/cartela_nesting.py e os handlers abaixo, todos
# protegidos por _cartela_enabled()). Para religar o recurso: True aqui.
CARTELAS_ENABLED = False

# Empurrar com as setas (nudge), estilo CorelDRAW: normal, micro (Ctrl), super (Shift).
NUDGE_MM = 1.0
NUDGE_MICRO_MM = 0.1
NUDGE_SUPER_MM = 10.0
# DPI para rasterizar a página de PDF ao detectar a faca "pelo contorno".
PDF_CONTOUR_DPI = 150
# Pos-processamento da faca: remove nós redundantes com desvio máximo (mm)
# escolhido no seletor "Nós da faca". Retas ficam perfeitamente retas (os
# pontos colineares saem); curvas desviam no máximo a tolerância — bem abaixo
# do kerf da lâmina. Menos nós = corte mais fluido na máquina.
FACA_NODE_TOLERANCES = {
    "fino": 0.1,    # máximo detalhe (mais nós)
    "medio": 0.3,   # recomendado: mesma qualidade visível, bem menos nós
    "leve": 0.6,    # faca bem enxuta (curvas ligeiramente facetadas)
}
# Com SUAVIZAR ligado a tolerância cai: a simplificação removeria justamente
# os pontos que o suavizado criou ("des-suavizando" a curva em facetas).
# Nestes valores a curva continua macia e ainda corta ~85% dos nós.
FACA_NODE_TOLERANCES_SMOOTH = {"fino": 0.05, "medio": 0.08, "leve": 0.12}
FACA_POST_SIMPLIFY_MM = FACA_NODE_TOLERANCES["medio"]  # padrão
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


_DROP_FILE_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".webp")


def dropped_file_paths(event) -> list[str]:
    """Arquivos suportados num drag/drop vindo de FORA (Explorer)."""
    mime = event.mimeData()
    if not mime.hasUrls():
        return []
    return [
        u.toLocalFile() for u in mime.urls()
        if u.toLocalFile() and u.toLocalFile().lower().endswith(_DROP_FILE_EXTS)
    ]


class ZoomableGraphicsView(QGraphicsView):
    """Preview estilo CorelDRAW: zoom (roda), pan (arrastar), fundo cinza."""

    view_changed = Signal()
    drag_started = Signal()
    drag_finished = Signal()
    nudge = Signal(float, float)  # deslocamento (dx, dy) em mm, via setas
    cursor_moved = Signal(float, float)  # posição do cursor (x, y) em mm na cena
    library_drop = Signal(QPointF)  # arquivo arrastado da biblioteca, soltou na cena
    files_dropped = Signal(list)  # arquivos do EXPLORER soltos na cena
    double_clicked = Signal(QPointF)  # duplo clique (posição de cena) — Pontos

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
        # texto-guia do estado VAZIO ("" = sem guia). A MainWindow define
        # conforme a etapa: sem arquivos / com arquivos mas sem produção.
        self.empty_hint = ""
        self.empty_step = 0  # passo do fluxo na faixa ilustrada (0=Adicionar)

    def drawForeground(self, painter, rect) -> None:  # noqa: N802
        super().drawForeground(painter, rect)
        # estado vazio orientando (QA 2.0/C7): sem isto o primeiro contato era
        # uma tela cinza morta — o operador não sabia que dava para arrastar.
        if not self.empty_hint:
            return
        painter.save()
        painter.resetTransform()  # desenha em coordenadas do viewport
        painter.setPen(QColor(theme.TEXT_MUTED))
        f = painter.font()
        f.setPointSizeF(f.pointSizeF() + 7)  # grande o bastante p/ parecer
        f.setWeight(QFont.DemiBold)          # intencional, nao artefato
        painter.setFont(f)
        vr = self.viewport().rect()
        painter.drawText(vr, Qt.AlignCenter, self.empty_hint)
        # os 3 passos do fluxo ilustrados acima do texto, com o atual em
        # destaque (Adicionar -> Gerar Faca -> Exportar)
        strip = faca_icons.empty_steps_pixmap(self.empty_step)
        tr = painter.fontMetrics().boundingRect(vr, Qt.AlignCenter, self.empty_hint)
        painter.drawPixmap(
            int(vr.center().x() - strip.width() / 2),
            max(8, int(tr.top() - strip.height() - 28)),
            strip,
        )
        painter.restore()

    # ---- arrastar da biblioteca para a área de trabalho ----
    @staticmethod
    def _is_library_drag(event) -> bool:
        src = event.source()
        return isinstance(src, QTableWidget) or event.mimeData().hasFormat(
            "application/x-qabstractitemmodeldatalist"
        )

    def dragEnterEvent(self, event) -> None:
        # arquivos do Explorer: o texto-guia PROMETE "arraste para cá" — o
        # drop era recusado (cursor proibido) e parecia que o app travou.
        if self._is_library_drag(event) or dropped_file_paths(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._is_library_drag(event) or dropped_file_paths(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if self._is_library_drag(event):
            self.library_drop.emit(self.mapToScene(event.position().toPoint()))
            event.acceptProposedAction()
            return
        files = dropped_file_paths(event)
        if files:
            self.files_dropped.emit(files)
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

    def mouseDoubleClickEvent(self, event) -> None:
        super().mouseDoubleClickEvent(event)  # itens (ex.: alça de nó) primeiro
        self.double_clicked.emit(self.mapToScene(event.position().toPoint()))

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
# Janela (s) para considerar dois recalculos "o MESMO gesto" (segurar a
# setinha). Fora dela, cada ajuste vira um passo próprio de desfazer — sem
# isto, TODOS os ajustes da sessão fundiam num comando só e um Ctrl+Z
# "voltava pro início" (bug do beta 13/07).
_MERGE_WINDOW_S = 1.5


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
        import time
        self._stamp = time.monotonic()

    def id(self) -> int:
        return self._merge_id

    def mergeWith(self, other) -> bool:
        # funde SÓ recalculos do mesmo tipo feitos em sequência rápida (mesmo
        # gesto: segurar a setinha/digitar). Passou a janela de tempo, o novo
        # ajuste vira um passo próprio — Ctrl+Z desfaz UM ajuste por vez.
        if self._merge_id < 0 or other.id() != self._merge_id:
            return False
        if other._stamp - self._stamp > _MERGE_WINDOW_S:
            return False
        self._after = other._after
        self._stamp = other._stamp  # gesto continua: janela desliza
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
        # maozinha estilo Corel/Photoshop: aberta ao pairar, fechada movendo
        # (so faz sentido quando a peça e movel — ver mousePress/Release).
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event) -> None:
        if self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable:
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

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
        # fundo/borda no QSS global (#measureOverlay) — tema troca ao vivo
        for w in (self._line1, self._line2):
            w.setProperty("role", "caption")
        self._title.setProperty("role", "cardTitle")
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
        # fundo/borda no QSS global (#floatBar) — tema troca ao vivo; o combo
        # compacto mantém só o ajuste de densidade local (sem cores fixas)
        self.setStyleSheet(
            "#floatBar QComboBox{min-height:16px; padding:2px 8px;}"
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


class _NodeHandle(QGraphicsRectItem):
    """Alça de nó da faca (ferramenta Pontos, estilo Corel F10).

    Quadradinho sobre um ponto do contorno de corte: arrastar MOVE o nó
    (corrige onde a faca "comeu" o desenho); duplo clique REMOVE o nó.
    Filha da peça (coords locais), tamanho fixo na tela (ignora zoom)."""

    S = 8.0

    def __init__(self, window, piece, ci: int, pi: int) -> None:
        super().__init__(-self.S / 2, -self.S / 2, self.S, self.S)
        self._w = window
        self._piece = piece
        self.ci = ci  # indice do contorno (0 = principal; 1+ = extras)
        self.pi = pi  # indice do ponto dentro do contorno
        self.setBrush(QBrush(QColor(theme.SURFACE)))
        pen = QPen(QColor(theme.CUT))
        pen.setCosmetic(True)
        pen.setWidth(2)
        self.setPen(pen)
        self.setZValue(2100)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setCursor(Qt.CrossCursor)

    # arraste manual (mapeando a cena) para ficar 1:1 em qualquer zoom
    def mousePressEvent(self, event) -> None:
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        self.setPos(self._piece.mapFromScene(event.scenePos()))
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.setPos(self._piece.mapFromScene(event.scenePos()))
        self._w._end_node_drag(self._piece)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        self._w._remove_node(self._piece, self.ci, self.pi)
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
                 sensitivity=50.0, ignore_white=True, pages=None):
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
        self._pages = pages

    def run(self) -> None:
        try:
            result = self._pipeline.execute(
                self._paths, self._material, self._offset, self._sheet_height, self._box,
                on_progress=lambda done, total: self.progress.emit(done, total),
                sensitivity=self._sensitivity, ignore_white=self._ignore_white,
                pages=self._pages,
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
        title.setProperty("role", "cardTitle")  # QSS: acompanha o tema ao vivo
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


@contextmanager
def _wait_cursor():
    """Cursor de espera em operações longas na thread da UI (QA 2.0/C6:
    exportações travavam a janela sem NENHUM feedback — parecia crash)."""
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


# referência ao critical REAL do Qt: se um teste monkeypatchar (QA-02), a
# identidade muda e o guard usa o dublê; se NÃO patchou, abrir modal em teste
# offscreen = suite travada -> re-levanta (falha alto, visível no CI).
_REAL_CRITICAL = QMessageBox.critical


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
            import os
            if (
                os.environ.get("PYTEST_CURRENT_TEST")
                and QMessageBox.critical is _REAL_CRITICAL
            ):
                raise  # em teste SEM dublê, modal = suite travada; falhar ALTO
            QMessageBox.critical(self, "PrintNest", f"Falha ao exportar:\n{exc}")
            return None
    return wrapper


# célula da âncora: 18px é o menor corpo em que as setas diagonais ainda se
# leem (a 14px a ponta some no antialiasing e vira um risco)
ANCHOR_CELL = 18
ANCHOR_GAP = 3


class AnchorCell(QPushButton):
    """Célula da AnchorGrid: a caixinha vem do stylesheet, a seta é pintada aqui.

    A seta é desenhada numa caixa normalizada de 24 unidades e escalada para o
    tamanho da célula — assim o desenho fica igual em qualquer tamanho e sai
    limpo mesmo nos 14px do painel (glifo de fonte nesse corpo vira borrão)."""

    def __init__(self, col: int, row: int) -> None:
        super().__init__()
        self._c, self._r = col, row
        self._center = col == 1 and row == 1
        self.setObjectName("anchorMid" if self._center else "anchorDot")
        self.setCheckable(True)
        self.setFixedSize(ANCHOR_CELL, ANCHOR_CELL)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event) -> None:  # repinta a seta no hover
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.update()

    def _ink(self) -> QColor:
        if self.isChecked():
            return QColor(theme.ICON_ON_ACCENT)  # seta sobre o azul
        if self.underMouse():
            return QColor(theme.ACCENT)
        return QColor(theme.TEXT_MUTED)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)  # caixa/borda/fundo pelo stylesheet
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        p.translate(rect.center().x() + 0.5, rect.center().y() + 0.5)
        p.scale(rect.width() / 24.0, rect.height() / 24.0)
        ink = self._ink()
        if self._center:
            # centro não tem sentido: marca de "usa o X/Y digitado"
            p.setPen(Qt.NoPen)
            p.setBrush(ink)
            p.drawEllipse(QPointF(0.0, 0.0), 3.2, 3.2)
            p.end()
            return
        dx, dy = self._c - 1, self._r - 1
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        px, py = -uy, ux  # perpendicular, para a base da ponta
        # ponta comprida e haste curta: a 14px uma seta "normal" perde a cabeça
        # no antialiasing e vira um risco sem sentido (pior nas diagonais)
        tip = QPointF(ux * 5.6, uy * 5.6)
        base = QPointF(ux * 0.4, uy * 0.4)
        pen = QPen(ink)
        pen.setWidthF(2.4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(-ux * 5.0, -uy * 5.0), base)
        p.setPen(Qt.NoPen)
        p.setBrush(ink)
        p.drawPolygon(
            QPolygonF(
                [
                    tip,
                    QPointF(base.x() + px * 3.2, base.y() + py * 3.2),
                    QPointF(base.x() - px * 3.2, base.y() - py * 3.2),
                ]
            )
        )
        p.end()


class AnchorGrid(QWidget):
    """Grade 3x3 de direção (estilo CorelDRAW): clicar num sentido preenche o
    X/Y do duplicar com o tamanho da peça naquele eixo (cópia encostada). Emite
    `picked(col, row)` — col/row em 0..2 (centro = 1,1)."""

    picked = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self._col, self._row = 1, 1  # centro
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(ANCHOR_GAP)
        self._btns = {}
        for r in range(3):
            for c in range(3):
                b = AnchorCell(c, r)
                b.clicked.connect(lambda _=False, cc=c, rr=r: self._pick(cc, rr))
                self._btns[(c, r)] = b
                grid.addWidget(b, r, c)
        self._btns[(1, 1)].setChecked(True)
        # trava o tamanho: 3 celulas + 2 espacos (senao a grade estica na
        # vertical ao lado dos campos X/Y e fica com aparencia bugada)
        side = ANCHOR_CELL * 3 + ANCHOR_GAP * 2
        self.setFixedSize(side, side)
        self.setToolTip(
            "Direção da cópia (estilo Corel): clique numa seta e o X/Y é\n"
            "preenchido com o tamanho da peça — a cópia sai encostada naquele\n"
            "sentido. Depois ajuste X/Y para dar folga.\n"
            "Centro (ponto): usa o X/Y que você digitar."
        )
        self.apply_theme()

    def apply_theme(self) -> None:
        """(Re)pinta as caixinhas com o tema ATUAL. Folha de widget congela a
        cor na montagem; sem reaplicar, a ancora ficava BRANCA no tema escuro.
        (As setas nao precisam: sao pintadas com os tokens a cada paintEvent.)"""
        self.setStyleSheet(
            # o QSS global de QPushButton traz padding 7x16 + min-height 22 (=38px
            # de altura). No Qt o min do stylesheet ganha do setFixedSize, entao as
            # celulas saiam 18x38, sobrepostas — tem que zerar aqui.
            # (o box do QSS mede o conteudo: desconta a borda dos dois lados)
            f"#anchorDot,#anchorMid{{padding:0; margin:0;"
            f" min-width:{ANCHOR_CELL - 2}px; max-width:{ANCHOR_CELL - 2}px;"
            f" min-height:{ANCHOR_CELL - 2}px; max-height:{ANCHOR_CELL - 2}px;"
            f" border:1px solid {theme.BORDER};"
            f" border-radius:3px; background:{theme.SURFACE};}}"
            f"#anchorMid{{background:{theme.SURFACE_ALT};}}"
            f"#anchorDot:hover,#anchorMid:hover{{border-color:{theme.BORDER_STRONG};"
            f" background:{theme.ACCENT_SOFT};}}"
            f"#anchorDot:checked,#anchorMid:checked{{background:{theme.ACCENT};"
            f" border-color:{theme.ACCENT};}}"
        )

    def _pick(self, c: int, r: int) -> None:
        self._col, self._row = c, r
        for key, b in self._btns.items():
            b.setChecked(key == (c, r))
        self.picked.emit(c, r)

    def anchor(self) -> tuple[float, float]:
        return self._col / 2.0, self._row / 2.0


class StatValue(QLabel):
    """QLabel de valor de métrica com a MESMA interface do MeasureField
    (set_value), para o _update_resumo continuar valendo sem alteração."""

    def set_value(self, value: str) -> None:
        self.setText(value)


class StatTile(QFrame):
    """Bloco de métrica do Resumo (estilo dashboard, U1 redesign 27/07): chip de
    ícone no topo, valor em destaque e legenda. Neutro por padrão."""

    def __init__(self, icon_name: str, caption: str) -> None:
        super().__init__()
        self.setObjectName("statTile")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 9)
        lay.setSpacing(2)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        chip = QLabel()
        chip.setObjectName("stChip")
        chip.setFixedSize(24, 24)
        chip.setAlignment(Qt.AlignCenter)
        self._icon_name = icon_name
        self._chip = chip
        top.addStretch()
        top.addWidget(chip)
        self.value = StatValue("—")
        self.value.setObjectName("stVal")
        cap = QLabel(caption)
        cap.setObjectName("stCap")
        lay.addLayout(top)
        lay.addWidget(self.value)
        lay.addWidget(cap)
        self.apply_theme()

    def apply_theme(self) -> None:
        """(Re)pinta com os tokens do tema ATUAL — o icone do chip junto.

        As cores eram chumbadas (#f6f8fb / #e7eefc / #111827): no tema escuro os
        quatro blocos do Resumo ficavam BRANCOS no meio do painel. Folha de
        widget congela a cor na montagem, entao isto tem de ser chamado de novo
        na troca de tema (MainWindow._on_theme_changed)."""
        self._chip.setPixmap(icons.pixmap(self._icon_name, theme.ACCENT, 15))
        self.setStyleSheet(
            f"#statTile{{background:{theme.SURFACE_ALT}; border-radius:14px;}}"
            f"#stVal{{font-size:15px; font-weight:700; color:{theme.TEXT};}}"
            f"#stCap{{font-size:10px; color:{theme.TEXT_MUTED};}}"
            f"#stChip{{background:{theme.ACCENT_SOFT}; border-radius:7px;}}"
        )

    def set_value(self, value: str) -> None:
        self.value.set_value(value)


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
        # faca EDITADA A MAO (ferramenta Pontos): caminho -> {"contours": tuple
        # de CutContour (principal + extras), "w"/"h": tamanho da arte e
        # "rotation": giro efetivo no momento da edição. Quando existe, VENCE o
        # recalculo automatico (sangria/suavizar não se aplicam mais ao arquivo
        # até "voltar ao automático"). Todas as cópias do arquivo herdam.
        self._faca_manual: dict[str, dict] = {}
        self._nodes_tool_on = False       # ferramenta Pontos (F10) ativa?
        self._node_handles: list = []     # alças de nó na peça selecionada
        # tamanho por arquivo: caminho -> Size (mm) desejado. Sem entrada, o
        # arquivo mantem o tamanho original importado. Aplicado na arte base
        # antes da faca (escala arte + contornos); vale para todas as cópias.
        self._file_sizes: dict[str, Size] = {}
        # rotação POR PECA: artwork_id -> giro extra (0/90/180/270) somado ao
        # giro do arquivo. Permite girar só uma peça (ex.: a sobra solta) para
        # encaixar melhor no nesting, sem mexer nas outras cópias/páginas.
        self._piece_rotations: dict[str, int] = {}
        # arranjo manual salvo no .printnest (QA A0), pendente de aplicar na
        # PRIMEIRA geração após abrir o projeto (abrir não gera sozinho).
        self._pending_arranjo: dict | None = None
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
        # paginas escolhidas por PDF: caminho -> [indices 0-based]. Caminho
        # ausente = TODAS (o padrao de sempre; so entra aqui quem escolheu).
        self._file_pages: dict[str, list[int]] = {}
        self._baked_crops: dict = {}      # (caminho, assinatura) -> PDF recortado em cache
        self._crop_cache: dict[str, str] = {}  # PDF recortado -> caminho original
        # faca "pelo contorno" de PDF: detecta o contorno da página rasterizada.
        self._contour_detector = Cv2ImageImporter()
        self._pdf_contours: dict = {}  # (caminho, página) -> contorno detectado
        # faca "do cliente" (vetor do PDF): usa o contorno vetorial enviado.
        self._vector_extractor = PdfiumVectorExtractor()
        self._vector_generator = VectorContourGenerator()
        self._vector_contours: dict = {}  # (caminho, página) -> contorno vetorial | None
        self._faca_notice: tuple[str, str] | None = None  # (nivel, texto) da detecção
        self._selected_path: str | None = None
        self._selected_is_image = False
        self._pf_loading = False        # carregando controles da peça (não gravar)
        self._keep_tab = False          # não trocar de aba durante reselecao
        self._clearing_scene = False    # dentro do scene.clear(): não reagir
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
        # QAX-01: QUALQUER mexida na pilha (mover, duplicar, excluir, ajustar,
        # undo/redo) marca o trabalho como alterado — editar depois de salvar
        # deixava _dirty=False e o fechamento descartava trabalho em silêncio.
        # (Abrir/gerar zeram a pilha e o fluxo re-seta _dirty=False no final.)
        self._undo.indexChanged.connect(lambda _i: self._mark_dirty())
        self._fit_next = True  # ajusta o zoom só após gerar; preserva no relayout
        self._snap = SnapConfig()
        self._project_store = ProjectStore()
        self._project_path: str | None = None

        # unidade definida ANTES de montar a UI, para os campos já nascerem na
        # unidade certa (LengthSpin le units.unit() ao ser criado).
        units.set_unit(getattr(settings, "unit", units.CM))

        self.setWindowTitle("PrintNest Premium")
        self.setAcceptDrops(True)  # arquivos do Explorer em qualquer ponto da janela
        self._build_ui()
        self._illustrate_all()  # miniaturas ilustrativas (nós, registro, caixas...)
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
        # o botão visivel mora na barra Faca (propBar); a QAction fica na janela
        # para o atalho Shift+F5 continuar funcionando
        gerar_faca = self._act("Gerar Faca", self._regenerate_faca, "Shift+F5",
                               "Recria a faca das peças (refaz a detecção da faca do cliente)")
        self.addAction(gerar_faca)
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
        fit_sheet = self._act(
            "Ajustar chapa ao conteúdo", self._fit_sheets_to_content, "Ctrl+Shift+F",
            "Encolhe a chapa para o tamanho exato do arranjo — a exportação sai "
            "rente ao conteúdo (marcas de registro entram na folga), sem branco em volta",
        )
        reset = self._act("Resetar arranjo", self._reset_arrangement, None,
                          "Refaz o nesting do zero (descarta ajustes manuais)")
        modo_corte = self._act("Modo Corte", self._open_cut_mode, None,
                               "Nesting pelo contorno REAL (laser/CNC): importa SVG, PDF "
                               "ou texto, encaixa as peças e exporta o DXF")
        rem = self._act("Remover arquivo da biblioteca", self.remove_selected, None,
                        "Remove o arquivo selecionado da lista da biblioteca")
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
        exp_mimaki = self._act("Exportar Faca Mimaki (PDF)...", self.export_faca_mimaki, None,
                               "Faca das peças para a Mimaki (sem bolinhas de registro)")
        exp_iecho = self._act("Exportar Faca IECHO (DXF)...", self.export_faca_iecho, None,
                              "Linhas de separação das cartelas (fora a fora) + bolinhas")
        exp_cartelas = self._act("Exportar produção em cartelas...", self.export_producao_cartelas,
                                 None,
                                 "Gera os 3 arquivos de uma vez: impressão com as duas marcas, "
                                 "faca Mimaki e faca IECHO")
        exp_mimaki_cart = self._act("Exportar Faca Mimaki (1 cartela)...",
                                    self.export_faca_mimaki_cartela, None,
                                    "Faca das peças de UMA cartela (todas são iguais no "
                                    "fluxo de cartelas idênticas)")
        cartelas_act = self._act("Cartelas e refile", self._show_cartelas_tab, None,
                                 "Abre a aba lateral 'Cartelas': monte a cartela, repita na "
                                 "chapa e exporte as facas Mimaki + refile")
        sair = self._act("Sair", self.close, None, "Fecha o programa")
        sobre = self._act("Sobre", self._show_about, None, "Sobre o PrintNest")

        # itens do fluxo de cartelas só entram no menu com o flag ligado
        menu_cartelas = (
            (None, cartelas_act, exp_cartelas, exp_mimaki_cart, exp_iecho)
            if CARTELAS_ENABLED else ()
        )
        bar = self.menuBar()
        m_arq = bar.addMenu("&Arquivo")
        for action in (novo, abrir, salvar, salvar_como, fechar_aba,
                       None, add, substituir,
                       None, exp_center,
                       None, exp_pdf, exp_dxf, exp_dxf_n, exp_faca_pdf, exp_img,
                       None, exp_mimaki,
                       *menu_cartelas,
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
        for action in (organizar, fit_sheet, center_act, None, grp, ungrp, None, to_front, to_back,
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
        # ferramenta Pontos (F10): editar os nós da linha de corte
        pontos = QAction("Pontos — editar nós da faca", self)
        pontos.setCheckable(True)
        pontos.setShortcut(QKeySequence("F10"))
        pontos.setIcon(icons.icon("nodes"))
        pontos.setToolTip(
            "Edita os nós da linha de corte (F10): arraste um nó para mover;\n"
            "duplo clique no traço adiciona; duplo clique num nó remove.\n"
            "A faca editada vale para o ARQUIVO (as cópias herdam)."
        )
        pontos.toggled.connect(self._set_nodes_tool)
        self._nodes_action = pontos

        m_ferr = bar.addMenu("&Ferramentas")
        m_ferr.addAction(gerar)
        m_ferr.addAction(gerar_faca)
        m_ferr.addAction(pontos)

        # Opções (ao lado de Ajuda): unidade de medida (cm/mm)
        m_opt = bar.addMenu("O&pções")  # Alt+P (Alt+O já e do menu Organizar; QA-09)
        # ---- Theme Engine: Aparência (tema + personalizar) ----
        from app.presentation.themes import manager as _theme_manager
        from app.presentation.themes.palettes import THEMES as _THEMES
        ap = m_opt.addMenu("Aparência")
        tm = ap.addMenu("Tema")
        tm_group = QActionGroup(self)
        tm_group.setExclusive(True)
        _tm = _theme_manager()
        for key, label in (
            *((k, lbl) for k, (lbl, _p, _d) in _THEMES.items()),
            ("auto", "Automático (segue o Windows)"),
        ):
            act = QAction(label, self, checkable=True)
            act.setChecked(_tm.theme_key == key)
            act.triggered.connect(lambda _=False, k=key: _theme_manager().set_theme(k))
            tm_group.addAction(act)
            tm.addAction(act)
        ap.addSeparator()
        ap.addAction("Personalizar Interface...", self._show_theme_dialog)
        _tm.theme_changed.connect(self._on_theme_changed)
        m_opt.addSeparator()
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
        tour = self._act("Tour de boas-vindas", lambda: self._start_tour(force=True),
                         None, "Reapresenta o guia passo a passo do programa")
        m_ajuda = bar.addMenu("A&juda")
        m_ajuda.addAction(tour)
        m_ajuda.addSeparator()
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
        self._export_actions = [exp_center, exp_pdf, exp_dxf, exp_dxf_n, exp_faca_pdf, exp_img,
                                exp_cartelas, exp_mimaki, exp_iecho]
        # tooltip original guardado para o aviso "gere primeiro" (U1/P7)
        self._export_tips = {a: a.toolTip() for a in self._export_actions}
        self._set_exports_enabled(False)

        # botão "Exibição" na barra: abre um popup com os controles de exibição
        disp_btn = QToolButton()
        disp_btn.setText("Exibição")
        disp_btn.setIcon(icons.icon("eye", theme.ICON, 18))
        disp_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        disp_btn.setPopupMode(QToolButton.InstantPopup)
        disp_btn.setCursor(Qt.PointingHandCursor)
        disp_btn.setToolTip("Réguas e encaixe (snap)")
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
                tb.tool_button(pontos, "nodes", show_text=False),  # F10
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
            *([("Cartelas", [
                # fluxo cartela + refile a UM clique (pedido do cliente: fora
                # da lista de cards do Documento); vem ANTES de Exportar para
                # não cair no overflow (») da barra em telas menores.
                tb.tool_button(cartelas_act, "scissors"),
            ])] if CARTELAS_ENABLED else []),
            ("Corte", [
                # Modo Corte (laser/CNC) e um fluxo SEPARADO: abre em dialogo
                # proprio, com cena e exportacao proprias, e nao mexe no
                # arranjo de impressao que estiver na tela.
                tb.tool_button(modo_corte, "scissors"),
            ]),
            ("Exportar", [
                # QA 2.0: o grupo só tem exportações — o nome dizia "Produção"
                # e mentia. Faca inteira mora na barra Faca (propBar).
                tb.tool_button(exp_center, "download"),
                tb.menu_button("Mais...", "download",
                               [exp_pdf, exp_dxf, exp_dxf_n, exp_faca_pdf, exp_img],
                               tip="Exportar formato especifico"),
            ]),
            ("Exibir", [
                tb.tool_button(fit, "maximize"),
                self._view_mode_menu_button(),  # visualização ao lado de Ajustar
                disp_btn,
                # U1/P4: o toggle solto de Réguas saiu — duplicava o checkbox
                # "Mostrar réguas" do popup Exibição no MESMO grupo da barra.
            ]),
        ])
        self._ribbon = rb  # referência p/ o tour de boas-vindas
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

    # ---- tour de boas-vindas (o "tutor" dentro do software) ----
    def _start_tour(self, force: bool = False) -> None:
        """Guia passo a passo na primeira abertura (Ajuda → Tour repete)."""
        import os

        from app.presentation.onboarding import TourOverlay, TourStep, tour_done
        if not force and (tour_done() or os.environ.get("PYTEST_CURRENT_TEST")):
            return
        steps = [
            TourStep(
                getattr(self, "_btn_add", None), "1. Adicione seus arquivos",
                "Tudo começa aqui: clique em Adicionar arquivos (ou arraste "
                "PDF, PNG e JPG direto para a área de trabalho).",
            ),
            TourStep(
                getattr(self, "_view", None), "2. Sua mesa de trabalho",
                "As chapas ficam aqui. Zoom com a roda do mouse (vai onde o "
                "cursor aponta), arraste com o botão do meio ou a tecla H, e "
                "F4 enquadra tudo de volta.",
            ),
            TourStep(
                getattr(self, "_prop_bar", None), "3. A barra da Faca",
                "Quando houver arquivos, a barra ✂ Faca aparece aqui: escolha "
                "o Tipo, ajuste Offset e Suavizar e clique no botão azul "
                "GERAR FACA. Com uma peça selecionada, os ajustes valem só "
                "para o arquivo dela.",
            ),
            TourStep(
                getattr(self, "_props_tabs", None), "4. Documento e Peça",
                "À direita: a chapa (medidas, espaçamentos), o acabamento e "
                "as marcas de registro. Selecionou uma peça? A aba Peça "
                "mostra os ajustes só daquele arquivo.",
            ),
            TourStep(
                getattr(self, "_ribbon", None), "5. Exportar",
                "Terminou? O Centro de Exportação gera o PDF de impressão e "
                "o DXF/PDF de corte para a sua máquina — com marcas de "
                "registro e tudo.",
            ),
            TourStep(
                None, "Pronto para produzir",
                "É só isso: adicionar, gerar faca e exportar. Para rever "
                "este guia a qualquer momento: menu Ajuda, Tour de "
                "boas-vindas. Bom trabalho!",
            ),
        ]
        TourOverlay(self, steps)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not getattr(self, "_tour_checked", False):
            self._tour_checked = True
            QTimer.singleShot(800, self._start_tour)

    def _show_theme_dialog(self) -> None:
        """Opções → Personalizar Interface... (Theme Engine, live preview)."""
        from app.presentation.themes import manager as _theme_manager
        from app.presentation.themes.settings_dialog import ThemeSettingsDialog
        ThemeSettingsDialog(_theme_manager(), self).exec()

    def _refresh_logo(self) -> None:
        """Logo certa para o tema: original no claro, invertida no escuro."""
        if getattr(self, "_logo_label", None) is None:
            return
        pm = self._logo_dark if (theme.is_dark() and not self._logo_dark.isNull()) \
            else self._logo_light
        self._logo_label.setPixmap(pm.scaledToWidth(200, Qt.SmoothTransformation))

    def _on_theme_changed(self) -> None:
        """Tema trocou ao vivo: redesenha o que pinta com tokens em runtime
        (canvas, réguas, logo). O QSS global o ThemeManager já reaplicou."""
        self._refresh_logo()
        if self._result is not None:
            self._draw_preview()
        for name in ("_ruler_h", "_ruler_v"):
            r = getattr(self, name, None)
            if r is not None:
                r.update()
        if hasattr(self, "_view"):
            self._view.setBackgroundBrush(QColor(theme.CANVAS_BG))
            self._view.viewport().update()
        # miniaturas ilustrativas carregam cores do tema: redesenha todas
        self._illustrate_all()
        # trilho do inspector: icones re-renderizados na cor do tema novo
        rail = getattr(self, "_props_tabs", None)
        if rail is not None:
            rail.refresh_icons()
        # folha de widget nao acompanha o tema sozinha: repinta quem tem a sua
        self._apply_doc_tabs_theme()
        self._apply_resumo_theme()
        ancora = getattr(self, "_td_anchor", None)
        if ancora is not None:
            ancora.apply_theme()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        """Arquivos do Explorer soltos em QUALQUER ponto da janela entram na
        biblioteca (o canvas promete "arraste para cá" — tem de funcionar)."""
        if dropped_file_paths(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        files = dropped_file_paths(event)
        if files:
            event.acceptProposedAction()
            self.add_paths(files)
        else:
            super().dropEvent(event)

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
            ProjectFile(
                path=path, quantity=quantities.get(path, 1), rotation=rotation,
                pages=list(self._file_pages.get(path, ())) or None,
            )
            for path in self._paths
        ]
        settings = {key: getattr(self._settings, key) for key in PROJECT_SETTING_KEYS}
        return ProjectDocument(
            files=files, settings=settings,
            file_overrides={p: dict(ov) for p, ov in self._file_overrides.items()},
            faca_manual=self._manual_faca_to_json(),
            arranjo=self._arranjo_to_json(),
        )

    def _arranjo_signature(self) -> list:
        """Assinatura leve (arquivos + quantidades, na ordem da biblioteca):
        invalida o arranjo salvo se a lista mudar entre salvar e regenerar."""
        quantities = self._quantities()
        return [[p, int(quantities.get(p, 1))] for p in self._paths]

    def _arranjo_to_json(self) -> dict:
        """QA A0: o arranjo MANUAL (duplicatas, posições e giro por peça) entra
        no .printnest sempre que houver produção na tela. Derivado de
        _effective_sheets() — o caminho único canvas->modelo — nunca da cena."""
        if not self._loaded or self._result is None:
            return {}
        return {
            "assinatura": self._arranjo_signature(),
            "giros": {
                art_id: int(rot) % 360
                for art_id, rot in self._piece_rotations.items()
                if int(rot) % 360
            },
            "chapas": [
                {
                    "comprimento": round(float(layout.used_length), 3),
                    "itens": [
                        {
                            "id": item.artwork_id,
                            "x": round(float(item.position.x), 3),
                            "y": round(float(item.position.y), 3),
                        }
                        for item in layout.items
                    ],
                }
                for layout in self._effective_sheets()
            ],
        }

    def _manual_faca_to_json(self) -> dict:
        """Facas manuais (Pontos) em formato serializável (listas de pontos)."""
        out: dict = {}
        for path, m in self._faca_manual.items():
            out[path] = {
                "contours": [
                    [[float(p.x), float(p.y)] for p in c.points]
                    for c in m["contours"]
                ],
                "w": float(m["w"]),
                "h": float(m["h"]),
                "rotation": int(m.get("rotation", 0)),
            }
        return out

    @staticmethod
    def _manual_faca_from_json(data: dict) -> dict:
        """Reconstrói as facas manuais do JSON; entrada corrompida é ignorada
        item a item (nunca impede a abertura do projeto)."""
        out: dict = {}
        for path, m in (data or {}).items():
            try:
                contours = [
                    CutContour([Point2D(float(x), float(y)) for x, y in c])
                    for c in m["contours"]
                ]
                out[path] = {
                    "contours": contours,
                    "w": float(m["w"]),
                    "h": float(m["h"]),
                    "rotation": int(m.get("rotation", 0)),
                }
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def _apply_project(self, doc: ProjectDocument) -> None:
        """Restaura o estado do projeto SEM gerar produção (regra do projeto)."""
        for key, value in doc.settings.items():
            if key in PROJECT_SETTING_KEYS and hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self._load_settings()  # empurra os parametros para os widgets
        self._reset_project_state()
        # ajustes POR ARQUIVO e facas manuais voltam com o projeto (antes se
        # perdiam ao reabrir — varredura 09/07); antes de popular, para a
        # próxima geração já usar os valores certos
        self._file_overrides = {
            p: dict(ov) for p, ov in doc.file_overrides.items()
        }
        self._faca_manual = self._manual_faca_from_json(doc.faca_manual)
        self._populate_files(doc.files)
        # QA A0: giro por peça volta JÁ na abertura (dono único continua sendo
        # _piece_rotations — o relayout aplica via _faca_for); o arranjo das
        # chapas fica PENDENTE e é consumido na primeira geração (abrir não
        # gera sozinho — regra do projeto).
        giros = (doc.arranjo or {}).get("giros") or {}
        self._piece_rotations = {
            str(art_id): int(rot) % 360
            for art_id, rot in giros.items()
            if isinstance(rot, (int, float)) and int(rot) % 360
        }
        self._pending_arranjo = doc.arranjo if (doc.arranjo or {}).get("chapas") else None
        # LIMPO só DEPOIS de repovoar: add_paths marca dirty e, sem isto, abrir
        # um projeto intocado já disparava o modal "alterações não salvas"
        # em Novo/Abrir/Fechar (varredura 09/07 — pior com o auto-reabrir)
        self._dirty = False

    def _reset_project_state(self) -> None:
        """Descarta a produção carregada (mantem parametros e widgets)."""
        self._loaded = False
        self._pending_arranjo = None  # arranjo salvo pendente morre junto
        self._result = None
        self._base_artworks = []
        self._sources = {}
        self._pixmaps = {}
        self._clear_scene(notify=True)
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
            if pfile.pages:
                self._file_pages[pfile.path] = list(pfile.pages)
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
            # QA A1b: _relayout() só recalcula a geometria dos artworks JÁ
            # importados — a chapa mostrava o nome novo mas cortava a arte
            # ANTIGA. Regenera a produção para importar o arquivo escolhido.
            self.generate(blocking=True, faca=self._faca_on)

    # ---- protecao contra perda de trabalho (QA 2.0/C5) ----
    def _mark_dirty(self) -> None:
        self._dirty = True

    def _confirm_discard(self, acao: str) -> bool:
        """Pergunta antes de descartar trabalho não salvo. True = prosseguir.

        Só pergunta quando ha algo a perder E a janela esta em uso real
        (suites offscreen/pytest nunca podem abrir modal — travaria o CI).
        """
        import os
        if not getattr(self, "_dirty", False):
            return True
        if not (self._paths or (self._result is not None and self._result.sheets)):
            return True
        if os.environ.get("PYTEST_CURRENT_TEST") or not self.isVisible():
            return True
        box = QMessageBox(self)
        box.setWindowTitle("PrintNest")
        box.setIcon(QMessageBox.Warning)
        box.setText("Há alterações não salvas neste trabalho.")
        box.setInformativeText(acao)
        b_save = box.addButton("Salvar", QMessageBox.AcceptRole)
        box.addButton("Descartar", QMessageBox.DestructiveRole)
        b_canc = box.addButton("Cancelar", QMessageBox.RejectRole)
        box.setDefaultButton(b_save)
        box.exec()
        if box.clickedButton() is b_canc:
            return False
        if box.clickedButton() is b_save:
            return self.save_project()
        return True

    def new_project(self) -> None:
        if not self._confirm_discard("Criar um novo projeto substitui o trabalho atual."):
            return
        self._dirty = False
        self._project_path = None
        self._reset_project_state()
        self._faca_on = False      # volta ao modo "soltar sem faca"
        self._file_overrides = {}  # descarta facas personalizadas por arquivo
        self._faca_manual = {}     # descarta facas editadas a mao (Pontos)
        self._file_sizes = {}      # descarta tamanhos personalizados por arquivo
        self._piece_rotations = {}  # descarta giros por peça
        self._page_crops = {}      # descarta recortes de página
        self._file_pages = {}      # descarta a escolha de páginas do PDF
        self._baked_crops = {}
        self._crop_cache = {}
        self._table.setRowCount(0)
        self._paths = []
        self._settings.last_project = ""
        self._store.save(self._settings)
        self._update_title()

    def open_project(self, path: str | None = None) -> bool:
        interactive = not isinstance(path, str) or not path
        if interactive and not self._confirm_discard(
            "Abrir outro projeto substitui o trabalho atual."
        ):
            return False
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
        self._dirty = False  # salvo: nada a perder
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
        self._prop_bar = bar  # referência p/ o tour de boas-vindas
        bar.setObjectName("propBar")  # estilo no QSS global (troca de tema ao vivo)
        # altura MINIMA derivada da fonte (QA 2.0/C2: 40px fixos cortavam a
        # borda dos botões, que precisam de ~38px + margens — pior em 125/150%)
        bar.setMinimumHeight(max(44, self.fontMetrics().height() * 2 + 16))
        outer = QHBoxLayout(bar)
        outer.setContentsMargins(theme.SPACE_MD, 2, theme.SPACE_MD, 2)
        self._pbar_stack = QStackedWidget()
        outer.addWidget(self._pbar_stack, 1)
        # barra Faca: aparece SO com arquivo carregado (QA 2.0 — 11 controles
        # ativos antes de existir faca era carga cognitiva pura)
        self._ct_tool = self._build_contour_tool()
        outer.addWidget(self._ct_tool)

        def _tag(text: str) -> QLabel:
            lb = QLabel(text)
            lb.setProperty("role", "accentTag")  # estilo no QSS (tema ao vivo)
            return lb

        def _sep() -> QLabel:
            lb = QLabel("·")
            lb.setProperty("role", "dot")
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
            # mínimo derivado da fonte: "20000.00 mm" precisa caber em 125-200%
            sp.setMinimumWidth(self.fontMetrics().horizontalAdvance("20000.00 mm") + 34)
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
        # Alinhar/Distribuir/Agrupar SAIRAM daqui (continuam na ribbon, no menu
        # Organizar e nos atalhos T/B/L/R/C/E) — a barra prioriza as funções de
        # FACA (pedido do beta), montadas em _build_contour_tool.
        self._pb_grp_count = QLabel("—")
        self._pb_grp_size = QLabel("—")
        gl.addWidget(_tag("▦ Grupo"))
        gl.addWidget(_sep())
        gl.addWidget(self._pb_grp_count)
        gl.addWidget(_sep())
        gl.addWidget(self._pb_grp_size)
        gl.addStretch()
        self._pbar_stack.addWidget(grp)

        return bar

    def _build_contour_tool(self) -> QWidget:
        """Barra Faca (fixa à direita da propBar), RESPONSIVA por projeto:

        - Inline ficam só os PRIMÁRIOS (Gerar Faca, Tipo, Offset + direção):
          ~520px lógicos, cabe de notebook 1366px a 4K em qualquer escala.
        - O resto (cantos, raio, suavizar, nós, grade, ajustar chapa) mora no
          popup "Ajustes ▾" — QA 2.0/C1: os 18 widgets numa linha somavam
          ~1500px e estouravam telas comuns. Também reduz a carga cognitiva.
        - Nenhuma largura/altura fixa em px para conteúdo que depende da
          fonte (QA 2.0 causa raiz nº 1): mínimos derivam de fontMetrics.
        """
        fm = self.fontMetrics()
        w = QFrame()
        cl = QHBoxLayout(w)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(theme.SPACE_XS)
        # a etiqueta mostra o ESCOPO (estilo Corel): sem seleção = documento
        # inteiro; com peça selecionada = só o arquivo dela (override).
        self._ct_tag = QLabel("✂ Faca · documento")
        self._ct_tag.setProperty("role", "accentTag")
        self._ct_tag.setToolTip(
            "Sem seleção: os ajustes valem para o documento inteiro.\n"
            "Com uma peça selecionada: o Tipo de faca vale SÓ para o\n"
            "arquivo dela (os demais arquivos não mudam)."
        )
        cl.addWidget(self._ct_tag)

        # botão principal AZUL: gerar a faca (o atalho Shift+F5 vive na QAction)
        gerar = QPushButton("  Gerar Faca")
        gerar.setIcon(icons.icon("scissors", theme.ICON_ON_ACCENT))
        gerar.setProperty("accent", "true")
        gerar.setToolTip("Gera/recria a faca das peças (Shift+F5)")
        gerar.clicked.connect(self._regenerate_faca)
        cl.addWidget(gerar)

        # Tipo de faca (dropdown) — espelho do controle do Documento
        self._ct_mode = QComboBox()
        self._fill_faca_combo(self._ct_mode)
        self._ct_mode.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._ct_mode.setToolTip("Tipo de faca (vale para o documento inteiro).")
        self._ct_mode.currentIndexChanged.connect(lambda _: self._apply_contour_mode())
        cl.addWidget(self._ct_mode)

        # Sensibilidade do recorte (imagens) — slider ARRASTÁVEL ao lado do tipo
        # de faca (pedido do teste 27/07): o cliente ajusta quando o recorte
        # automático "come" o desenho (diminui) ou sobra fundo (aumenta).
        # Re-detecta a faca ao SOLTAR (imagens são detectadas na importação).
        self._ct_sensitivity = QSlider(Qt.Horizontal)
        self._ct_sensitivity.setRange(0, 100)
        self._ct_sensitivity.setFixedWidth(96)
        self._ct_sensitivity.setToolTip(
            "Sensibilidade do recorte automático de IMAGENS.\n"
            "Recorte 'comendo' o desenho? DIMINUA. Sobrou fundo? AUMENTE.\n"
            "Ao soltar, a faca é recalculada."
        )
        self._ct_sens_val = QLabel("50")
        self._ct_sens_val.setMinimumWidth(fm.horizontalAdvance("100"))
        self._ct_sensitivity.valueChanged.connect(
            lambda v: self._ct_sens_val.setText(str(v))
        )
        self._ct_sensitivity.sliderReleased.connect(self._apply_contour_sensitivity)
        cl.addWidget(QLabel("Sensib."))
        cl.addWidget(self._ct_sensitivity)
        cl.addWidget(self._ct_sens_val)

        # negativo = corte PARA DENTRO (recuo/vinco); positivo = sangria (fora).
        self._ct_offset = LengthSpin(-100, 100)
        # largura MINIMA derivada da fonte (nunca fixa): "-100.00 mm" + setas
        self._ct_offset.setMinimumWidth(fm.horizontalAdvance("-100.00 mm") + 34)
        self._ct_offset.setToolTip(
            "Sangria da faca (offset): distância da linha de corte até a arte.\n"
            "Positivo = para FORA (sangria). Negativo = para DENTRO (recuo/vinco)."
        )
        self._ct_offset.editingFinished.connect(self._apply_contour_offset)
        cl.addWidget(QLabel("Sangria"))
        cl.addWidget(self._ct_offset)

        # botões só-icone com dimensão derivada da fonte (escala 125-200% ok)
        btn_h = max(28, fm.height() + 12)
        btn_w = max(30, fm.height() + 14)

        def _icon_btn(icon_name: str, tip: str, checked: bool = False) -> QPushButton:
            """Botão só-icone (estilo Corel): nome no tooltip, sem texto."""
            b = QPushButton()
            b.setIcon(icons.icon(icon_name, theme.ICON))
            b.setIconSize(QSize(18, 18))
            b.setCheckable(True)
            b.setChecked(checked)
            b.setFixedSize(btn_w, btn_h)
            b.setToolTip(tip)
            return b

        self._ct_dir = QButtonGroup(self)
        b_out = _icon_btn("arrows-out", "Contorno externo\nFaca para FORA da arte (sangria).", True)
        b_in = _icon_btn("arrows-in", "Contorno interno\nFaca para DENTRO (recuo/vinco).")
        # ilustração no lugar das setas: arte cinza + faca tracejada fora/dentro
        b_out.setIcon(faca_icons.offset_icon("out"))
        b_in.setIcon(faca_icons.offset_icon("in"))
        b_out.setIconSize(QSize(20, 20))
        b_in.setIconSize(QSize(20, 20))
        self._ct_dir.addButton(b_out, 1)   # externo (id 1; evita -1, sentinela do Qt)
        self._ct_dir.addButton(b_in, 2)    # interno
        self._ct_dir.buttonClicked.connect(self._on_ct_dir_clicked)
        cl.addWidget(b_out)
        cl.addWidget(b_in)

        # Suavizar SEMPRE visível ao lado do Offset (pedido do beta 09/07 —
        # é ajuste de uso constante, não podia morar escondido no popup)
        self._ct_smooth = _spin(0, 5)
        self._ct_smooth.setMinimumWidth(fm.horizontalAdvance("55") + 40)
        self._ct_smooth.setToolTip("Suavizar curvas da faca: 0 = reto, 5 = macio.")
        self._ct_smooth.valueChanged.connect(lambda _: self._apply_contour_smooth())
        cl.addWidget(QLabel("Suavizar"))
        cl.addWidget(self._ct_smooth)

        # ---- popup "Ajustes ▾": secundários organizados em grade ----
        panel = QWidget()
        grid = QGridLayout(panel)
        grid.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM, theme.SPACE_MD, theme.SPACE_SM)
        grid.setHorizontalSpacing(theme.SPACE_SM)
        grid.setVerticalSpacing(theme.SPACE_SM)

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
        corner_row = QHBoxLayout()
        corner_row.setSpacing(theme.SPACE_XS)
        for i, (val, icon_name, tip) in enumerate(corners):
            b = _icon_btn(icon_name, tip, checked=(val == "round"))
            self._ct_corner.addButton(b, i)
            self._ct_corner_val[i] = val
            corner_row.addWidget(b)
        corner_row.addStretch()
        self._ct_corner.buttonClicked.connect(lambda _: self._apply_contour_corner())
        grid.addWidget(QLabel("Cantos"), 0, 0)
        grid.addLayout(corner_row, 0, 1)

        # raio de arredondamento dos cantos (fillet, estilo Corel) — GLOBAL;
        # o card "Faca deste arquivo" pode sobrepor por arquivo
        self._ct_radius = LengthSpin(0, 50)
        self._ct_radius.setMinimumWidth(fm.horizontalAdvance("50.00 mm") + 34)
        self._ct_radius.setToolTip(
            "Cantos arredondados — raio (mm). Arredonda os cantos da faca,\n"
            "até em faca retangular. 0 = canto vivo."
        )
        self._ct_radius.editingFinished.connect(self._apply_contour_radius)
        # ilustração ao lado do campo: canto vivo virando arredondado
        self._ct_radius_icon = QLabel()
        self._ct_radius_icon.setPixmap(faca_icons.corner_radius_pixmap())
        self._ct_radius_icon.setToolTip(self._ct_radius.toolTip())
        radius_row = QHBoxLayout()
        radius_row.setSpacing(theme.SPACE_XS)
        radius_row.addWidget(self._ct_radius_icon)
        radius_row.addWidget(self._ct_radius)
        grid.addWidget(QLabel("Raio dos cantos"), 1, 0)
        grid.addLayout(radius_row, 1, 1)

        # Nós da faca (dropdown curto) — espelho do seletor do Acabamento
        self._ct_nodes = QComboBox()
        self._ct_nodes.addItem("Fino (máximo detalhe)", "fino")
        self._ct_nodes.addItem("Médio (recomendado)", "medio")
        self._ct_nodes.addItem("Leve (corte fluido)", "leve")
        self._ct_nodes.setCurrentIndex(1)
        self._ct_nodes.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._ct_nodes.setToolTip(
            "Quantidade de nós da faca enviados à máquina de corte."
        )
        self._ct_nodes.currentIndexChanged.connect(lambda _: self._apply_contour_nodes())
        grid.addWidget(QLabel("Nós da faca"), 3, 0)
        grid.addWidget(self._ct_nodes, 3, 1)

        # Corte por peça ou grade compartilhada (dropdown) — espelho
        self._ct_shared = QComboBox()
        self._ct_shared.addItem("Corte por peça", "piece")
        self._ct_shared.addItem("Grade (fora a fora)", "grid")
        self._ct_shared.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self._ct_shared.setToolTip(
            "Faca por peça (cada uma com o próprio corte; rentes se fundem\n"
            "sozinhas) ou faca compartilhada em grade fora a fora."
        )
        self._ct_shared.currentIndexChanged.connect(lambda _: self._apply_contour_shared())
        grid.addWidget(QLabel("Modo do corte"), 4, 0)
        grid.addWidget(self._ct_shared, 4, 1)

        # ajustar a chapa ao conteúdo (mesma ação do menu Organizar / Ctrl+Shift+F)
        fit_btn = QPushButton("  Ajustar chapa ao conteúdo")
        fit_btn.setIcon(icons.icon("arrows-in", theme.ICON))
        fit_btn.setToolTip(
            "Ajustar chapa ao conteúdo (Ctrl+Shift+F): encolhe a chapa para o\n"
            "tamanho exato do arranjo — exportação sem branco em volta."
        )
        fit_btn.clicked.connect(self._fit_sheets_to_content)
        grid.addWidget(fit_btn, 5, 0, 1, 2)

        ajustes = QToolButton()
        ajustes.setText("Ajustes ▾")
        ajustes.setToolButtonStyle(Qt.ToolButtonTextOnly)
        ajustes.setPopupMode(QToolButton.InstantPopup)
        ajustes.setCursor(Qt.PointingHandCursor)
        ajustes.setToolTip("Acabamento da faca: cantos, raio, suavizar, nós, modo do corte")
        menu = QMenu(ajustes)
        wa = QWidgetAction(menu)
        wa.setDefaultWidget(panel)
        menu.addAction(wa)
        ajustes.setMenu(menu)
        cl.addWidget(ajustes)
        return w

    def _apply_contour_sensitivity(self) -> None:
        """Slider de sensibilidade (barra Faca), ao SOLTAR: grava o valor global
        e RE-DETECTA a faca. Sensibilidade vale na detecção (importação), então
        precisa reimportar → generate (não basta relayout)."""
        if self._ct_loading:
            return
        self._auto_sensitivity.blockSignals(True)
        self._auto_sensitivity.setValue(int(self._ct_sensitivity.value()))
        self._auto_sensitivity.blockSignals(False)
        if self._loaded and self._paths:
            self._faca_on = True
            with _wait_cursor():
                self.generate(blocking=True, faca=True)

    def _apply_contour_smooth(self) -> None:
        """Suavizar (barra), sensível ao ESCOPO: arquivo selecionado ou global."""
        if self._ct_loading:
            return
        if getattr(self, "_selected_path", None):
            self._piece_override({"smooth": int(self._ct_smooth.value())})
            return
        self._auto_smooth.blockSignals(True)
        self._auto_smooth.setValue(int(self._ct_smooth.value()))
        self._auto_smooth.blockSignals(False)
        if self._loaded:
            self._relayout(renest=False)

    def _piece_override(self, updates: dict) -> None:
        """Grava ajustes NO ARQUIVO selecionado (override) e re-gera.

        BUG do beta (09/07): arquivo com override congelava os valores da
        criação — mudar Offset na barra alterava só o global, que o override
        ignora, e 'a borda parava de aumentar'. Com seleção, a barra edita o
        override; sem seleção, o global (escopo igual ao Tipo de faca).
        O override é ESPARSO: só as chaves editadas; o resto segue o global."""
        path = self._selected_path
        atual = self._params_for(path)
        if all(atual.get(k) == v for k, v in updates.items()):
            return
        ov = dict(self._file_overrides.get(path, {}))
        ov.update(updates)
        self._file_overrides[path] = ov
        self._keep_tab = True
        try:
            self._relayout(renest=False)
            self._reselect_path(path)
        finally:
            self._keep_tab = False

    def _on_ct_dir_clicked(self, btn) -> None:
        """Botões fora/dentro da barra Faca: definem o SINAL da sangria (fora =
        positivo, dentro = negativo). Equivale a digitar o negativo no campo."""
        want_out = self._ct_dir.id(btn) == 1
        cur = abs(float(self._ct_offset.value()))
        self._ct_offset.setValue(cur if want_out else -cur)
        self._apply_contour_offset()

    def _apply_contour_offset(self) -> None:
        """Offset (barra), sensível ao ESCOPO: arquivo selecionado ou global."""
        if self._ct_loading:
            return
        val = float(self._ct_offset.value())  # o campo já carrega o sinal
        # espelha o sinal nos botões de direção (fora = +, dentro = −)
        btn = self._ct_dir.button(1 if val >= 0 else 2)
        if btn is not None:
            btn.setChecked(True)
        if getattr(self, "_selected_path", None):
            self._piece_override({"offset": val, "auto_offset": val})
            return
        self._offset.blockSignals(True)
        self._auto_offset.blockSignals(True)
        self._offset.setValue(val)
        self._auto_offset.setValue(val)
        self._offset.blockSignals(False)
        self._auto_offset.blockSignals(False)
        if self._loaded:
            self._relayout(renest=False)

    def _apply_contour_corner(self) -> None:
        """Estilo do canto (barra), sensível ao ESCOPO como os demais."""
        val = self._ct_corner_val.get(self._ct_corner.checkedId(), "round")
        if self._ct_loading:
            return
        if getattr(self, "_selected_path", None):
            self._piece_override({"corner": val})
            return
        self._faca_corner = val
        if self._loaded:
            self._relayout(renest=False)

    def _apply_contour_mode(self) -> None:
        """Tipo de faca (barra), sensível ao CONTEXTO (estilo Corel):

        - COM peça selecionada: muda o tipo SÓ do arquivo dela (override) —
          misturar corte reto com contorno justo na mesma chapa deixava o
          global atropelar os outros arquivos (pedido do Philipe 08/07).
        - SEM seleção: vale para o documento (combo global re-gera).
        """
        if self._ct_loading:
            return
        data = self._ct_mode.currentData()
        if getattr(self, "_selected_path", None):
            # QAX-02: usar o override ESPARSO (só a chave "mode") — a cópia
            # completa congelava recorte/giro/offset globais no arquivo
            self._piece_override({"mode": data})
            return
        idx = self._faca_mode.findData(data)
        if idx >= 0 and idx != self._faca_mode.currentIndex():
            self._faca_mode.setCurrentIndex(idx)

    def _apply_contour_nodes(self) -> None:
        """Nós da faca (barra) -> seletor do Acabamento (handler re-gera)."""
        if self._ct_loading:
            return
        idx = self._faca_nodes.findData(self._ct_nodes.currentData())
        if idx >= 0 and idx != self._faca_nodes.currentIndex():
            self._faca_nodes.setCurrentIndex(idx)

    def _apply_contour_shared(self) -> None:
        """Por peça/grade (barra) -> combo do Documento (handler re-gera)."""
        if self._ct_loading:
            return
        if self._shared.currentIndex() != self._ct_shared.currentIndex():
            self._shared.setCurrentIndex(self._ct_shared.currentIndex())

    def _apply_contour_radius(self) -> None:
        """Raio dos cantos (barra), sensível ao ESCOPO."""
        if self._ct_loading:
            return
        if getattr(self, "_selected_path", None):
            self._piece_override({"corner_radius": float(self._ct_radius.value())})
            return
        if self._loaded:
            self._relayout(renest=False)

    def _sync_contour_tool(self) -> None:
        """Reflete a sangria/cantos atuais na toolbar (ex.: ao abrir projeto)."""
        if not hasattr(self, "_ct_offset"):
            return
        self._ct_loading = True
        try:
            # valores exibidos seguem o ESCOPO: arquivo selecionado (efetivo,
            # com override) ou o global do documento
            sel = getattr(self, "_selected_path", None)
            if sel:
                p = self._params_for(sel)
                signed = float(p.get("auto_offset") or p.get("offset") or 0.0)
                smooth_val = int(p.get("smooth", self._auto_smooth.value()))
                radius_val = float(p.get("corner_radius", self._ct_radius.value()))
            else:
                signed = float(self._offset.value())
                smooth_val = int(self._auto_smooth.value())
                radius_val = float(self._ct_radius.value())
            self._ct_offset.setValue(signed)  # campo carrega o sinal (±)
            btn = self._ct_dir.button(1 if signed >= 0 else 2)
            if btn is not None:
                btn.setChecked(True)
            self._ct_radius.setValue(radius_val)
            for i, val in self._ct_corner_val.items():
                if val == self._faca_corner:
                    b = self._ct_corner.button(i)
                    if b is not None:
                        b.setChecked(True)
            self._ct_smooth.setValue(smooth_val)
            # sensibilidade é global (vale para a detecção de imagens)
            self._ct_sensitivity.setValue(int(self._auto_sensitivity.value()))
            # tipo exibido segue o ESCOPO: arquivo selecionado (efetivo, com
            # override) ou o global do documento
            sel = getattr(self, "_selected_path", None)
            mode_data = (
                self._params_for(sel).get("mode", self._faca_mode.currentData())
                if sel else self._faca_mode.currentData()
            )
            if hasattr(self, "_ct_tag"):
                if sel and sel in self._faca_manual:
                    # faca editada a mão vence os ajustes — avisa em vez de
                    # deixar o usuário girar controles sem efeito (varredura)
                    self._ct_tag.setText("✂ Faca · manual (Pontos)")
                else:
                    self._ct_tag.setText(
                        "✂ Faca · este arquivo" if sel else "✂ Faca · documento"
                    )
            i_mode = self._ct_mode.findData(mode_data)
            if i_mode >= 0:
                self._ct_mode.setCurrentIndex(i_mode)
            i_nodes = self._ct_nodes.findData(self._faca_nodes.currentData())
            if i_nodes >= 0:
                self._ct_nodes.setCurrentIndex(i_nodes)
            self._ct_shared.setCurrentIndex(self._shared.currentIndex())
        finally:
            self._ct_loading = False

    def _update_property_bar(self) -> None:
        """Repinta a barra conforme a seleção atual (Projeto / Objeto / Grupo)."""
        if not hasattr(self, "_pbar_stack"):
            return
        # barra Faca só com arquivo carregado (revelação progressiva)
        if hasattr(self, "_ct_tool"):
            self._ct_tool.setVisible(bool(self._paths))
        # texto-guia do canvas vazio, conforme a etapa do fluxo
        if hasattr(self, "_view"):
            if not self._paths:
                hint = (
                    "Adicione arquivos (Ctrl+I) e clique em  Colocar na chapa\n"
                    "(você também pode arrastá-los para cá)"
                )
                step = 0
            elif self._result is None:
                hint = (
                    "Clique em  Colocar na chapa  — ou arraste o arquivo "
                    "da biblioteca para cá\nDepois:  Gerar Faca  (Shift+F5)"
                )
                step = 1
            else:
                hint = ""
                step = 2
            if self._view.empty_hint != hint or self._view.empty_step != step:
                self._view.empty_hint = hint
                self._view.empty_step = step
                self._view.viewport().update()
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
        # com a ferramenta Pontos ativa, as alças de nó assumem (menos poluição)
        if len(pieces) != 1 or self._nodes_tool_on:
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

    # ---- ferramenta Pontos (F10): editar nós da faca, estilo CorelDRAW ----
    def _set_nodes_tool(self, on: bool) -> None:
        """Liga/desliga a ferramenta Pontos (edição de nós da linha de corte)."""
        self._nodes_tool_on = bool(on)
        self._update_resize_handles()
        self._update_node_handles()
        if on:
            self._toasts.info(
                "Pontos: arraste um nó para mover; duplo clique no traço "
                "adiciona; duplo clique num nó remove."
            )

    def _update_node_handles(self) -> None:
        """Mostra as alças de nó da faca na peça selecionada (Pontos ativa)."""
        for h in self._node_handles:
            with contextlib.suppress(RuntimeError, ValueError):
                h.setParentItem(None)
                self._scene.removeItem(h)
        self._node_handles = []
        if not self._nodes_tool_on or self._result is None:
            return
        pieces = self._selected_pieces()
        if len(pieces) != 1:
            return
        piece = pieces[0]
        art = next(
            (a for a in self._result.artworks if a.id == piece.artwork_id), None
        )
        if art is None or not art.has_cut:
            return
        fp = artwork_footprint(art)
        ax, ay = -fp.min_x, -fp.min_y
        for ci, contour in enumerate((art.cut_contour, *art.extra_cuts)):
            for pi, pt in enumerate(contour.points):
                handle = _NodeHandle(self, piece, ci, pi)
                handle.setParentItem(piece)
                handle.setPos(ax + pt.x, ay + pt.y)
                self._node_handles.append(handle)

    def _piece_contours_points(self, piece):
        """(art, ax, ay, contornos como listas de Point2D) da peça, ou None."""
        if self._result is None:
            return None
        art = next(
            (a for a in self._result.artworks if a.id == piece.artwork_id), None
        )
        if art is None or not art.has_cut:
            return None
        fp = artwork_footprint(art)
        contours = [list(c.points) for c in (art.cut_contour, *art.extra_cuts)]
        return art, -fp.min_x, -fp.min_y, contours

    def _end_node_drag(self, piece) -> None:
        """Solta um nó: reconstroi os contornos a partir das alças e salva."""
        got = self._piece_contours_points(piece)
        if got is None:
            return
        _art, ax, ay, contours = got
        for h in self._node_handles:
            pos = h.pos()
            with contextlib.suppress(IndexError):
                contours[h.ci][h.pi] = Point2D(pos.x() - ax, pos.y() - ay)
        self._commit_manual_faca(piece, contours, "mover nó")

    def _remove_node(self, piece, ci: int, pi: int) -> None:
        """Duplo clique numa alça: remove o nó (mantendo o mínimo de 3)."""
        got = self._piece_contours_points(piece)
        if got is None:
            return
        _art, _ax, _ay, contours = got
        if ci >= len(contours) or len(contours[ci]) <= 3:
            self._toasts.info("O contorno precisa de pelo menos 3 nós.")
            return
        del contours[ci][pi]
        self._commit_manual_faca(piece, contours, "remover nó")

    def _on_canvas_double_click(self, scene_pos) -> None:
        """Duplo clique no canvas com Pontos ativa: adiciona nó no traço."""
        if not self._nodes_tool_on or self._result is None:
            return
        # se caiu numa alça, a própria alça tratou (remover) — não adiciona
        for it in self._scene.items(scene_pos):
            if isinstance(it, _NodeHandle):
                return
        pieces = self._selected_pieces()
        if len(pieces) != 1:
            return
        piece = pieces[0]
        got = self._piece_contours_points(piece)
        if got is None:
            return
        _art, ax, ay, contours = got
        local = piece.mapFromScene(scene_pos)
        px, py = local.x() - ax, local.y() - ay
        best = None  # (dist, ci, indice do segmento, ponto projetado)
        for ci, pts in enumerate(contours):
            n = len(pts)
            for i in range(n):
                a, b = pts[i], pts[(i + 1) % n]
                d, proj = self._dist_point_segment(px, py, a, b)
                if best is None or d < best[0]:
                    best = (d, ci, i, proj)
        if best is None:
            return
        # só adiciona se o clique foi PERTO do traço (~12px na tela, em mm)
        threshold = 12.0 / max(self._view.zoom_factor(), 1e-6)
        if best[0] > threshold:
            return
        _d, ci, i, proj = best
        contours[ci].insert(i + 1, Point2D(proj[0], proj[1]))
        self._commit_manual_faca(piece, contours, "adicionar nó")

    @staticmethod
    def _dist_point_segment(px, py, a, b):
        """Distância do ponto (px,py) ao segmento a-b e o ponto projetado."""
        ax_, ay_, bx, by = a.x, a.y, b.x, b.y
        dx, dy = bx - ax_, by - ay_
        length2 = dx * dx + dy * dy
        if length2 <= 1e-12:
            return ((px - ax_) ** 2 + (py - ay_) ** 2) ** 0.5, (ax_, ay_)
        t = max(0.0, min(1.0, ((px - ax_) * dx + (py - ay_) * dy) / length2))
        qx, qy = ax_ + t * dx, ay_ + t * dy
        return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5, (qx, qy)

    def _commit_manual_faca(self, piece, contours_pts, text="editar nós") -> None:
        """Salva a faca editada como faca MANUAL do ARQUIVO (com desfazer).

        Todas as cópias do arquivo herdam a correção — o fluxo recomendado é
        arrumar a faca e SÓ DEPOIS duplicar para o nesting. A partir daqui os
        ajustes automáticos (sangria/suavizar/modo) não mudam este arquivo,
        até 'Voltar à faca automática'."""
        art = next(
            (a for a in self._result.artworks if a.id == piece.artwork_id), None
        )
        if art is None:
            return
        valid = [pts for pts in contours_pts if len(pts) >= 3]
        if not valid:
            return
        path = self._path_of(piece.artwork_id)
        rotation = int(self._art_params(piece.artwork_id).get("rotation", 0))
        before = self._state_snapshot()
        first_time = path not in self._faca_manual
        self._faca_manual[path] = {
            "contours": tuple(CutContour(pts) for pts in valid),
            "w": art.size.width,
            "h": art.size.height,
            "rotation": rotation,
        }
        self._suspend_undo = True
        try:
            self._relayout(renest=False)
        finally:
            self._suspend_undo = False
        if self._result is not None:
            after = self._state_snapshot()
            self._undo.push(SnapshotCommand(self, before, after, text))
        self._reselect_by_artwork({piece.artwork_id})
        self._update_node_handles()
        if first_time:
            self._toasts.info(
                "Faca em edição manual — sangria/suavizar não mudam este "
                "arquivo até voltar à faca automática."
            )

    def _reset_manual_faca(self) -> None:
        """Descarta a faca manual do arquivo selecionado (volta ao automático)."""
        path = self._selected_path
        if not path or path not in self._faca_manual:
            return
        before = self._state_snapshot() if self._result is not None else None
        del self._faca_manual[path]
        self._suspend_undo = True
        try:
            self._relayout(renest=False)
        finally:
            self._suspend_undo = False
        if before is not None and self._result is not None:
            after = self._state_snapshot()
            self._undo.push(SnapshotCommand(self, before, after, "faca automática"))
        self._reselect_path(path)
        self._update_node_handles()
        self._toasts.success("Faca voltou ao automático.")

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

    def _fill_faca_combo(self, combo: QComboBox) -> None:
        """Popula um combo de Tipo de faca com miniatura ilustrativa por item
        (arte cinza + linha de faca tracejada) e dica ao pairar em cada opção."""
        combo.setIconSize(QSize(26, 26))
        for i, (label, data) in enumerate(self._FACA_MODES):
            combo.addItem(faca_icons.mode_icon(data), label, data)
            combo.setItemData(i, faca_icons.MODE_HINTS.get(data, ""), Qt.ToolTipRole)

    @staticmethod
    def _illustrate_combo(combo: QComboBox, icon_fn, hints: dict | None = None) -> None:
        """Aplica miniatura ilustrativa (e dica por item) a um combo já
        populado, usando o itemData de cada opção como chave do desenho."""
        combo.setIconSize(QSize(26, 26))
        for i in range(combo.count()):
            combo.setItemIcon(i, icon_fn(combo.itemData(i)))
            if hints is not None:
                combo.setItemData(i, hints.get(combo.itemData(i), ""), Qt.ToolTipRole)

    # combos ilustrados além do Tipo de faca: (atributo, desenho, dicas) —
    # usado na criação e no redesenho quando o tema troca.
    _ILLUSTRATED_COMBOS = (
        ("_ct_nodes", "nodes_icon", "NODE_HINTS"),
        ("_faca_nodes", "nodes_icon", "NODE_HINTS"),
        ("_ct_shared", "shared_icon", "SHARED_HINTS"),
        ("_reg_type", "regmark_icon", "REG_HINTS"),
        ("_import_box", "import_box_icon", "BOX_HINTS"),
        ("_view_mode", "view_mode_icon", "VIEW_HINTS"),
    )

    def _illustrate_all(self) -> None:
        """(Re)desenha TODAS as miniaturas ilustrativas da janela. Chamado ao
        montar a UI e quando o tema troca (as cores entram nos desenhos)."""
        self._refresh_cartela_illustrations()  # passos da aba Cartelas
        for name in ("_ct_mode", "_faca_mode", "_pf_mode"):
            combo = getattr(self, name, None)
            if combo is not None:
                for i in range(combo.count()):
                    combo.setItemIcon(i, faca_icons.mode_icon(combo.itemData(i)))
        for name, fn_name, hints_name in self._ILLUSTRATED_COMBOS:
            combo = getattr(self, name, None)
            if combo is not None:
                self._illustrate_combo(
                    combo,
                    getattr(faca_icons, fn_name),
                    getattr(faca_icons, hints_name),
                )
        if hasattr(self, "_ct_dir"):  # sangria para fora / para dentro
            for bid, direction in ((1, "out"), (2, "in")):
                b = self._ct_dir.button(bid)
                if b is not None:
                    b.setIcon(faca_icons.offset_icon(direction))
        if hasattr(self, "_ct_radius_icon"):  # canto vivo -> arredondado
            self._ct_radius_icon.setPixmap(faca_icons.corner_radius_pixmap())

    _SESSION_WIDGETS = (
        ("_width", "spin"), ("_height", "spin"), ("_spacing", "spin"),
        ("_spacing_v", "spin"), ("_offset", "spin"), ("_crop", "spin"),
        ("_faca_mode", "combo"), ("_faca_nodes", "combo"),
        ("_rotation", "combo"), ("_shared", "combo"),
        ("_auto_sensitivity", "spin"), ("_auto_smooth", "spin"),
        ("_ct_radius", "spin"),  # raio dos cantos (barra Faca) e por sessão
        ("_auto_offset", "spin"), ("_auto_ignore_white", "check"),
        ("_reg_type", "combo"), ("_reg_margin", "spin"), ("_reg_diameter", "spin"),
        ("_reg_thickness", "spin"),
        ("_mk_distance", "spin"), ("_mk_size", "spin"), ("_mk_thickness", "spin"),
        ("_import_box", "combo"), ("_view_mode", "combo"), ("_center_check", "check"),
        ("_cart_on", "check"), ("_cart_w", "spin"), ("_cart_h", "spin"),
        ("_cart_gap", "spin"), ("_cart_margin", "spin"),
        ("_cart_identical", "check"),
        ("_cart_reg_mimaki", "check"), ("_cart_reg_iecho", "check"),
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
        plus.setObjectName("tabPlus")  # estilo no QSS global (tema ao vivo)
        plus.setToolTip("Novo trabalho (aba)")
        plus.setFixedSize(34, 38)
        plus.setCursor(Qt.PointingHandCursor)
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
            "file_pages": {k: list(v) for k, v in self._file_pages.items()},
            "baked_crops": dict(self._baked_crops),
            "crop_cache": dict(self._crop_cache),
            "file_overrides": {k: dict(v) for k, v in self._file_overrides.items()},
            "faca_manual": {k: dict(v) for k, v in self._faca_manual.items()},
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
            crop_cache={}, file_overrides={}, piece_rotations={}, faca_manual={},
            faca_on=False, loaded=False, project_path=None, guides=[],
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
        # seleção não atravessa abas: um _selected_path da aba anterior faria
        # a barra Faca criar override de arquivo de OUTRO trabalho (varredura)
        self._selected_path = None
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
            self._file_pages = {
                k: list(v) for k, v in s.get("file_pages", {}).items()
            }
            self._baked_crops = dict(s["baked_crops"])
            self._crop_cache = dict(s["crop_cache"])
            self._file_overrides = {k: dict(v) for k, v in s["file_overrides"].items()}
            self._faca_manual = {k: dict(v) for k, v in s.get("faca_manual", {}).items()}
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
            self._clear_scene(notify=True)
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
        # QA 2.0/C5: fechar aba descartava o trabalho SEM aviso e sem volta
        if index == self._active_tab:
            if not self._confirm_discard(
                "Fechar esta aba descarta o trabalho não salvo dela."
            ):
                return
        elif self._sessions[index] is not None:
            import os
            if not os.environ.get("PYTEST_CURRENT_TEST") and self.isVisible():
                r = QMessageBox.question(
                    self, "Fechar aba",
                    "Esta aba tem um trabalho aberto. Fechar e descartar?",
                )
                if r != QMessageBox.Yes:
                    return
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
        self._view.files_dropped.connect(self.add_paths)
        self._view.double_clicked.connect(self._on_canvas_double_click)
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._canvas_menu)

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
        self._view_mode.addItem("Tela dividida (lado a lado)", "split_h")
        self._view_mode.currentIndexChanged.connect(lambda _: self._refresh_preview())
        self._display_bar.adjustSize()
        self._display_bar.move(12, 12)
        self._display_bar.show()
        # mantem a barrinha SEMPRE por cima e visivel (o QGraphicsView pode
        # deixa-la atras do canvas ao rolar/zoom -> "some"). Igual a caixa de
        # medidas, que se re-eleva a cada atualizacao.
        self._view.view_changed.connect(self._keep_display_bar)

        # demais controles de Exibição (réguas, snap) no popup do botão da barra
        self._display_panel = self._build_display_controls()

        for ruler in (self._h_ruler, self._v_ruler):
            ruler.guide_preview.connect(self._on_guide_preview)
            ruler.guide_dropped.connect(self._on_guide_dropped)
        return work

    def _keep_display_bar(self) -> None:
        """Garante a barrinha de exibição visivel e no topo (anti-'sumiu')."""
        bar = getattr(self, "_display_bar", None)
        if bar is None:
            return
        parent = bar.parent()
        if parent is not None:  # nao deixa escapar da area visivel apos resize
            x = max(0, min(bar.x(), parent.width() - bar.width()))
            y = max(0, min(bar.y(), parent.height() - bar.height()))
            bar.move(x, y)
        bar.show()
        bar.raise_()

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

        # Atalho destacado para a aba "Cartelas" (só com o fluxo ligado)
        if CARTELAS_ENABLED:
            cta = QPushButton("  Cartelas e refile  →")
            cta.setIcon(icons.icon("scissors", theme.ICON_ON_ACCENT))
            cta.setProperty("accent", "true")
            cta.setCursor(Qt.PointingHandCursor)
            cta.setToolTip(
                "Produza em cartelas: monte uma cartela, repita na chapa e\n"
                "exporte as duas facas (Mimaki de 1 cartela + refile da chapa)."
            )
            cta.clicked.connect(self._show_cartelas_tab)
            self._cartelas_cta = cta
            dl.addWidget(cta)
        # U1 passo 2 (redesign 27/07): o acordeão de 6 barras vira SUB-ABAS.
        # Os cards continuam (guardam _width/_faca_mode etc. e o Modo Compacto),
        # mas com o cabeçalho ESCONDIDO e sem borda — quem troca a seção visível
        # é o segmented control azul. Só uma seção aparece por vez.
        prod = self._build_producao_card()
        acab = self._build_acabamento_card()
        img = self._build_imagens_card()      # só estado (sub-aba removida 27/07)
        reg = self._build_registro_card()
        avan = self._build_avancado_card()    # só estado (sub-aba removida 27/07)
        sections = [("Produção", prod), ("Acabamento", acab), ("Registro", reg)]
        # Imagens e Avançado saíram das sub-abas (declutter 27/07); os widgets
        # (auto_ignore_white, reset da faca etc.) seguem vivos, só escondidos.
        for hidden in (img, avan):
            hidden.setVisible(False)
            dl.addWidget(hidden)
        # abas + conteudo num bloco SEM espaco entre eles: e o encosto que faz
        # a aba parecer aba (a folha continua a aba ativa, como num fichario).
        aba_bloco = QWidget()
        abl = QVBoxLayout(aba_bloco)
        abl.setContentsMargins(0, 0, 0, 0)
        abl.setSpacing(0)
        abl.addWidget(self._build_doc_nav(sections))
        self._doc_sections = []
        for _label, card in sections:
            card._header.setVisible(False)  # o cabeçalho virou a sub-aba
            self._doc_sections.append(card)
            abl.addWidget(card)
        self._apply_doc_tabs_theme()  # cores das abas + da folha
        dl.addWidget(aba_bloco)
        self._show_doc_section(0)  # Produção ativa
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

        # trilho de icones (estilo VS Code): as abas de texto eram cortadas
        # quando o painel ficava estreito; icone nao depende da largura.
        self._props_tabs = IconRailTabs()
        self._props_tabs.addTab(doc_scroll, "file-text", "Documento")
        self._props_tabs.addTab(self._sel_stack, "mouse-pointer", "Seleção")
        self._props_tabs.addTab(self._build_object_page(), "layers", "Objeto")
        # aba "Transformar" removida (27/07): a "Posição (duplicar)" foi para a
        # sub-aba Produção; o preview fantasma agora vale na aba Documento.
        if CARTELAS_ENABLED:
            self._props_tabs.addTab(self._build_cartelas_tab(), "scissors", "Cartelas")
        # ao sair da aba Transformar, some com os fantasmas
        self._props_tabs.currentChanged.connect(lambda _: self._refresh_transform_preview())

        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(theme.SPACE_XS, 0, 0, 0)
        wl.setSpacing(theme.SPACE_SM)
        wl.addWidget(self._props_tabs, 1)
        # o trilho de icones ocupa ~46px: painel um pouco mais largo para os
        # campos manterem a mesma area util de antes (280px de conteudo)
        # largura mínima maior: o resumo em blocos precisa de espaço para não
        # cortar "Chapas"/"Registro" (pedido 27/07: "tem que ficar sempre assim").
        wrap.setMinimumWidth(400)
        wrap.setMaximumWidth(452)
        return wrap

    # ==================== Aba "Transformar" (duplicação inteligente) ==========
    def _build_position_card(self) -> CollapsibleCard:
        """'Posição (duplicar)' estilo CorelDRAW: âncora de DIREÇÃO + X/Y +
        Posição relativa + Cópias + Aplicar. Mora na sub-aba Produção (movida
        da antiga aba Transformar em 27/07). As cópias viram peças reais via
        _add_placed (entram no undo, no PDF, no DXF e no .printnest)."""
        card = CollapsibleCard("Posição (duplicar)")
        cap = QLabel("Selecione peça(s) e a direção para multiplicar.")
        cap.setProperty("role", "caption")
        cap.setWordWrap(True)
        card.body.addWidget(cap)

        self._td_anchor = AnchorGrid()
        self._td_anchor.picked.connect(self._on_anchor_direction)
        self._td_x = LengthSpin(-20000, 20000)
        self._td_x.setValue(100)
        self._td_y = LengthSpin(-20000, 20000)
        self._td_y.setValue(0)
        self._td_x.setToolTip("Posição/passo no eixo X (mm).")
        self._td_y.setToolTip("Posição/passo no eixo Y (mm).")
        self._td_x.valueChanged.connect(lambda _: self._preview_duplicate())
        self._td_y.valueChanged.connect(lambda _: self._preview_duplicate())

        # âncora (esquerda, alinhada ao topo) + X/Y (direita), compacto
        pos_row = QHBoxLayout()
        pos_row.setContentsMargins(0, 0, 0, 0)
        pos_row.setSpacing(theme.SPACE_MD)
        anchor_cap = QLabel("Âncora")
        anchor_cap.setProperty("role", "caption")
        anchor_w = QWidget()
        avb = QVBoxLayout(anchor_w)
        avb.setContentsMargins(0, 0, 0, 0)
        avb.setSpacing(4)
        avb.addWidget(anchor_cap)
        avb.addWidget(self._td_anchor)
        pos_row.addWidget(anchor_w, 0, Qt.AlignTop)
        xy = QGridLayout()
        xy.setContentsMargins(0, 0, 0, 0)
        xy.setHorizontalSpacing(8)
        xy.setVerticalSpacing(8)
        xy.addWidget(QLabel("X"), 0, 0)
        xy.addWidget(self._td_x, 0, 1)
        xy.addWidget(QLabel("Y"), 1, 0)
        xy.addWidget(self._td_y, 1, 1)
        xy.setColumnStretch(1, 1)
        pos_row.addLayout(xy, 1)
        card.body.addLayout(pos_row)

        self._td_relative = QCheckBox("Posição relativa")
        self._td_relative.setChecked(True)
        self._td_relative.setToolTip(
            "Marcado: X/Y são o passo entre cópias (0, X, 2X...). Desmarcado: "
            "as cópias vão para a posição (X, Y)."
        )
        self._td_relative.toggled.connect(lambda _: self._preview_duplicate())
        card.body.addWidget(self._td_relative)
        self._td_copies = QuantityStepper(1, 1000, 1)
        self._td_copies.valueChanged.connect(lambda _: self._preview_duplicate())
        card.body.addWidget(labeled("Cópias", self._td_copies))
        btn_dup = QPushButton("  Aplicar")
        btn_dup.setIcon(icons.icon("copy-plus", theme.ICON))
        btn_dup.clicked.connect(self._apply_transform_duplicate)
        card.body.addWidget(btn_dup)

        # widgets da Grade (removida) seguem como estado: _apply_transform_grid
        self._tg_cols = _spin(1, 200)
        self._tg_cols.setValue(5)
        self._tg_rows = _spin(1, 200)
        self._tg_rows.setValue(4)
        self._tg_gap_h = LengthSpin(0, 20000)
        self._tg_gap_h.setValue(10)
        self._tg_gap_v = LengthSpin(0, 20000)
        self._tg_gap_v.setValue(10)
        return card

    def _transform_active(self) -> bool:
        """True quando a aba Documento está em foco (onde mora a Posição/duplicar)
        — para mostrar/limpar os fantasmas do preview."""
        if not hasattr(self, "_props_tabs"):
            return False
        idx = self._props_tabs.currentIndex()
        return self._props_tabs.tabText(idx) == "Documento"

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

    def _on_anchor_direction(self, col: int, row: int) -> None:
        """Grade de âncora (estilo Corel): clicar num sentido preenche X/Y com o
        TAMANHO da SELEÇÃO naquele eixo — a cópia sai ENCOSTADA no sentido
        escolhido (→ ao lado, ↓ abaixo...). O usuário ajusta X/Y para dar folga.
        Centro (1,1) não mexe nos valores.

        O passo é a caixa do conjunto, não a da primeira peça: com 3 peças
        selecionadas lado a lado, → tem que pular as 3 (senão a cópia cai em
        cima das outras duas)."""
        dirx, diry = col - 1, row - 1
        if not (dirx or diry):
            return
        sel = self._selected_pieces()
        if not sel:
            return
        # coordenadas de layout (sem o deslocamento do bloco): na tela dividida
        # a mesma peça aparece na arte e na faca com dx diferente
        x0 = min(p.scenePos().x() - p.dx for p in sel)
        x1 = max(p.scenePos().x() - p.dx + p.rect().width() for p in sel)
        y0 = min(p.scenePos().y() - p.dy for p in sel)
        y1 = max(p.scenePos().y() - p.dy + p.rect().height() for p in sel)
        self._td_x.setValue(dirx * (x1 - x0))
        self._td_y.setValue(diry * (y1 - y0))

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
        # fantasma do PRÓXIMO passo: clicando Aplicar em cadeia da pra ver onde
        # a próxima cópia cai antes de clicar
        self._refresh_transform_preview()
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
        self._fill_faca_combo(self._pf_mode)
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
        faca.body.addWidget(QLabel("Raio dos cantos (0 = vivo)"))
        self._pf_corner_radius = LengthSpin(0, 50)
        self._pf_corner_radius.setToolTip(
            "Arredonda os cantos da faca com este raio (mm), estilo Contorno do\n"
            "Corel — vale até para faca retangular. 0 = canto vivo."
        )
        self._pf_corner_radius.valueChanged.connect(
            lambda _: self._on_piece_faca_changed()
        )
        faca.body.addWidget(self._pf_corner_radius)
        self._pf_reset = QPushButton("  Usar padrão do documento")
        self._pf_reset.setIcon(icons.icon("rotate-ccw", theme.ICON))
        self._pf_reset.setToolTip(
            "Remove TODOS os ajustes de faca deste arquivo (tipo, sangria,\n"
            "suavizar, raio, recorte, giro) e volta ao padrão do Documento."
        )
        self._pf_reset.clicked.connect(self._reset_piece_faca)
        faca.body.addWidget(self._pf_reset)
        self._pf_manual_reset = QPushButton("  Voltar à faca automática")
        self._pf_manual_reset.setIcon(icons.icon("rotate-ccw", theme.ICON))
        self._pf_manual_reset.setToolTip(
            "Descarta a edição manual dos nós (ferramenta Pontos) e volta a\n"
            "calcular a faca automaticamente para este arquivo."
        )
        self._pf_manual_reset.clicked.connect(self._reset_manual_faca)
        faca.body.addWidget(self._pf_manual_reset)
        lay.addWidget(faca)

        # card "Ações" removido (U1 declutter 27/07): Duplicar/Excluir/Duplicar
        # por posição já vivem no ribbon, no menu e nos atalhos (Ctrl+D, Del,
        # Ctrl+Shift+C) e na aba Transformar — a lista lateral só repetia.
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
            ("trash-2", "Excluir da chapa", self._delete_selected),
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
        if self._clearing_scene:
            # a cena esta sendo destruida: responder agora criaria alças e
            # fantasmas dentro dela, itens que ja nascem condenados
            return
        try:
            selected = self._scene.selectedItems()
        except RuntimeError:  # cena já destruida (fechando a janela)
            return
        pieces = [it for it in selected if isinstance(it, PieceItem)]
        cur = self._props_tabs.currentIndex()
        switch = not self._keep_tab  # durante reselecao não troca de aba
        if not pieces:
            # varredura 09/07: sem limpar, a barra Faca continuava editando o
            # "arquivo fantasma" da última seleção (escopo documento quebrado)
            self._selected_path = None
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
        self._update_node_handles()    # alças de nó (ferramenta Pontos)

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
            self._pf_corner_radius.setValue(float(p.get("corner_radius", 0.0)))
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
        self._pf_manual_reset.setVisible(path in self._faca_manual)
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
        # override ESPARSO: só as chaves do card; o resto segue o global vivo
        p = dict(self._file_overrides.get(path, {}))
        sangria = float(self._pf_offset.value())
        if self._selected_is_image:
            p["auto_offset"] = sangria
        else:
            p["offset"] = sangria
        p["crop"] = float(self._pf_crop.value())
        p["rotation"] = int(self._pf_rotation.currentText())
        p["smooth"] = int(self._pf_smooth.value())
        p["corner_radius"] = float(self._pf_corner_radius.value())
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
        self._mk_distance.setToolTip("Distância do quadro até o conteudo (mm)")
        self._mk_size.setToolTip("Tamanho das marcas em L (mm)")
        self._mk_thickness.setToolTip("Espessura das marcas (mm)")
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

        # logo completa (simbolo + nome PRINTNEST PRO) no topo do painel.
        # Tem DUAS versões: a original (temas claros) e a invertida
        # printnest_dark.png (temas escuros) — trocadas em _on_theme_changed.
        self._logo_label = None
        self._logo_light = QPixmap(str(resource_path("assets/printnest.png")))
        dark_path = resource_path("assets/printnest_dark.png")
        self._logo_dark = QPixmap(str(dark_path)) if dark_path.exists() else QPixmap()
        if not self._logo_light.isNull():
            self._logo_label = QLabel()
            self._logo_label.setAlignment(Qt.AlignHCenter)
            self._logo_label.setContentsMargins(0, 2, 0, 4)
            self._refresh_logo()
            lay.addWidget(self._logo_label)

        header = QLabel("Biblioteca")
        header.setProperty("role", "cardTitle")  # QSS: acompanha o tema ao vivo
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
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setDragEnabled(True)  # arrastar arquivo para a área de trabalho
        self._table.setDragDropMode(QAbstractItemView.DragOnly)
        self._table.itemSelectionChanged.connect(self._update_selection_info)
        # duplo clique na linha = Colocar na chapa (U1: o arrastar ganhou
        # caminho visível; ambos convergem em _place_selected_on_sheet)
        self._table.itemDoubleClicked.connect(lambda _i: self._place_selected_on_sheet())
        lay.addWidget(self._table, 1)

        self._btn_place = QPushButton("  Colocar na chapa")
        self._btn_place.setIcon(icons.icon("zap", theme.ICON_ON_ACCENT))
        self._btn_place.setProperty("accent", "true")
        self._btn_place.setToolTip(
            "Coloca o(s) arquivo(s) selecionado(s) na área de trabalho —\n"
            "o mesmo que arrastar o arquivo da biblioteca para a chapa.\n"
            "Sem seleção: coloca todos. Duplo clique na linha também funciona."
        )
        self._btn_place.clicked.connect(self._place_selected_on_sheet)
        lay.addWidget(self._btn_place)

        self._btn_crop = QPushButton("  Recortar páginas ou imagem...")
        self._btn_crop.setIcon(icons.icon("replace", theme.ICON))
        self._btn_crop.setToolTip(
            "Corta as bordas do arquivo selecionado (PDF ou imagem): arraste as\n"
            "bordas na previa. No PDF, vale para todas as páginas ou as que escolher."
        )
        self._btn_crop.clicked.connect(self._crop_pages_dialog)
        lay.addWidget(self._btn_crop)

        self._btn_pages = QPushButton("  Páginas do PDF...")
        self._btn_pages.setIcon(icons.icon("file-text", theme.ICON))
        self._btn_pages.setToolTip(
            "Escolhe QUAIS páginas do PDF vão para a área de trabalho:\n"
            "uma, várias ou todas. Só vale para PDF com mais de uma página."
        )
        self._btn_pages.clicked.connect(self._pages_dialog_selected)
        lay.addWidget(self._btn_pages)

        self._btn_remove = QPushButton("  Remover da biblioteca")
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

    def _build_resumo_card(self) -> QWidget:
        """Resumo da produção em blocos (U1 redesign 27/07, aprovado): bloco
        duplo AZUL juntando Material + Área usada; demais neutros com ícone.
        Atualizado por _update_resumo (mesma interface set_value)."""
        # bloco duplo azul (Material da chapa + Área usada juntos)
        hero = QFrame()
        hero.setObjectName("statHero")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(12, 11, 12, 11)
        hl.setSpacing(2)
        htop = QHBoxLayout()
        htop.setContentsMargins(0, 0, 0, 0)
        hchip = QLabel()
        hchip.setAlignment(Qt.AlignCenter)
        hchip.setPixmap(icons.pixmap("layers", theme.ICON_ON_ACCENT, 16))
        htop.addStretch()
        htop.addWidget(hchip)
        self._sum_material = StatValue("—")
        self._sum_material.setObjectName("heroVal")
        mcap = QLabel("Material da chapa")
        mcap.setObjectName("heroCap")
        hdiv = QFrame()
        hdiv.setObjectName("heroDiv")
        hdiv.setFixedHeight(1)
        self._sum_area = StatValue("—")
        self._sum_area.setObjectName("heroVal2")
        acap = QLabel("Área usada")
        acap.setObjectName("heroCap")
        hl.addLayout(htop)
        hl.addWidget(self._sum_material)
        hl.addWidget(mcap)
        hl.addWidget(hdiv)
        hl.addWidget(self._sum_area)
        hl.addWidget(acap)
        hl.addStretch()
        self._sum_hero = hero
        self._sum_hero_chip = hchip
        self._sum_hero_div = hdiv

        # blocos neutros com ícone
        self._sum_pecas = StatTile("copy", "Peças")
        self._sum_chapas = StatTile("grid-3x3", "Chapas")
        self._sum_faca = StatTile("scissors", "Faca (mm)")
        self._sum_reg = StatTile("plus", "Registro")

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        grid.addWidget(hero, 0, 0, 2, 1)
        grid.addWidget(self._sum_pecas, 0, 1)
        grid.addWidget(self._sum_chapas, 0, 2)
        grid.addWidget(self._sum_faca, 1, 1)
        grid.addWidget(self._sum_reg, 1, 2)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 2)

        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, theme.SPACE_SM)
        bl.setSpacing(0)
        bl.addLayout(grid)
        self._apply_resumo_theme()
        return box

    def _apply_resumo_theme(self) -> None:
        """(Re)pinta o Resumo com os tokens do tema ATUAL.

        O bloco azul e os quatro neutros tinham cor chumbada (#2563eb/#4f46e5,
        #f6f8fb, #111827...): no tema escuro viravam manchas claras no meio do
        painel. Chamado na montagem e em _on_theme_changed."""
        hero = getattr(self, "_sum_hero", None)
        if hero is not None:
            # o gradiente do herói sai do acento: escurece um pouco a segunda
            # parada para manter o mesmo degradê em qualquer acento escolhido
            fim = QColor(theme.ACCENT).darker(125).name()
            self._sum_hero_chip.setPixmap(
                icons.pixmap("layers", theme.ICON_ON_ACCENT, 16)
            )
            hero.setStyleSheet(
                "#statHero{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {theme.ACCENT}, stop:1 {fim}); border-radius:15px;}}"
                f"#heroVal{{font-size:19px; font-weight:800;"
                f" color:{theme.ICON_ON_ACCENT};}}"
                f"#heroVal2{{font-size:15px; font-weight:800;"
                f" color:{theme.ICON_ON_ACCENT}; margin-top:10px;}}"
                f"#heroCap{{font-size:10px; color:{theme.ACCENT_SOFT};}}"
                f"#heroDiv{{background:{fim}; border:none; margin-top:12px;}}"
            )
        for tile in (
            getattr(self, "_sum_pecas", None), getattr(self, "_sum_chapas", None),
            getattr(self, "_sum_faca", None), getattr(self, "_sum_reg", None),
        ):
            if tile is not None:
                tile.apply_theme()

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
        # Posição (duplicar) estilo Corel — logo abaixo do espaçamento (pedido
        # 27/07: movida da aba Transformar para o início da Produção).
        card.body.addWidget(self._build_position_card())
        self._center_check = QCheckBox("Manter centralizado na chapa")
        self._center_check.setChecked(self._center_on_sheet)
        self._center_check.setToolTip(
            "Ligado: o conteudo fica centralizado na chapa automaticamente.\n"
            "DESMARQUE para posicionar/arrastar as peças livremente na página."
        )
        self._center_check.toggled.connect(self._set_center_on_sheet)
        card.body.addWidget(self._center_check)
        # QA 2.0 (fonte única): "Ajustar chapa" e a sangria saíram DESTE card —
        # o controle visível mora na barra Faca; _offset segue vivo como estado
        # (sessão/projeto/testes) sincronizado pela barra.
        self._offset = LengthSpin(-100, 100)
        self._offset.valueChanged.connect(lambda _: self._relayout(renest=False))
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
        self._fill_faca_combo(self._faca_mode)
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
        # "Nós da faca": pós-simplificação da linha de corte. Retas ficam
        # perfeitamente retas em qualquer nível; muda só o detalhe das curvas.
        self._faca_nodes = NoWheelComboBox()
        self._faca_nodes.addItem("Fino (mais nós, máximo detalhe)", "fino")
        self._faca_nodes.addItem("Médio (recomendado)", "medio")
        self._faca_nodes.addItem("Leve (menos nós, corte fluido)", "leve")
        self._faca_nodes.setCurrentIndex(1)  # Médio por padrão
        self._faca_nodes.setToolTip(
            "Quantidade de nós da linha de corte enviada à máquina.\n"
            "Retas continuam retas em qualquer nível (pontos colineares saem).\n"
            "Fino: desvio máx. 0,1mm · Médio: 0,3mm · Leve: 0,6mm — todos\n"
            "abaixo da espessura da lâmina; menos nós = corte mais fluido."
        )
        self._faca_nodes.currentIndexChanged.connect(
            lambda _: self._relayout(renest=False)
        )
        # QA 2.0 (fonte única): "Nós da faca" e "Modo da faca" saíram do card —
        # os controles visíveis moram no popup "Ajustes" da barra Faca; os
        # widgets seguem vivos como estado (sessão/projeto/testes).
        self._shared = NoWheelComboBox()
        self._shared.addItems(["Faca por peça (quadrados)", "Faca compartilhada (grade)"])
        self._shared.currentIndexChanged.connect(lambda _: self._relayout(renest=False))
        return card

    def _build_imagens_card(self) -> CollapsibleCard:
        """Secao 3 - Imagens (recolhida): faca automática de PNG/JPG/WEBP."""
        card = self._doc_card("Imagens", "imagens", collapsed=True)
        # Sensibilidade agora mora no SLIDER da barra Faca (topo) — aqui fica só
        # como estado (sincronizado pela barra). Tira o controle duplicado da
        # lateral (U1 declutter 27/07).
        self._auto_sensitivity = _spin(0, 100)
        # QA 2.0 (fonte única): "Suavizar" e a sangria da imagem saíram do
        # card — os controles visíveis moram na barra Faca (Offset vale para
        # PDF e imagem juntos; Suavizar no popup Ajustes). Widgets vivos como
        # estado (sessão/projeto/testes), sincronizados pela barra.
        self._auto_smooth = _spin(0, 5)
        self._auto_smooth.valueChanged.connect(lambda _: self._relayout(renest=False))
        self._auto_offset = LengthSpin(-100, 100)
        self._auto_offset.valueChanged.connect(lambda _: self._relayout(renest=False))
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
        # Rotulos pela FORMA da marca (neutros); a maquina que le cada forma
        # fica nos tooltips (REG_HINTS). O data e contrato com motor,
        # exportadores e projeto salvo — NUNCA mudar.
        self._reg_type.addItem("Nenhuma", "none")
        self._reg_type.addItem("Círculos", "circles")
        self._reg_type.addItem("Marcas em L", "mimaki")
        self._reg_type.addItem("Círculos + L", "both")  # cortar na Mimaki, refilar na IECHO
        self._reg_type.addItem("Quadrados", "squares")
        self._reg_type.addItem("Cruzes", "crosses")
        self._reg_type.addItem("L de canto", "corner_l")  # sem quadro (difere da Mimaki)
        self._reg_type.currentIndexChanged.connect(lambda _: self._relayout(renest=False))
        self._reg_type.currentIndexChanged.connect(
            lambda _: self._update_reg_thickness_state()
        )
        card.body.addWidget(labeled("Tipo de registro", self._reg_type))
        self._reg_margin = LengthSpin(0, 200)
        self._reg_diameter = LengthSpin(1, 50)
        self._grid_fields(card.body, [
            ("Marcas: afastamento", self._reg_margin,
             "Distância das marcas até a arte (mm).\n"
             "Vale para círculos, quadrados, cruzes e L de canto."),
            ("Marcas: tamanho", self._reg_diameter,
             "Tamanho da marca (mm): diâmetro do círculo, lado do\n"
             "quadrado, comprimento da cruz e dos braços do L."),
        ])
        self._reg_thickness = LengthSpin(0.3, 2.0)
        self._reg_thickness.valueChanged.connect(lambda _: self._relayout(renest=False))
        card.body.addWidget(self._labeled_tip(
            "Marcas: espessura do traço", self._reg_thickness,
            "Espessura do traço (mm) das cruzes e dos Ls de canto.\n"
            "Formas cheias (círculo/quadrado) não usam espessura."
        ))
        self._update_reg_thickness_state()
        self._mk_distance = LengthSpin(0, 200)
        self._mk_distance.valueChanged.connect(lambda _: self._relayout(renest=False))
        self._mk_size = LengthSpin(1, 100)
        self._mk_size.valueChanged.connect(lambda _: self._relayout(renest=False))
        self._grid_fields(card.body, [
            ("Distância da marca", self._mk_distance,
             "Distância do quadro (frame) até o conteudo (mm)."),
            ("Tamanho da marca", self._mk_size, "Tamanho das marcas em L (mm)."),
        ])
        self._mk_thickness = LengthSpin(0.1, 10)
        card.body.addWidget(self._labeled_tip(
            "Espessura da marca", self._mk_thickness,
            "Espessura das marcas de registro (mm)."
        ))
        return card

    def _build_cartelas_tab(self) -> QWidget:
        """Aba lateral 'Cartelas' (fluxo cartela + refile da grafica), FORA da
        lista de cards do Documento: sempre a um clique, sem rolar a lista.

        Passo a passo ilustrado: 1) montar a cartela (as pecas encaixam
        dentro dela); 2) repetir a MESMA cartela na chapa inteira, com as
        linhas de refile centralizadas (todas as cartelas iguais); 3) exportar
        as duas facas — Mimaki (1 cartela so) e refile (chapa toda)."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_SM)

        cap = QLabel("Monte uma cartela, repita na chapa e exporte as duas facas.")
        cap.setProperty("role", "caption")
        cap.setWordWrap(True)
        lay.addWidget(cap)

        self._cart_on = QCheckBox("Produzir em cartelas")
        self._cart_on.setToolTip(
            "Liga o fluxo de cartelas: a chapa vira uma grade de cartelas\n"
            "iguais, com linhas retas de refile (fora a fora) entre elas.\n"
            "Use com o registro \"Mimaki + IECHO\" para a impressão sair\n"
            "com as duas marcas."
        )
        self._cart_on.toggled.connect(self._cartela_toggled)
        lay.addWidget(self._cart_on)

        # Botão que FAZ TUDO: importa (se a biblioteca estiver vazia), liga o
        # modo e monta a chapa. Sem ele o cliente marcava a opção antes de
        # gerar a produção e nada acontecia ("to perdido", 15/07).
        self._btn_cart_gerar = QPushButton("  Gerar chapa de cartelas")
        self._btn_cart_gerar.setIcon(icons.icon("grid-3x3", theme.ICON_ON_ACCENT))
        self._btn_cart_gerar.setProperty("accent", "true")
        self._btn_cart_gerar.setCursor(Qt.PointingHandCursor)
        self._btn_cart_gerar.setToolTip(
            "Monta a página: liga o modo cartelas e gera a produção.\n"
            "Se ainda não houver arquivo, abre a janela de importação."
        )
        self._btn_cart_gerar.clicked.connect(self._cartela_generate)
        lay.addWidget(self._btn_cart_gerar)

        card1 = CollapsibleCard("Passo 1 · Monte a cartela")
        self._cart_step1 = QLabel()
        self._cart_step1.setAlignment(Qt.AlignCenter)
        card1.body.addWidget(self._cart_step1)
        hint1 = QLabel(
            "As quantidades da tabela são o conteúdo de <b>uma</b> cartela; "
            "as peças encaixam dentro dela."
        )
        hint1.setWordWrap(True)
        hint1.setProperty("role", "caption")
        card1.body.addWidget(hint1)
        self._cart_w = LengthSpin(10, 5000)
        self._cart_w.setValue(330.0)
        self._cart_w.editingFinished.connect(lambda: self._relayout(renest=True))
        self._cart_h = LengthSpin(10, 5000)
        self._cart_h.setValue(480.0)
        self._cart_h.editingFinished.connect(lambda: self._relayout(renest=True))
        self._cart_margin = LengthSpin(0, 100)
        self._cart_margin.setValue(5.0)
        self._cart_margin.editingFinished.connect(lambda: self._relayout(renest=True))
        self._grid_fields(card1.body, [
            ("Largura da cartela", self._cart_w,
             "Largura de cada cartela (mm). O sistema calcula quantas\n"
             "cabem na chapa e centraliza o conjunto."),
            ("Altura da cartela", self._cart_h, "Altura de cada cartela (mm)."),
            ("Respiro interno", self._cart_margin,
             "Distância mínima entre as peças e a borda da cartela (mm),\n"
             "para a faca da peça não encostar no corte de refile."),
        ])
        lay.addWidget(card1)

        card2 = CollapsibleCard("Passo 2 · Repita na chapa (refile)")
        self._cart_step2 = QLabel()
        self._cart_step2.setAlignment(Qt.AlignCenter)
        card2.body.addWidget(self._cart_step2)
        self._cart_identical = QCheckBox("Todas as cartelas iguais (repetir a 1ª)")
        self._cart_identical.setChecked(True)
        self._cart_identical.setToolTip(
            "Enche a chapa com cópias exatas da cartela do Passo 1 — o\n"
            "jeito clássico da gráfica (uma faca Mimaki serve para todas).\n"
            "Desligado: as cartelas são preenchidas em sequência com a\n"
            "quantidade total da tabela (podem sair diferentes entre si)."
        )
        self._cart_identical.toggled.connect(lambda _: self._relayout(renest=True))
        card2.body.addWidget(self._cart_identical)
        self._cart_gap = LengthSpin(0, 200)
        self._cart_gap.editingFinished.connect(lambda: self._relayout(renest=True))
        self._grid_fields(card2.body, [
            ("Espaço entre cartelas", self._cart_gap,
             "0 = cartelas coladas (o refile corta UMA linha entre elas).\n"
             "Maior que 0 = duas linhas, com apara no meio."),
        ])
        # Registros do fluxo, SEM caçar o card "Marcas de registro": dois
        # checkboxes que comandam o mesmo _reg_type (e ficam em dia com ele).
        self._cart_reg_mimaki = QCheckBox("Registro Mimaki em cada cartela (Ls)")
        self._cart_reg_mimaki.setChecked(True)
        self._cart_reg_mimaki.setToolTip(
            "Marcas em L nos cantos de CADA cartela — a Mimaki lê cartela\n"
            "por cartela depois do refile."
        )
        self._cart_reg_iecho = QCheckBox("Registro IECHO no refile (bolinhas)")
        self._cart_reg_iecho.setChecked(True)
        self._cart_reg_iecho.setToolTip(
            "Bolinhas pretas nos cantos da CHAPA — a refiladora IECHO usa\n"
            "para alinhar os cortes de separação."
        )
        self._cart_reg_mimaki.toggled.connect(lambda _: self._apply_cart_marks())
        self._cart_reg_iecho.toggled.connect(lambda _: self._apply_cart_marks())
        card2.body.addWidget(self._cart_reg_mimaki)
        card2.body.addWidget(self._cart_reg_iecho)
        # combo "Tipo de registro" mudou por fora? espelha nos checkboxes
        self._reg_type.currentIndexChanged.connect(lambda _: self._sync_cart_marks())
        self._cart_info = QLabel()
        self._cart_info.setWordWrap(True)
        self._cart_info.setProperty("role", "caption")
        card2.body.addWidget(self._cart_info)
        lay.addWidget(card2)

        card3 = CollapsibleCard("Passo 3 · Exporte as facas")
        self._cart_step3 = QLabel()
        self._cart_step3.setAlignment(Qt.AlignCenter)
        card3.body.addWidget(self._cart_step3)
        hint3 = QLabel(
            "São <b>duas</b> facas: a da Mimaki corta as peças de uma cartela "
            "(todas são iguais); a de refile separa as cartelas na chapa toda."
        )
        hint3.setWordWrap(True)
        hint3.setProperty("role", "caption")
        card3.body.addWidget(hint3)
        self._btn_faca_mimaki_cart = QPushButton("  Faca Mimaki — 1 cartela (PDF)")
        self._btn_faca_mimaki_cart.setIcon(icons.icon("scissors", theme.ICON))
        self._btn_faca_mimaki_cart.setToolTip(
            "Contornos das peças de UMA cartela (+ quadro das marcas em L).\n"
            "Como as cartelas são iguais, essa faca serve para todas."
        )
        self._btn_faca_mimaki_cart.clicked.connect(self.export_faca_mimaki_cartela)
        card3.body.addWidget(self._btn_faca_mimaki_cart)
        self._btn_faca_refile = QPushButton("  Faca de refile — chapa toda (DXF)")
        self._btn_faca_refile.setIcon(icons.icon("grid-3x3", theme.ICON))
        self._btn_faca_refile.setToolTip(
            "Linhas retas de refile (fora a fora) + bolinhas de registro,\n"
            "para a refiladora separar as cartelas."
        )
        self._btn_faca_refile.clicked.connect(self.export_faca_iecho)
        card3.body.addWidget(self._btn_faca_refile)
        self._btn_producao_cart = QPushButton("  Produção completa (3 arquivos)")
        self._btn_producao_cart.setIcon(icons.icon("download", theme.ICON))
        self._btn_producao_cart.setToolTip(
            "Gera de uma vez: IMPRESSAO.pdf (com as duas marcas),\n"
            "FACA-MIMAKI.pdf (1 cartela) e FACA-IECHO.dxf (refile)."
        )
        self._btn_producao_cart.clicked.connect(self.export_producao_cartelas)
        card3.body.addWidget(self._btn_producao_cart)
        lay.addWidget(card3)

        lay.addStretch()
        self._refresh_cartela_illustrations()
        self._update_cartela_info()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self._cartelas_tab = scroll
        return scroll

    def _refresh_cartela_illustrations(self) -> None:
        """(Re)desenha as ilustrações da aba Cartelas nas cores do tema."""
        if not hasattr(self, "_cart_step1"):
            return
        self._cart_step1.setPixmap(faca_icons.cartela_pixmap("montar"))
        self._cart_step2.setPixmap(faca_icons.cartela_pixmap("replicar"))
        self._cart_step3.setPixmap(faca_icons.cartela_pixmap("facas"))

    def _update_cartela_info(self) -> None:
        """Resumo vivo da grade: quantas cartelas cabem e as sobras do refile."""
        if not hasattr(self, "_cart_info"):
            return
        if not self._cartela_enabled():
            self._cart_info.setText(
                "Ative \"Produzir em cartelas\" para ver a distribuição na chapa."
            )
            return
        grid = self._cartela_grid_now()
        if grid is None:
            self._cart_info.setText(
                f"<span style='color:{theme.WARNING}'>A cartela não cabe na "
                "chapa — confira as medidas.</span>"
            )
            return
        rows = grid.rows or 1
        per = grid.cols * rows
        texto = (
            f"<b>{grid.cols} × {rows} = {per} cartela(s)</b> por chapa · "
            f"sobra lateral {units.fmt_len(grid.origin_x)} · "
            f"vertical {units.fmt_len(grid.origin_y)}"
        )
        if self._result is None:  # modo ligado mas a chapa nunca foi montada
            passo = (
                "clique em <b>Gerar chapa de cartelas</b> (acima) para montar"
                if self._paths else
                "adicione um arquivo (Ctrl+I) e clique em "
                "<b>Gerar chapa de cartelas</b>"
            )
            texto += (
                f"<br><span style='color:{theme.WARNING}'>A página ainda não "
                f"foi montada — {passo}.</span>"
            )
        self._cart_info.setText(texto)

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

    def _build_doc_nav(self, sections) -> QFrame:
        """Barra de sub-abas do painel Documento, estilo ABA DE FICHARIO.

        Antes era um segmento com a ativa pintada de azul: parecia um botao
        solto, e o cliente nao percebia que Produção/Acabamento/Registro sao
        abas (28/07). Agora cada uma tem forma de aba — canto redondo so em
        cima, sem borda embaixo (encosta na folha) e uma LOMBADA de 3px no
        topo: cinza parada, azul-claro no hover, azul na ativa. O hover e o
        que responde antes do clique e diz "isto aqui e clicavel".

        Cores por token do tema (o hardcode antigo quebrava nos temas escuros)."""
        bar = QFrame()
        bar.setObjectName("docNav")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._doc_nav_btns = []
        for i, (label, _card) in enumerate(sections):
            b = QPushButton(label)
            b.setObjectName("docTab")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self._show_doc_section(idx))
            self._doc_nav_btns.append(b)
            lay.addWidget(b, 1)
        self._doc_nav_bar = bar
        return bar

    def _apply_doc_tabs_theme(self) -> None:
        """(Re)pinta as sub-abas e a folha com os tokens do tema ATUAL.

        Folha de widget guarda a cor no momento em que e montada; o tema troca
        ao vivo (claro/escuro/midnight/carbon). Sem reaplicar aqui, as abas e o
        conteudo ficavam BRANCOS num tema escuro — a mancha clara no meio do
        painel escuro. Chamado na montagem e em _on_theme_changed."""
        bar = getattr(self, "_doc_nav_bar", None)
        if bar is not None:
            bar.setStyleSheet(
                "#docNav{background:transparent;}"
                f"#docTab{{background:{theme.SURFACE_ALT}; color:{theme.TEXT_SECONDARY};"
                f" border:1px solid {theme.BORDER}; border-bottom:none;"
                f" border-top:3px solid {theme.BORDER_STRONG};"
                " border-top-left-radius:7px; border-top-right-radius:7px;"
                " border-bottom-left-radius:0; border-bottom-right-radius:0;"
                " padding:6px 2px 8px; font-size:11px; font-weight:600;}"
                f"#docTab:hover{{border-top-color:{theme.ACCENT_SOFT};"
                f" color:{theme.TEXT};}}"
                f"#docTab:checked{{background:{theme.SURFACE};"
                f" border-top-color:{theme.ACCENT}; color:{theme.ACCENT};"
                " font-weight:700;}"
            )
        # a secao visivel e a FOLHA da aba: borda sem o topo (quem fecha em
        # cima e a propria aba) e canto redondo so embaixo
        folha = (
            f"#card{{background:{theme.SURFACE};"
            f" border:1px solid {theme.BORDER}; border-top:none;"
            " border-top-left-radius:0; border-top-right-radius:0;"
            f" border-bottom-left-radius:{theme.RADIUS_CARD}px;"
            f" border-bottom-right-radius:{theme.RADIUS_CARD}px;}}"
        )
        for card in getattr(self, "_doc_sections", ()):
            card.setStyleSheet(folha)

    def _show_doc_section(self, index: int) -> None:
        """Mostra só a seção `index` do painel Documento (recolhe as demais) e
        marca a sub-aba correspondente em azul."""
        for i, card in enumerate(self._doc_sections):
            card.set_collapsed(i != index)
        for i, btn in enumerate(self._doc_nav_btns):
            btn.setChecked(i == index)

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
        off = float(self._offset.value())
        sinal = "+" if off >= 0 else "−"
        # bloco azul mostra só a largura do material ("1250 mm"); a área usada
        # vem no mesmo bloco (set_value de _sum_area abaixo)
        self._sum_material.set_value(units.fmt_len(mat.width))
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
        self._reg_thickness.setValue(s.reg_thickness)
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
        s.reg_thickness = float(self._reg_thickness.value())
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

    def _update_reg_thickness_state(self) -> None:
        """Espessura do traço só se aplica às marcas de linha (cruz / L de
        canto); nas formas cheias o campo fica desabilitado."""
        if hasattr(self, "_reg_thickness"):
            self._reg_thickness.setEnabled(self._reg() in ("crosses", "corner_l"))

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
            # raio de arredondamento dos cantos: global na barra Faca; o card
            # "Faca deste arquivo" sobrepõe por arquivo
            "corner_radius": (
                float(self._ct_radius.value()) if hasattr(self, "_ct_radius") else 0.0
            ),
            "mode": self._faca_mode.currentData(),  # ver _FACA_MODES (auto/rect/...)
        }

    def _params_for(self, path) -> dict:
        """Params de faca efetivos do arquivo: global + override ESPARSO.

        O override guarda SÓ as chaves que o usuário sobrescreveu naquele
        arquivo; todo o resto continua seguindo o global AO VIVO. (Varredura
        09/07: a cópia completa congelava recorte/giro/canto globais nos
        arquivos com override — mesma doença do bug do Offset.)"""
        return {
            **self._global_faca_params(),
            **self._file_overrides.get(path, {}),
        }

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
        manual = self._faca_manual.get(path)
        if manual is not None:
            # faca EDITADA A MAO (Pontos) vence o recalculo automatico
            return self._manual_faca(base, params, manual)
        is_img = isinstance(base, ImageArtwork)
        # imagem usa a "sangria de imagem" (auto_offset); PDF usa a sangria da faca.
        sangria = params["auto_offset"] if is_img else params["offset"]
        mode = self._resolve_faca_mode(params.get("mode", "auto"), base)
        if mode == "rect":  # corte reto por fora (vale p/ imagem e PDF)
            art_r = self._faca_uc.execute(self._transform(base, params), sangria)
            # cantos arredondados valem ATE para o retangulo puro
            radius = float(params.get("corner_radius", 0.0))
            if radius > 0 and art_r.cut_contour is not None:
                art_r = replace(
                    art_r, cut_contour=round_corners(art_r.cut_contour, radius)
                )
            return art_r
        if mode == "vector":  # faca do cliente (linha vetorial do PDF)
            raw = self._scaled_contour(self._pdf_vector_contour(base), sx, sy)
            # mode="vector": fidelidade — o desenho do cliente NAO passa por
            # densidade/suavizar/reducao de nos (só sangria/raio se pedidos)
            return self._contour_faca(base, raw, params, params["offset"], mode="vector")
        # contorno (justo / suave / simplificado), para imagem ou PDF rasterizado
        if is_img:
            raw = base.raw_contour
        else:
            raw = self._scaled_contour(self._pdf_raster_contour(base), sx, sy)
        return self._contour_faca(base, raw, params, sangria, mode)

    def _manual_faca(self, base, params: dict, manual: dict):
        """Aplica a faca editada a mao (ferramenta Pontos) a arte base.

        Os contornos foram salvos no espaco art-local da peça no momento da
        edição ("w"/"h"/"rotation"). Se depois o usuario girar a peça ou
        redimensionar o arquivo, os contornos giram/escalam junto — mas os
        ajustes de faca (sangria/suavizar/modo) NAO se aplicam mais: manual e
        manual, até "voltar ao automático"."""
        art_t = self._transform(base, params)
        w0, h0 = float(manual["w"]), float(manual["h"])
        delta = (int(params.get("rotation", 0)) - int(manual.get("rotation", 0))) % 360
        contours = list(manual["contours"])
        if delta:
            contours = [
                crop_and_rotate_contour(c, 0.0, delta, w0, h0)[0] for c in contours
            ]
            if delta in (90, 270):
                w0, h0 = h0, w0
        sx = art_t.size.width / w0 if w0 else 1.0
        sy = art_t.size.height / h0 if h0 else 1.0
        scaled = [self._scaled_contour(c, sx, sy) for c in contours]
        return replace(
            art_t, cut_contour=scaled[0], extra_cuts=tuple(scaled[1:])
        )

    def _resolve_faca_mode(self, mode: str, base) -> str:
        """Resolve o modo 'auto' pelo tipo da arte e valida o modo pedido.

        - PDF: 'auto' -> faca do CLIENTE se houver linha magenta no vetor
          (a convenção de corte das gráficas); senão retângulo (corte reto).
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
            # a linha magenta é inequívoca ("quero cortar AQUI") — usa a faca
            # do cliente sem o usuário precisar trocar o combo
            if self._pdf_client_knife(base) is not None:
                return "vector"
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
            raws = tuple(self._scaled_contour(c, sx, sy) for c in base.raw_contours)
            return replace(base, size=target, raw_contour=raw, raw_contours=raws), sx, sy
        return replace(base, size=target), sx, sy

    @staticmethod
    def _scaled_contour(contour, sx, sy):
        """Escala um contorno de corte pelos fatores (sx, sy). None -> None."""
        if contour is None or (sx == 1.0 and sy == 1.0):
            return contour
        return CutContour(tuple(Point2D(p.x * sx, p.y * sy) for p in contour.points))

    def _pdf_vector_contour_ex(self, base):
        """(contorno, motivo) da faca vetorial do PDF, cacheado por (path, pág).

        motivo: tier de select_cut_rings ('magenta'/'spot'/'stroke'/'all') ou
        None quando não há vetor utilizável. NÃO mexe nos avisos — quem chama
        decide o que dizer (o modo AUTO sonda silenciosamente)."""
        key = self._sources.get(base.id)
        if key is None:
            return None, None
        if key in self._vector_contours:
            return self._vector_contours[key]
        path, page = key
        try:
            infos = self._vector_extractor.extract_rings_info(path, page)
            rings, reason = select_cut_rings(infos)
            result = (self._vector_generator.generate(rings), reason)
        except Exception:  # sem vetor de corte utilizavel
            result = (None, None)
        self._vector_contours[key] = result
        return result

    def _pdf_client_knife(self, base):
        """Faca do cliente SÓ se inequívoca (linha magenta). Usada pelo modo
        AUTO: magenta = intenção clara de corte; os demais tiers exigem que o
        usuário escolha 'Faca do cliente' de propósito."""
        contour, reason = self._pdf_vector_contour_ex(base)
        return contour if reason == "magenta" else None

    def _pdf_vector_contour(self, base):
        """Faca do cliente (modo 'vector'): contorno vetorial do PDF + aviso
        didático do que foi detectado. Sem vetor utilizavel, registra um aviso
        e cai no retângulo (retorna None)."""
        contour, reason = self._pdf_vector_contour_ex(base)
        if contour is None:
            self._faca_notice = (
                "warning",
                "Não encontrei vetor de corte no PDF; usei o retângulo. "
                "Desenhe a faca como traço vetorial magenta 100% (sem "
                "preenchimento) por cima da arte e exporte em PDF.",
            )
        elif reason == "magenta":
            self._faca_notice = (
                "info",
                "Faca do cliente detectada pela linha MAGENTA do PDF "
                f"({len(contour.points)} pontos).",
            )
        elif reason in ("spot", "stroke"):
            self._faca_notice = (
                "info",
                "Faca do cliente detectada pelo traço sem preenchimento "
                f"({len(contour.points)} pontos). Para garantir sempre, "
                "desenhe a faca em magenta 100% (rosa choque).",
            )
        else:  # "all": sem pista de faca — usou a união de TODOS os vetores
            self._faca_notice = (
                "warning",
                "Não achei uma linha de faca no PDF (traço magenta ou sem "
                "preenchimento); usei o contorno geral dos vetores — "
                "confira o resultado. Ideal: desenhe a faca como traço "
                "magenta 100%, sem preenchimento, por cima da arte.",
            )
        return contour

    def _regenerate_faca(self) -> None:
        """Botão 'Gerar Faca': refaz a detecção da faca (contorno/cliente) e
        recalcula, sem precisar reimportar nem refazer o nesting do zero.

        Sem produção ainda: gera a produção JA com faca (assim o botão azul
        sempre funciona, ex.: depois de remover tudo e soltar outro arquivo)."""
        if not self._loaded:
            if self._paths:
                with _wait_cursor():
                    self.generate(blocking=True, faca=True)
            else:
                self._toasts.warning("Adicione arquivos na biblioteca primeiro.")
            return
        self._pdf_contours = {}
        self._vector_contours = {}
        self._faca_on = True  # liga a faca (modo "soltar sem faca" -> gera agora)
        with _wait_cursor():
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
        contour = self._finish_contour(contour, params, sangria, mode)
        # facas ADICIONAIS: demais desenhos separados na imagem (mesmos transforms
        # do principal). So imagens tem raw_contours; PDF/vetor -> vazio.
        extras = []
        for raw in getattr(base, "raw_contours", ()):
            c, _, _ = crop_and_rotate_contour(
                raw, crop, rotation, base.size.width, base.size.height
            )
            extras.append(self._finish_contour(c, params, sangria, mode))
        # SOLDA (estilo Contorno do Corel): facas vizinhas que se INVADEM (a
        # sangria de um desenho entra no outro) viram UMA linha externa unica —
        # senao a lamina atravessaria o adesivo do lado. Quem nao se toca
        # continua com a propria faca, intacta.
        if extras:
            welded = weld_contours([contour, *extras])
            contour, extras = welded[0], list(welded[1:])
        return replace(
            base, size=Size(w, h), cut_contour=contour, extra_cuts=tuple(extras)
        )

    def _finish_contour(self, contour, params, sangria, mode):
        """Aplica densidade + suavizar + sangria a UM contorno ja recortado/girado."""
        if mode == "vector":
            # faca do CLIENTE: o desenho dele é a verdade — sem densidade,
            # sem suavizar, sem redução de nós (deformavam a faca e o cliente
            # via "outra faca"). Sangria e raio só se o usuário pedir.
            if sangria != 0:
                contour = offset_contour(contour, sangria, params.get("corner", "round"))
            radius = float(params.get("corner_radius", 0.0))
            if radius > 0:
                contour = round_corners(contour, radius)
            return contour
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
        # pos-processamento: tira os nós redundantes que suavizar (dobra por
        # passada) e a sangria arredondada (arcos densos) criam. Tolerância do
        # seletor "Nós da faca"; com suavizar ligado ela cai (tabela _SMOOTH)
        # para NAO desfazer a curva que o suavizado acabou de criar.
        if len(contour.points) > 8:
            reduced = simplify_contour(contour, self._faca_nodes_tol(smooth))
            if len(reduced.points) >= 3:
                contour = reduced
        # cantos arredondados (raio em mm, estilo Contorno do Corel) — por
        # ULTIMO, para a redução de nós não facetar os arcos recém-criados
        radius = float(params.get("corner_radius", 0.0))
        if radius > 0:
            contour = round_corners(contour, radius)
        return contour

    def _faca_nodes_tol(self, smooth: int = 0) -> float:
        """Tolerância (mm) do seletor 'Nós da faca' (padrão: Médio).

        Com suavização ativa usa a tabela fina (preserva a curva macia)."""
        table = FACA_NODE_TOLERANCES_SMOOTH if smooth > 0 else FACA_NODE_TOLERANCES
        default = table["medio"]
        if not hasattr(self, "_faca_nodes"):
            return default
        return table.get(self._faca_nodes.currentData(), default)

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
        self._faca_manual = {}  # restaurar padroes descarta a edicao manual
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
        self._mark_dirty()
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
        # Soltar o PDF na biblioteca NAO pergunta as paginas (decisao do Philipe
        # 28/07): trazer o arquivo tem de ser um gesto so. Quem quiser escolher
        # usa o botao "Páginas do PDF..." ou o menu do botao direito na peca.

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
            escolhidas = self._file_pages.get(path)
            if escolhidas:  # so aparece quando NAO e o PDF inteiro
                total_pg = self._pdf_page_count(path)
                meta += f" · {len(escolhidas)} de {total_pg} pág."
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
            self._clear_scene(notify=True)  # nada sera redesenhado depois
            self._status_ctl.set_production(0, 0)
            self._alert.clear()
            # varredura 09/07: sem isto a barra Faca ficava visível sem nenhum
            # arquivo e o texto-guia do canvas não voltava ao "arraste aqui"
            self._update_property_bar()
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
                import pypdfium2 as pdfium
                doc = pdfium.PdfDocument(path)
                total = len(doc)
                doc.close()
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
                    w_mm, h_mm = self._source_size_mm(path, pm)
                    preview.set_page(pm, w_mm, h_mm)
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
            # QA A1: o toast de sucesso só DEPOIS do bake real — e só se ele
            # gerou o arquivo recortado (o cache foi invalidado acima, então
            # qualquer entrada deste path é desta geração).
            if any(k[0] == path for k in self._baked_crops):
                self._toasts.success(f"Recorte aplicado a {len(pages)} página(s)")
        else:
            # sem produção carregada o bake ainda não rodou: só configurado
            self._toasts.success(f"Recorte configurado para {len(pages)} página(s)")

    @staticmethod
    def _pdf_page_count(path: str) -> int:
        """Numero de paginas do PDF (0 se nao for PDF ou nao abrir)."""
        if Path(path).suffix.lower() != ".pdf":
            return 0
        try:
            import pypdfium2 as pdfium

            doc = pdfium.PdfDocument(path)
            total = len(doc)
            doc.close()
            return total
        except Exception:
            return 0

    def _pages_dialog(self, path: str) -> bool:
        """Escolha de QUAIS paginas do PDF entram na area de trabalho.

        Miniaturas com caixa de marcar + Todas/Nenhuma/Inverter. Devolve True
        se o usuario confirmou. Vem tudo marcado, entao confirmar sem mexer =
        comportamento de sempre (todas as paginas)."""
        total = self._pdf_page_count(path)
        if total <= 1:
            return False

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Páginas — {Path(path).name}")
        dlg.resize(720, 540)
        root = QVBoxLayout(dlg)
        topo = QLabel(f"{total} páginas. Marque as que vão para a área de trabalho.")
        topo.setProperty("role", "caption")
        root.addWidget(topo)

        lista = QListWidget()
        lista.setViewMode(QListWidget.IconMode)
        lista.setIconSize(QSize(110, 150))
        lista.setGridSize(QSize(130, 190))
        lista.setResizeMode(QListWidget.Adjust)
        lista.setMovement(QListWidget.Static)
        lista.setSelectionMode(QListWidget.NoSelection)
        lista.setSpacing(4)
        escolhidas = set(self._file_pages.get(path, range(total)))
        for pg in range(total):
            item = QListWidgetItem(f"{pg + 1}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if pg in escolhidas else Qt.Unchecked)
            item.setData(Qt.UserRole, pg)
            with contextlib.suppress(Exception):
                data = self._renderer.render_png(
                    path, pg, dpi=26, box=self._import_box.currentData()
                )
                pm = QPixmap()
                pm.loadFromData(data, "PNG")
                if not pm.isNull():
                    item.setIcon(QIcon(pm))
            lista.addItem(item)
        root.addWidget(lista, 1)

        def marcar(estado) -> None:
            for i in range(lista.count()):
                lista.item(i).setCheckState(estado)

        def inverter() -> None:
            for i in range(lista.count()):
                it = lista.item(i)
                it.setCheckState(
                    Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked
                )

        linha = QHBoxLayout()
        for texto, fn in (
            ("Todas", lambda: marcar(Qt.Checked)),
            ("Nenhuma", lambda: marcar(Qt.Unchecked)),
            ("Inverter", inverter),
        ):
            b = QPushButton(texto)
            b.clicked.connect(fn)
            linha.addWidget(b)
        linha.addStretch()
        root.addLayout(linha)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            return False

        marcadas = [
            lista.item(i).data(Qt.UserRole)
            for i in range(lista.count())
            if lista.item(i).checkState() == Qt.Checked
        ]
        if not marcadas:
            self._toasts.info("Marque ao menos uma página.")
            return False
        self._set_file_pages(path, marcadas, total)
        return True

    def _set_file_pages(self, path: str, marcadas: list[int], total: int) -> None:
        """Grava a escolha (ou apaga, se for tudo) e regenera se ja havia produção."""
        if len(marcadas) >= total:
            mudou = self._file_pages.pop(path, None) is not None
        else:
            mudou = self._file_pages.get(path) != marcadas
            self._file_pages[path] = marcadas
        self._refresh_library_metadata()
        if mudou and self._loaded:
            self.generate(blocking=True)
        if mudou:
            self._dirty = True

    def _pages_dialog_selected(self) -> None:
        """Botao 'Páginas...' da biblioteca: age no arquivo selecionado."""
        row = self._table.currentRow()
        if row < 0 or row >= len(self._paths):
            QMessageBox.information(self, "PrintNest", "Selecione um arquivo na biblioteca.")
            return
        path = self._paths[row]
        if self._pdf_page_count(path) <= 1:
            self._toasts.info("Só faz sentido em PDF com mais de uma página.")
            return
        self._pages_dialog(path)

    def _source_size_mm(self, path: str, preview_pm) -> tuple[float, float]:
        """Tamanho FISICO (mm) do arquivo, do jeito que ele entra na chapa.

        O dialogo de recorte trabalha em mm, entao ele precisa do mesmo tamanho
        que o importador usa — senao cada mm digitado corta um tanto diferente.

        Em PDF os dois batem: o renderizador escala os pontos por dpi/72, entao
        px*25.4/dpi da o tamanho certo. Em IMAGEM, nao: o renderizador trata
        1px como 1pt (comportamento antigo, mantido para os previews), enquanto
        o importador usa o DPI do arquivo. Num PNG de 96dpi isso dava uma
        pagina 1,333x maior no dialogo (800x1000px viravam 282x353mm em vez de
        212x265mm) e o recorte saia MUITO maior do que o desenhado."""
        if Path(path).suffix.lower() != ".pdf":
            with contextlib.suppress(Exception):
                from PIL import Image

                with Image.open(path) as im:
                    w_px, h_px = im.size
                dpi = Cv2ImageImporter._read_dpi(path)  # mesma regra do importador
                return w_px / dpi * 25.4, h_px / dpi * 25.4
        return preview_pm.width() * 25.4 / 110.0, preview_pm.height() * 25.4 / 110.0

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
            # QA A1: o bake falhou e a produção vai sair com o arquivo INTEIRO;
            # sem este aviso o recorte era descartado em silêncio.
            self._toasts.warning(
                f"Recorte de {Path(path).name} não pôde ser aplicado — usando o original"
            )
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
            import pikepdf

            mm2pt = 72.0 / 25.4
            doc = pikepdf.open(path)
            for pg, (left, top, right, bottom) in crops.items():
                if not (0 <= pg < len(doc.pages)):
                    continue
                page = doc.pages[pg]
                mx0, my0, mx1, my1 = (float(v) for v in page.mediabox)
                # recorte em mm com origem no TOPO-esquerda; o PDF conta o Y
                # de baixo para cima (top corta my1, bottom corta my0)
                new = (
                    mx0 + left * mm2pt, my0 + bottom * mm2pt,
                    mx1 - right * mm2pt, my1 - top * mm2pt,
                )
                if (new[2] - new[0]) > 1 and (new[3] - new[1]) > 1:
                    box = pikepdf.Array(list(new))
                    page.MediaBox = box
                    page.CropBox = box
                    # caixas antigas apontavam para a página SEM recorte
                    for key in ("/TrimBox", "/BleedBox", "/ArtBox"):
                        if key in page:
                            del page[key]
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

    # ---- cartelas (fluxo Mimaki + IECHO) ----
    def _cartela_enabled(self) -> bool:
        return bool(getattr(self, "_cart_on", None)) and self._cart_on.isChecked()

    def _cartela_identical_enabled(self) -> bool:
        """Fluxo de cartelas IDENTICAS ligado (repetir a 1a na chapa toda)."""
        return (
            self._cartela_enabled()
            and hasattr(self, "_cart_identical")
            and self._cart_identical.isChecked()
        )

    def _nesting_for_mode(self):
        """Nesting da vez: grade (faca compartilhada) ou MaxRects; embrulhado
        no nesting por CARTELA quando o modo cartela esta ligado (identicas:
        repete a 1a cartela; senao, preenche em sequencia)."""
        uc = self._grid_nesting_uc if self._shared.currentIndex() == 1 else self._nesting_uc
        if self._cartela_enabled():
            from app.application.use_cases.cartela_nesting import (
                CartelaNestingUseCase,
                IdenticalCartelaNestingUseCase,
            )
            klass = (
                IdenticalCartelaNestingUseCase
                if self._cartela_identical_enabled() else CartelaNestingUseCase
            )
            return klass(
                uc,
                float(self._cart_w.value()), float(self._cart_h.value()),
                gutter=float(self._cart_gap.value()),
                cell_margin=float(self._cart_margin.value()),
            )
        return uc

    def _apply_cart_marks(self) -> None:
        """Checkboxes de registro da aba Cartelas -> combo 'Tipo de registro'.
        Mimaki (Ls por cartela) + IECHO (bolinhas do refile) em linguagem de
        gráfica, sem o cliente caçar o card de marcas."""
        data = {
            (True, True): "both", (True, False): "mimaki",
            (False, True): "circles", (False, False): "none",
        }[(self._cart_reg_mimaki.isChecked(), self._cart_reg_iecho.isChecked())]
        idx = self._reg_type.findData(data)
        if idx >= 0 and idx != self._reg_type.currentIndex():
            self._reg_type.setCurrentIndex(idx)  # redesenha as marcas ao vivo

    def _sync_cart_marks(self) -> None:
        """Combo 'Tipo de registro' mudou por fora -> espelha nos checkboxes
        da aba Cartelas (só com o modo ligado, para um reset de padrões antes
        de gerar não desmarcar a preferência do fluxo)."""
        if not hasattr(self, "_cart_reg_mimaki") or not self._cartela_enabled():
            return
        data = self._reg_type.currentData()
        for box, on in (
            (self._cart_reg_mimaki, data in ("mimaki", "both")),
            (self._cart_reg_iecho, data in ("circles", "both")),
        ):
            box.blockSignals(True)
            box.setChecked(on)
            box.blockSignals(False)

    def _cartela_toggled(self, on: bool) -> None:
        """Marcar 'Produzir em cartelas' dá resposta IMEDIATA: se a produção
        ainda não foi gerada (o _relayout ignoraria a mudança), gera agora
        com os arquivos da biblioteca — era um no-op silencioso e o cliente
        ficava perdido sem ver a chapa montada."""
        if on:
            self._suspend_relayout = True
            try:
                self._apply_cart_marks()  # registros do fluxo (Mimaki/IECHO)
            finally:
                self._suspend_relayout = False
        if on and not self._loaded and self._paths:
            self.generate()
        else:
            self._relayout(renest=True)
        self._update_cartela_info()

    def _cartela_generate(self) -> None:
        """Botão 'Gerar chapa de cartelas' (aba Cartelas): faz o caminho
        inteiro num clique — importa se preciso, liga o modo e monta a chapa."""
        if not self._paths:
            self.add_pdfs()  # seletor de arquivos; cancelar = não gera
            if not self._paths:
                return
        if not self._cart_on.isChecked():
            self._cart_on.blockSignals(True)  # evita gerar duas vezes
            self._cart_on.setChecked(True)
            self._cart_on.blockSignals(False)
        self._suspend_relayout = True
        try:
            self._apply_cart_marks()  # registros escolhidos nos checkboxes
        finally:
            self._suspend_relayout = False
        self.generate()
        self._update_cartela_info()

    def _cartela_grid_now(self, material=None, sheet_length=None):
        """Grade de cartelas dos parametros ATUAIS (None se desligado/nao cabe)."""
        if not self._cartela_enabled():
            return None
        from app.domain.cut.cartela import build_cartela_grid
        material = material or self._material()
        if sheet_length is None:
            sheet_length = float(self._height.value())
        return build_cartela_grid(
            material.width, sheet_length,
            float(self._cart_w.value()), float(self._cart_h.value()),
            float(self._cart_gap.value()),
        )

    def _cartela_segments_for(self, layout):
        """Linhas de separacao (IECHO) de UMA chapa; [] se modo desligado."""
        grid = self._cartela_grid_now(layout.material, layout.used_length)
        if grid is None:
            return []
        from app.domain.cut.cartela import cartela_separation_segments
        return cartela_separation_segments(
            grid, layout.material.width, layout.used_length
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
        # QAX-05: um arquivo AUSENTE no disco abortava a geração INTEIRA
        # (nada saía, mesmo com os demais válidos). Agora as linhas ⚠ são
        # puladas com aviso e o resto gera normalmente.
        ausentes = [p for p in target_paths if not Path(p).exists()]
        if ausentes:
            target_paths = [p for p in target_paths if Path(p).exists()]
            nomes = ", ".join(Path(p).name for p in ausentes[:3])
            extra = "..." if len(ausentes) > 3 else ""
            self._toasts.warning(
                f"Ignorando {len(ausentes)} arquivo(s) ausente(s): {nomes}{extra}"
            )
            if not target_paths:
                QMessageBox.warning(
                    self, "PrintNest",
                    "Nenhum dos arquivos foi encontrado no disco.\n"
                    "Verifique se foram movidos ou renomeados.",
                )
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
        # paginas escolhidas: o filtro e por caminho EFETIVO (o PDF recortado em
        # cache), que e o que o pipeline recebe
        pages_map = {
            eff: list(self._file_pages[orig])
            for orig, eff in zip(target_paths, eff_paths, strict=False)
            if orig in self._file_pages
        }
        pages_map = pages_map or None

        if blocking:
            # QA A14: PDF ruim (0 bytes/corrompido/sem páginas) estourava a
            # exceção crua aqui — o worker em thread já tratava; mesmo padrão.
            try:
                result = self._pipeline.execute(
                    eff_paths, material, offset, sheet_height, box,
                    sensitivity=sensitivity, ignore_white=ignore_white,
                    pages=pages_map,
                )
                unique = sorted(set(result.sources.values()))
                png_map = {key: self._renderer.render_png(key[0], key[1], box=box) for key in unique}
            except Exception as exc:
                self._on_failed(str(exc))
                return
            self._load_production(result, png_map)
            return

        self._set_busy(True)
        self._thread = QThread()
        self._worker = ProductionWorker(
            self._pipeline, self._renderer, eff_paths,
            material, offset, sheet_height, box, sensitivity, ignore_white,
            pages_map,
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
        if not self._confirm_discard("Fechar o PrintNest descarta o que não foi salvo."):
            event.ignore()
            return
        # solta o sinal do ThemeManager (singleton vive além da janela; sem
        # isto uma troca de tema depois chamaria métodos de objeto destruído)
        with contextlib.suppress(Exception):
            from app.presentation.themes import manager as _tm
            _tm().theme_changed.disconnect(self._on_theme_changed)
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(10000)  # geracao normal termina em segundos
        super().closeEvent(event)

    def _set_exports_enabled(self, enabled: bool) -> None:
        # U1/P7: desabilitado MUDO confunde — o tooltip diz o que falta
        tips = getattr(self, "_export_tips", {})
        for action in getattr(self, "_export_actions", []):
            action.setEnabled(enabled)
            base = tips.get(action, action.toolTip())
            action.setToolTip(
                base if enabled else f"{base}\n(Gere a produção primeiro — F5)"
            )

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)

    def _on_finished(self, bundle) -> None:
        self._set_busy(False)
        result, png_map = bundle
        self._load_production(result, png_map)

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        import os
        if os.environ.get("PYTEST_CURRENT_TEST") or not self.isVisible():
            # suites offscreen não podem abrir modal (travaria o CI)
            self._toasts.error(f"Falha ao gerar produção: {message}")
            return
        QMessageBox.critical(self, "PrintNest", f"Falha ao gerar produção:\n{message}")

    def _load_production(self, result: ProductionResult, png_map: dict) -> None:
        self._mark_dirty()
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
        self._maybe_restore_saved_arrangement()  # QA A0: arranjo do .printnest

    def _maybe_restore_saved_arrangement(self) -> None:
        """QA A0: reaplica o arranjo manual salvo no .printnest na PRIMEIRA
        geração após abrir o projeto. O pendente é consumido aqui (uma chance):
        gerações seguintes, Organizar e Resetar arranjo seguem como hoje.
        Assinatura (arquivos+quantidades) diferente ou peça salva que não
        existe mais -> mantém o encaixe automático recém-gerado e avisa."""
        saved = self._pending_arranjo
        if not saved:
            return
        self._pending_arranjo = None
        if self._result is None:
            return
        aviso = "Arranjo salvo não pôde ser aplicado — usando o encaixe automático"
        if saved.get("assinatura") != self._arranjo_signature():
            self._toasts.warning(aviso)
            return
        by_id = {a.id: a for a in self._result.artworks}
        material = self._material()
        sheets: list = []
        instances: list = []
        try:
            for chapa in saved.get("chapas") or []:
                items = []
                for it in chapa["itens"]:
                    art = by_id.get(str(it["id"]))
                    if art is None:  # arquivo mudou fora (ex.: página sumiu)
                        raise KeyError(it["id"])
                    items.append(PlacedItem(
                        str(it["id"]),
                        Point2D(float(it["x"]), float(it["y"])),
                    ))
                    instances.append(art)
                sheets.append(Layout(material, items, float(chapa["comprimento"])))
        except (KeyError, TypeError, ValueError):
            self._toasts.warning(aviso)
            return
        if not instances:
            self._toasts.warning(aviso)
            return
        # mesmo primitivo do desfazer (sem push): não briga com o Undo — a
        # pilha fica vazia, como após qualquer geração.
        self._apply_state((sheets, instances))
        self._undo.clear()
        self._toasts.info("Arranjo manual do projeto restaurado")

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
        # QAX-01: recálculo real = trabalho alterado (parâmetro, quantidade,
        # giro, sangria...). Abrir projeto re-seta _dirty=False no FINAL do
        # _apply_project, então marcar aqui nunca suja um projeto recém-aberto.
        self._mark_dirty()
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
            self._clear_scene(notify=True)
            self._alert.show_message(
                AlertLevel.WARNING, "Nenhuma peça (verifique as quantidades)."
            )
            self._status_ctl.set_production(0, 0)
            return
        # 3. re-nesta (layout/giro: re-encaixa mantendo a contagem) ou preserva
        #    as posições atuais (ajuste de geometria: sangria/recorte/tamanho).
        if renest or fresh:
            # faca compartilhada precisa das peças alinhadas em grade; senao usa
            # MaxRects (maximo aproveitamento). Modo cartela embrulha qualquer
            # um dos dois (encaixe cartela por cartela).
            try:
                nesting_uc = self._nesting_for_mode()
                if hasattr(nesting_uc, "set_from_table"):
                    # cartelas identicas: a tabela define o conteudo de UMA
                    # cartela; re-nesting recebe a producao ja replicada
                    nesting_uc.set_from_table(bool(from_table or fresh))
                sheets = nesting_uc.execute_sheets(
                    instances, material, sheet_height
                )
            except ValidationError as exc:
                self._alert.show_message(AlertLevel.ERROR, str(exc))
                return
        else:
            sheets = self._preserve_arrangement(by_id, material)
        sheets = self._center_sheets(sheets, material, instances)  # centraliza na página
        self._result = ProductionResult(sheets=sheets, artworks=instances, sources=self._sources)
        self._draw_preview()
        total = sum(s.item_count for s in sheets)
        self._status.setText(f"{len(sheets)} chapa(s) | {total} peça(s)")
        self._update_status_and_alerts(sheets, total, instances, material)
        self._update_cartela_info()
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
        estiver desligada. Modo cartela: a GRADE ja centraliza (deslocar o
        conteudo desalinharia as pecas das linhas de separacao)."""
        if not self._center_on_sheet or self._cartela_enabled():
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

    def _clear_scene(self, *, notify: bool = False) -> None:
        """Esvazia a cena SEM deixar wrapper Python apontando para item morto.

        scene.clear() destroi os QGraphicsItem do lado C++. Dois jeitos de isso
        virar heap corruption (0xc0000374 — o Windows mata o processo na hora,
        sem traceback nenhum, foi o que derrubou o app ao excluir arquivo da
        biblioteca):

        1. alguma lista nossa continuar segurando os itens destruidos: quando o
           wrapper e coletado o PySide tenta deletar de novo. So o _draw_preview
           zerava tudo; os outros scene.clear() deixavam fantasmas, alças e a
           lista de objetos apontando para lixo.
        2. o clear() emite selectionChanged NO MEIO da destruicao; o nosso
           handler responde criando alças/fantasmas dentro de uma cena que esta
           sendo esvaziada — itens que nascem ja condenados. Por isso os sinais
           ficam bloqueados durante o clear.

        notify=True roda o handler UMA vez depois, com a cena vazia e estavel
        (para quem termina sem redesenhar nada). Todo scene.clear() desta janela
        passa por aqui — nao chame direto.

        A trava do (2) e uma FLAG nossa, nao QSignalBlocker na cena: bloquear os
        sinais da cena calava tambem os que o QGraphicsView usa por dentro para
        invalidar o viewport — o fundo da chapa "abaixava" e so voltava ao
        minimizar/maximizar a janela (repaint forcado)."""
        self._piece_items = []
        self._obj_rows = []
        self._guide_preview_item = None
        # itens decorativos (chapa branca, marcas, linhas de corte): precisam de
        # referência Python, senao o PySide os coleta e o Qt remove o item orfao
        # durante o laco de seleção (a chapa "sumia" ao clicar no vazio).
        self._decor_items = []
        self._ghost_items = []
        self._resize_handles = []
        self._node_handles = []
        self._resize_preview = None
        self._clearing_scene = True
        try:
            self._scene.clear()
        finally:
            self._clearing_scene = False
        if notify:
            self._on_selection_changed()

    def _draw_preview(self) -> None:
        # guarda a seleção para restaurar após o redesenho (continuar empurrando
        # com as setas, desfazer/refazer sem perder o que estava selecionado).
        # (pela SELEÇÃO da cena, não por _piece_items: em tela dividida/só-corte
        # as peças não são interativas e ficam fora da lista — a seleção se
        # perdia). Guardar so os NUMEROS: manter wrapper de item vivo depois do
        # clear e receita de heap corruption (o PySide deleta de novo ao coletar).
        antes = self._selected_pieces()
        selected_keys = {self._piece_sel_key(p) for p in antes}
        prefer_dx = min((p.dx for p in antes), default=None)
        del antes  # nenhum wrapper de item atravessa o clear abaixo
        # NAO limpa o histórico aqui: senao excluir/duplicar/desfazer (que
        # redesenham) apagariam o próprio comando. O reset do histórico acontece
        # só quando o arranjo e regenerado (em _relayout).
        self._clear_scene()
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
        elif mode == "split_h":
            # lado a lado: arte à esquerda, faca deslocada em X (largura total
            # ocupada pelas chapas + respiro), espelhando o split vertical.
            self._draw_sheets(draw_art=True, draw_cut=False, dy=0.0, interactive=False)
            total_w = max(
                (i * (s.material.width + SHEET_GAP_MM) + s.material.width
                 for i, s in enumerate(self._result.sheets)),
                default=0.0,
            )
            self._draw_sheets(
                draw_art=False, draw_cut=True, dy=0.0,
                dx0=total_w + max(50.0, total_w * 0.15),
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
                for p in self._scene_pieces(prefer_dx):
                    if self._piece_sel_key(p) in selected_keys:
                        p.setSelected(True)
            finally:
                self._keep_tab = False
        self._refresh_object_list()
        self._update_overlay()

    def _draw_sheets(self, *, draw_art: bool, draw_cut: bool, dy: float,
                     dx0: float = 0.0, interactive: bool) -> None:
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
            dx = dx0 + index * (layout.material.width + SHEET_GAP_MM)
            off = max(1.5, layout.material.width * 0.004)  # ~4/1000 da largura
            self._keep(self._scene.addRect(
                dx + off, dy + off, layout.material.width, layout.used_length,
                QPen(Qt.NoPen), shadow_brush,
            ))
            sheet_rect = self._scene.addRect(
                dx, dy, layout.material.width, layout.used_length, sheet_pen, sheet_brush
            )
            self._keep(sheet_rect)
            # fusao automatica (corte rente): retangulos colados viram grade.
            # 'consumed' segue a MESMA ordem de _contours_of (itens -> facas).
            fused_consumed: set[int] = set()
            fused_segments: list = []
            if draw_cut and not shared:
                fused_consumed, fused_segments = merge_touching_rect_cuts(
                    [c.points for c in positioned_cut_contours(layout, result.artworks)]
                )
            faca_idx = 0
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
                        self._resolve_faca_mode(
                            self._params_for(self._path_of(item.artwork_id))
                            .get("mode", "auto"),
                            art,
                        ) == "vector"
                    )
                    pen = client_pen if is_client else faca_pen
                    # faca principal + facas adicionais (varios desenhos na peca)
                    for faca in (art.cut_contour, *art.extra_cuts):
                        idx = faca_idx
                        faca_idx += 1
                        if idx in fused_consumed:
                            continue  # esta faca virou linha da grade fundida
                        # contorno curvo vira Bezier no canvas (curva lisa,
                        # igual ao que sai no PDF/DXF); reto segue poligono
                        segs = cubic_segments(faca.points)
                        if segs and has_curves(segs):
                            pp = QPainterPath()
                            pp.moveTo(ax + segs[0].p0.x, ay + segs[0].p0.y)
                            for s in segs:
                                pp.cubicTo(
                                    ax + s.c1.x, ay + s.c1.y,
                                    ax + s.c2.x, ay + s.c2.y,
                                    ax + s.p1.x, ay + s.p1.y,
                                )
                            path_item = QGraphicsPathItem(pp, piece)
                            path_item.setPen(pen)
                            path_item.setBrush(Qt.NoBrush)
                            continue
                        poly = QPolygonF(
                            [QPointF(ax + p.x, ay + p.y) for p in faca.points]
                        )
                        poly_item = QGraphicsPolygonItem(poly, piece)
                        poly_item.setPen(pen)
                        poly_item.setBrush(Qt.NoBrush)
                self._scene.addItem(piece)

            if draw_cut and not shared and fused_segments:
                for seg in fused_segments:
                    self._keep(self._scene.addLine(
                        dx + seg.start.x, dy + seg.start.y,
                        dx + seg.end.x, dy + seg.end.y, faca_pen,
                    ))
            if draw_cut and shared:
                for seg in shared_cut_segments(layout, result.artworks):
                    self._keep(self._scene.addLine(
                        dx + seg.start.x, dy + seg.start.y,
                        dx + seg.end.x, dy + seg.end.y, faca_pen,
                    ))
            if draw_cut:
                # linhas de separacao das CARTELAS (corte da IECHO, fora a fora)
                for seg in self._cartela_segments_for(layout):
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

        # NAVEGAÇÃO LIVRE (pedido do beta 13/07, estilo Corel): a área rolável
        # ganha uma folga GENEROSA ao redor do conteúdo. Sem isto o sceneRect
        # colava no conteúdo e o Qt travava o pan e a âncora do zoom perto das
        # bordas — "a página fica no canto e não vai pro centro nem a pau".
        rect = self._scene.itemsBoundingRect()
        if not rect.isEmpty():
            folga = max(rect.width(), rect.height()) * 2.0 + 1000.0
            self._scene.setSceneRect(rect.adjusted(-folga, -folga, folga, folga))

    def _fit_view(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if not rect.isEmpty():
            self._view.fitInView(rect, Qt.KeepAspectRatio)
            self._view.view_changed.emit()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        # Restaurar da barra de tarefas com o canvas "perdido" (pan/zoom longe
        # da chapa — feedback do beta: "minimizei e nao acho mais a pagina"):
        # se NENHUMA parte da cena esta visivel, re-enquadra sozinho.
        if event.type() == QEvent.Type.WindowStateChange and not (
            self.windowState() & Qt.WindowState.WindowMinimized
        ):
            QTimer.singleShot(0, self._rescue_lost_view)

    def _rescue_lost_view(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return
        visible = self._view.mapToScene(self._view.viewport().rect()).boundingRect()
        if not visible.intersects(rect):
            self._fit_view()

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

    # ---- menu de botao direito no canvas ----
    def _canvas_menu(self, pos) -> None:
        """Menu do botao direito na area de trabalho.

        Clicar com o direito numa peca que NAO esta selecionada passa a
        seleção para ela (comportamento de todo editor grafico): o que o menu
        oferece e sempre o que voce esta vendo marcado."""
        cena = self._view.mapToScene(pos)
        alvo = None
        for it in self._scene.items(cena):
            if isinstance(it, PieceItem):
                alvo = it
                break
        if alvo is not None and not alvo.isSelected():
            self._scene.clearSelection()
            alvo.setSelected(True)
        menu = self._build_canvas_menu()
        menu.exec(self._view.viewport().mapToGlobal(pos))

    def _build_canvas_menu(self) -> QMenu:
        """Monta o menu conforme a seleção (separado do exec: da para testar)."""
        sel = self._selected_pieces()
        menu = QMenu(self._view)

        if sel:
            path = self._path_of(sel[0].artwork_id)
            nome = Path(path).name if path else "arquivo"
            e_pdf = bool(path) and Path(path).suffix.lower() == ".pdf"
            rotulo = "Recortar páginas..." if e_pdf else "Recortar imagem..."
            act = menu.addAction(icons.icon("replace", theme.ICON), f"{rotulo}  ({nome})")
            act.setEnabled(bool(path))
            act.triggered.connect(lambda: self._crop_from_canvas(path))
            if e_pdf and self._pdf_page_count(path) > 1:
                menu.addAction(
                    icons.icon("file-text", theme.ICON), "Escolher páginas do PDF...",
                ).triggered.connect(lambda: self._pages_dialog(path))
            menu.addSeparator()
            menu.addAction(
                icons.icon("copy", theme.ICON), "Duplicar\tCtrl+D",
            ).triggered.connect(self._duplicate_selected)
            menu.addAction(
                icons.icon("rotate-ccw", theme.ICON), "Girar 90° à esquerda",
            ).triggered.connect(lambda: self._rotate_selected(-90))
            menu.addAction(
                icons.icon("rotate-cw", theme.ICON), "Girar 90° à direita",
            ).triggered.connect(lambda: self._rotate_selected(90))
            menu.addSeparator()
            if len(sel) > 1:
                menu.addAction(
                    icons.icon("group", theme.ICON), "Agrupar",
                ).triggered.connect(self._group_selected)
            if any(isinstance(it, QGraphicsItemGroup) for it in self._scene.selectedItems()):
                menu.addAction(
                    icons.icon("ungroup", theme.ICON), "Desagrupar",
                ).triggered.connect(self._ungroup_selected)
            menu.addAction(
                icons.icon("align-vertical-justify-start", theme.ICON),
                "Trazer para frente",
            ).triggered.connect(self._bring_to_front)
            menu.addAction(
                icons.icon("align-vertical-justify-end", theme.ICON),
                "Enviar para trás",
            ).triggered.connect(self._send_to_back)
            menu.addSeparator()
            if path:
                menu.addAction(
                    icons.icon("layers", theme.ICON),
                    "Selecionar todas as peças deste arquivo",
                ).triggered.connect(lambda: self._select_same_file(path))
            menu.addAction(
                icons.icon("trash-2", theme.ICON), "Excluir da chapa\tDel",
            ).triggered.connect(self._delete_selected)
        else:
            # clique no vazio: acoes da chapa
            menu.addAction(
                icons.icon("grid-3x3", theme.ICON), "Organizar (re-encaixar)",
            ).triggered.connect(self._organize)
            menu.addAction(
                icons.icon("layers", theme.ICON), "Selecionar tudo\tCtrl+A",
            ).triggered.connect(self._select_all)
            menu.addAction(
                icons.icon("maximize", theme.ICON), "Ajustar à tela",
            ).triggered.connect(self._fit_view)
        return menu

    def _crop_from_canvas(self, path: str | None) -> None:
        """'Recortar' pelo menu da peca: seleciona o arquivo dela na biblioteca
        e abre o MESMO dialogo do botao (uma logica de recorte so)."""
        if not path:
            return
        for row, p in enumerate(self._paths):
            if p == path:
                self._table.setCurrentCell(row, 0)
                break
        else:
            self._toasts.info("Arquivo não está mais na biblioteca.")
            return
        self._crop_pages_dialog()

    def _select_same_file(self, path: str) -> None:
        """Marca todas as pecas que vieram do mesmo arquivo (util para aplicar
        giro/duplicar/excluir de uma vez)."""
        alvos = {
            b.id for b in self._base_artworks if self._path_of(b.id) == path
        }
        self._batch_select(lambda piece: piece.artwork_id in alvos)

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
        # em qual bloco o usuário estava (arte ou faca, na tela dividida): a
        # seleção nova tem que cair no mesmo lugar que ele esta olhando
        blocos = [p.dx for p in self._selected_pieces()]
        prefer_dx = min(blocos) if blocos else None
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
        self._select_pieces_at(add_by_sheet, prefer_dx)

    def _scene_pieces(self, prefer_dx: float | None = None) -> list:
        """Peças selecionaveis da cena — UMA por posição lógica, em qualquer modo.

        _piece_items só guarda as peças ARRASTAVEIS: em tela dividida e em
        só-corte elas nascem não-interativas e ficam de fora. Quem selecionava
        por ali (duplicar, Ctrl+A, restaurar seleção pós-redesenho) simplesmente
        não achava nada nesses modos — o 'Aplicar' duplicava e deixava a cópia
        SEM seleção, obrigando a clicar na peça de novo a cada cópia.

        Na tela dividida a mesma peça existe duas vezes (bloco da arte e bloco
        da faca, com dx diferente): fica só uma — a do bloco em que o usuário ja
        estava (prefer_dx), senão a da arte. Sem isso um duplicar viraria dois."""
        best: dict[tuple, object] = {}
        for it in self._scene.items():
            if not isinstance(it, PieceItem):
                continue
            key = self._piece_sel_key(it)
            cur = best.get(key)
            if cur is None:
                best[key] = it
            elif prefer_dx is None:
                if it.dx < cur.dx:
                    best[key] = it
            elif abs(it.dx - prefer_dx) < abs(cur.dx - prefer_dx):
                best[key] = it
        return list(best.values())

    def _batch_select(self, predicate, prefer_dx: float | None = None) -> None:
        """Seleciona em LOTE com os sinais da cena bloqueados (QAX-04).

        Cada setSelected disparava _on_selection_changed inteiro (O(n)); em
        loops de seleção isso virava O(n²): Ctrl+A + Ctrl+D com 256 peças
        levava 6s e com 2048 TRAVAVA o programa. Agora o handler roda UMA vez
        no final, custe 5 ou 5000 peças."""
        from PySide6.QtCore import QSignalBlocker

        try:
            with QSignalBlocker(self._scene):
                self._scene.clearSelection()
                for piece in self._scene_pieces(prefer_dx):
                    if predicate(piece):
                        piece.setSelected(True)
        except RuntimeError:
            return  # cena já destruída (fechando)
        self._on_selection_changed()

    def _select_pieces_at(self, add_by_sheet: dict,
                          prefer_dx: float | None = None) -> None:
        """Seleciona as peças recem-adicionadas (a cópia vira a nova seleção)."""
        targets = {
            (idx, p.artwork_id, round(p.position.x, 2), round(p.position.y, 2))
            for idx, placed in add_by_sheet.items()
            for p in placed
        }

        def _alvo(piece) -> bool:
            return (
                piece.sheet_index, piece.artwork_id,
                round(piece.scenePos().x() - piece.dx, 2),
                round(piece.scenePos().y() - piece.dy, 2),
            ) in targets

        # a cópia virar seleção NÃO pode jogar o usuário para a aba Peça: ele
        # esta no Documento > Posição, clicando Aplicar em cadeia (estilo Corel)
        self._keep_tab = True
        try:
            self._batch_select(_alvo, prefer_dx)
        finally:
            self._keep_tab = False

    # ---- adicionar arquivo da biblioteca a produção já gerada (arrastar) ----
    def _place_selected_on_sheet(self) -> None:
        """Botão 'Colocar na chapa' e duplo clique da biblioteca (U1).

        MESMO caminho de código do arrastar: delega em _on_library_drop, que
        gera a produção (sem faca) na primeira vez ou insere as peças no
        centro da vista quando já existe produção. Sem seleção, coloca todos.
        """
        if not self._paths:
            return
        if not self._table.selectedIndexes():
            self._table.selectAll()
        center = self._view.mapToScene(self._view.viewport().rect().center())
        self._on_library_drop(center)

    def _on_library_drop(self, scene_pos) -> None:
        rows = sorted({ix.row() for ix in self._table.selectedIndexes()})
        if not rows:
            rows = [self._table.currentRow()]
        paths = [self._paths[r] for r in rows if 0 <= r < len(self._paths)]
        if not paths:
            return
        if self._result is None or not self._loaded:
            # ainda não gerou: o drop monta a produção com os arquivos
            # SELECIONADOS (não todos), e SEM faca. A faca surge depois ao
            # clicar "Gerar Faca". O usuário organiza dali.
            self.generate(blocking=True, paths=paths, faca=False)
            return
        step = NUDGE_SUPER_MM
        for n, path in enumerate(paths):
            # deslocamento diagonal por arquivo para o drop não sobrepor
            self._add_file_to_production(
                path, QPointF(scene_pos.x() + n * step, scene_pos.y() + n * step)
            )

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
        sheets = self._nesting_for_mode().execute_sheets(
            instances, material, float(self._height.value())
        )
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
        # em lote: com centenas de peças o loop de setSelected era O(n²) (QAX-04)
        self._batch_select(lambda _piece: True)

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
            dict(self._faca_manual),  # facas editadas a mao (Pontos) tambem
        )

    def _apply_state(self, state) -> None:
        """Reaplica um estado (chapas + artes + giros + facas manuais) e
        redesenha. Base de desfazer/refazer. Tolera estados mais curtos."""
        if self._result is None:
            return
        sheets, artworks, *rest = state
        if rest:
            self._piece_rotations = dict(rest[0])
        if len(rest) > 1:
            self._faca_manual = dict(rest[1])
        self._result = ProductionResult(
            sheets=sheets, artworks=artworks, sources=self._sources
        )
        self._mark_dirty()
        self._draw_preview()
        total = sum(s.item_count for s in sheets)
        self._status.setText(f"{len(sheets)} chapa(s) | {total} peça(s)")
        self._status_ctl.set_production(total, len(sheets))

    def _fit_sheets_to_content(self) -> None:
        """Ajusta cada chapa ao tamanho EXATO do arranjo atual: sem branco em
        volta na exportação/impressão. As marcas de registro não precisam
        entrar aqui — os exportadores já somam a folga delas (_faca_pad) ao
        redor da página, então a folha final sai 'conteúdo + marcas', justa.
        Desfazível com Ctrl+Z; o arranjo das peças não muda (só translada)."""
        if self._result is None or not self._result.sheets:
            return
        before = self._snapshot_sheets()
        by_id = {a.id: a for a in self._result.artworks}
        after = []
        changed = False
        for layout in before:
            xs, ys, xe, ye = [], [], [], []
            for item in layout.items:
                art = by_id.get(item.artwork_id)
                if art is None:
                    continue
                fp = artwork_footprint(art)
                xs.append(item.position.x)
                ys.append(item.position.y)
                xe.append(item.position.x + (fp.max_x - fp.min_x))
                ye.append(item.position.y + (fp.max_y - fp.min_y))
            if not xs:
                after.append(layout)
                continue
            minx, miny = min(xs), min(ys)
            width = max(1.0, max(xe) - minx)
            height = max(1.0, max(ye) - miny)
            items = [
                PlacedItem(
                    i.artwork_id,
                    Point2D(i.position.x - minx, i.position.y - miny),
                )
                for i in layout.items
            ]
            material = replace(layout.material, width=width, margin=0.0)
            after.append(Layout(material, items, height))
            changed = True
        if not changed:
            return
        self._commit_arrangement(before, after, "Ajustar chapa ao conteúdo")
        self._fit_view()
        self._toasts.success("Chapa ajustada ao conteúdo — exportação sem branco em volta")

    def _commit_arrangement(self, before, after, text: str) -> None:
        """Aplica 'after' e registra o passo no histórico (Ctrl+Z desfaz).

        'before'/'after' são listas de Layout. As artes não mudam numa operacao
        de arranjo (mover/excluir/duplicar), entao o estado usa as artes atuais.
        """
        arts = list(self._result.artworks)
        rot = dict(self._piece_rotations)  # arranjo não muda giros: mesmo dict
        man = dict(self._faca_manual)      # nem as facas manuais
        before_state = (before, arts, rot, man)
        after_state = (after, arts, rot, man)
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
        sel = set(self._selected_pieces())
        ids = {p.artwork_id for p in sel}
        if ids:
            # QA A13: o relayout RECRIA os PieceItem, então a seleção é
            # guardada por (artwork_id, nº da cópia) — re-selecionar por
            # artwork_id pegava TODAS as cópias e o Ctrl+D seguinte dobrava
            # a produção (1→2→4→8…).
            sel_keys = set()
            counters: dict = {}
            for p in self._piece_items:
                idx = counters.get(p.artwork_id, 0)
                counters[p.artwork_id] = idx + 1
                if p in sel:
                    sel_keys.add((p.artwork_id, idx))
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
            # se perdia -> re-seleciona as MESMAS cópias para continuar girando.
            self._reselect_copies(sel_keys)
            self._toasts.success(
                f"Girou {len(ids)} peça(s) {abs(delta)}°" if len(ids) > 1
                else f"Peça girada {abs(delta)}°"
            )
        else:
            # nada selecionado: gira todos (rotação global do documento)
            novo = (self._rotation_value() + delta) % 360
            self._rotation.setCurrentText(str(novo))  # dispara o relayout

    def _reselect_copies(self, keys) -> None:
        """Re-seleciona pelas cópias exatas (artwork_id, n-ésima cópia) após um
        re-encaixe. Diferente de _reselect_by_artwork, NAO expande a seleção
        para as outras cópias do mesmo artwork (QA A13)."""
        if not keys:
            return
        self._scene.clearSelection()
        counters: dict = {}
        for p in self._piece_items:
            idx = counters.get(p.artwork_id, 0)
            counters[p.artwork_id] = idx + 1
            if (p.artwork_id, idx) in keys:
                p.setSelected(True)

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

    def _open_cut_mode(self) -> None:
        """Modo Corte (laser/CNC): dialogo modal com cena e exportacao
        proprias — nao toca no arranjo de impressao. Import tardio porque o
        dialogo puxa pyclipper/fontTools, peso que o modo Impressao nao paga
        se o operador nunca abrir o Modo Corte."""
        from app.presentation.cut_mode_dialog import CutModeDialog

        CutModeDialog(self, export_dxf=self._dxf_export).exec()

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
        if reg == "squares":
            for mark in square_marks(
                layout, artworks,
                margin_mm=float(self._reg_margin.value()),
                size_mm=float(self._reg_diameter.value()),
            ):
                self._keep(self._scene.addRect(
                    dx + mark.center.x - mark.half, dy + mark.center.y - mark.half,
                    mark.size, mark.size, mark_pen, mark_brush,
                ))
        if reg in ("crosses", "corner_l"):
            fn = cross_mark_segments if reg == "crosses" else corner_l_segments
            for seg in fn(
                layout, artworks,
                margin_mm=float(self._reg_margin.value()),
                size_mm=float(self._reg_diameter.value()),
            ):
                self._keep(self._scene.addLine(
                    dx + seg.start.x, dy + seg.start.y,
                    dx + seg.end.x, dy + seg.end.y, mark_pen,
                ))
        if reg in ("mimaki", "both"):
            # cartelas identicas: um quadro de marcas em L POR cartela (a
            # Mimaki le cada uma depois do refile); senao, o quadro unico
            frames = self._cartela_mimaki_frames(layout)
            if frames:
                marks_list = mimaki_marks_for_frames(
                    frames,
                    distance_mm=float(self._mk_distance.value()),
                    mark_size_mm=float(self._mk_size.value()),
                )
            else:
                single = mimaki_marks(
                    layout, artworks,
                    distance_mm=float(self._mk_distance.value()),
                    mark_size_mm=float(self._mk_size.value()),
                )
                if single is None:
                    return
                marks_list = [single]
            for marks in marks_list:
                f = marks.frame
                self._keep(self._scene.addRect(
                    dx + f.min_x, dy + f.min_y, f.max_x - f.min_x, f.max_y - f.min_y,
                    faca_pen,
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
            "reg_thickness_mm": float(self._reg_thickness.value()),
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
            # cartelas identicas: marcas em L POR cartela na impressao
            "mimaki_frames_for": (
                self._cartela_mimaki_frames
                if self._cartela_identical_enabled() else None
            ),
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
        with _wait_cursor():
            self._print_export.execute(
                sheets, self._result.artworks, self._result.sources, path,
                **self._print_kwargs(),
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
        with _wait_cursor():
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
        """Monta (contornos, segmentos, marcas-circulo, marcas-segmento,
        marcas-polilinha) de um conjunto de chapas."""
        artworks = self._result.artworks
        sheet_width = sheets[0].material.width
        reg = self._reg()
        if self._shared.currentIndex() == 1:
            contours = []
            segments = shared_cut_segments_sheets(sheets, artworks, sheet_width)
        else:
            contours = positioned_cut_contours_sheets(sheets, artworks, sheet_width)
            # fusao automatica: retangulos COLADOS (corte rente, espacamento 0)
            # viram linhas continuas — a maquina corta 1x na linha em vez de 2x
            # na mesma borda. Pecas com espacamento seguem individuais.
            consumed, fused = merge_touching_rect_cuts(
                [c.points for c in contours]
            )
            if consumed:
                contours = [c for i, c in enumerate(contours) if i not in consumed]
                segments = fused
            else:
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
        mark_polylines = []
        if reg == "squares":
            # quadrado cheio vira polilinha FECHADA no layer de registro
            mark_polylines = [
                list(m.corners()) for m in square_marks_sheets(
                    sheets, artworks, sheet_width,
                    margin_mm=float(self._reg_margin.value()),
                    size_mm=float(self._reg_diameter.value()),
                )
            ]
        if reg in ("crosses", "corner_l"):
            fn = cross_mark_segments_sheets if reg == "crosses" else corner_l_segments_sheets
            mark_segments = fn(
                sheets, artworks, sheet_width,
                margin_mm=float(self._reg_margin.value()),
                size_mm=float(self._reg_diameter.value()),
            )
        return contours, segments, marks, mark_segments, mark_polylines

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
        with _wait_cursor():
            contours, segments, marks, mark_segments, mark_polys = self._dxf_payload(sheets)
            self._dxf_export.execute(
                contours, path, segments=segments, marks=marks,
                mark_segments=mark_segments, mark_polylines=mark_polys,
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
        with _wait_cursor():
            for i, sheet in enumerate(sheets, start=1):
                contours, segments, marks, mark_segments, mark_polys = self._dxf_payload([sheet])
                out = f"{stem}_{i:02d}{ext}"
                self._dxf_export.execute(
                    contours, out, segments=segments, marks=marks,
                    mark_segments=mark_segments, mark_polylines=mark_polys,
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
        if reg in ("squares", "crosses"):
            pad = max(pad, float(self._reg_margin.value()) + float(self._reg_diameter.value()))
        if reg == "corner_l":  # os bracos do L crescem PARA FORA do quadro
            pad = max(pad, float(self._reg_margin.value())
                      + float(self._reg_diameter.value())
                      + float(self._reg_thickness.value()))
        return pad

    @_guard_export
    def export_faca_pdf(self, path: str | None = None, pages=None, sheets_override=None,
                        include_circle_marks: bool = True,
                        dialog_title: str = "Exportar Faca (PDF)",
                        default_name: str = "FACA.pdf") -> None:
        """Exporta a faca (linhas de corte) em PDF vetorial, uma página por chapa.
        Inclui as marcas de registro (bolinhas), igual ao DXF e a impressao.
        include_circle_marks=False: versao para a MIMAKI (só contornos +
        quadro das marcas em L; as bolinhas ficam com a IECHO)."""
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        sheets = sheets_override if sheets_override is not None else self._select_export_sheets(
            self._effective_sheets(), pages, interactive, dialog_title
        )
        if sheets is None:
            return
        if not sheets:
            if interactive:
                QMessageBox.warning(self, "PrintNest", "Nenhuma chapa selecionada.")
            return
        # faca vazia = PDF em branco indo para a máquina de corte (bug QA-03):
        # valida ANTES de pedir o nome do arquivo e NUNCA grava sem linhas.
        contours_all, segments_all, _mk, _ln, _pl = self._dxf_payload(sheets)
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
                self, dialog_title,
                str(Path(self._settings.last_dir) / default_name), "PDF (*.pdf)",
            )
            if not path:
                return
        from app.infrastructure.exporters.pdf_writer import PdfWriter

        pad = self._faca_pad()  # folga para as marcas caberem na página
        _FACA_PEN = {"color": (0.86, 0.0, 0.0), "width_pt": 0.5}  # faca (vermelho)
        QApplication.setOverrideCursor(Qt.WaitCursor)  # ver _wait_cursor
        writer = PdfWriter()
        try:
            for sheet in sheets:
                writer.new_page(
                    sheet.material.width + 2 * pad,
                    sheet.used_length + 2 * pad,
                )
                contours, segments, marks, mark_segs, mark_polys = self._dxf_payload([sheet])
                for contour in contours:
                    # contorno curvo sai como Bezier NATIVO do PDF e agora em
                    # UM caminho FECHADO por contorno (QAX-06: antes eram
                    # dezenas de Beziers soltos e a mesa podia levantar a faca).
                    segs = cubic_segments(contour.points)
                    if segs and has_curves(segs):
                        writer.draw_bezier_path(
                            [
                                (
                                    (s.p0.x + pad, s.p0.y + pad),
                                    (s.c1.x + pad, s.c1.y + pad),
                                    (s.c2.x + pad, s.c2.y + pad),
                                    (s.p1.x + pad, s.p1.y + pad),
                                )
                                for s in segs
                            ],
                            close=True, **_FACA_PEN,
                        )
                        continue
                    pts = [(p.x + pad, p.y + pad) for p in contour.points]
                    if len(pts) >= 2:
                        writer.draw_polyline(pts, close=True, **_FACA_PEN)
                for seg in segments:
                    writer.draw_line(
                        (seg.start.x + pad, seg.start.y + pad),
                        (seg.end.x + pad, seg.end.y + pad),
                        **_FACA_PEN,
                    )
                if include_circle_marks:
                    for mark in marks:  # bolinhas de registro: PRETO solido
                        writer.draw_circle(
                            (mark.center.x + pad, mark.center.y + pad),
                            mark.radius, color=(0, 0, 0), fill=(0, 0, 0),
                        )
                    for poly in mark_polys:  # quadrados de registro: PRETO solido
                        xs = [p.x for p in poly]
                        ys = [p.y for p in poly]
                        writer.draw_rect_filled(
                            min(xs) + pad, min(ys) + pad,
                            max(xs) - min(xs), max(ys) - min(ys),
                        )
                    for seg in mark_segs:  # cruz / L de canto: traço preto
                        writer.draw_line(
                            (seg.start.x + pad, seg.start.y + pad),
                            (seg.end.x + pad, seg.end.y + pad),
                            width_pt=float(self._reg_thickness.value()) * 72.0 / 25.4,
                            color=(0, 0, 0),
                        )
            writer.save(path)
        finally:
            QApplication.restoreOverrideCursor()
            writer.close()
        if interactive:
            self._toasts.success("Faca exportada em PDF")

    # ---- exportacao por maquina (fluxo de cartelas Mimaki + IECHO) ----
    def export_faca_mimaki(self, path: str | None = None, pages=None) -> None:
        """Faca da MIMAKI: contornos das peças (+ quadro das marcas em L).
        Sem bolinhas e sem linhas de cartela — essas ficam com a IECHO."""
        self.export_faca_pdf(
            path, pages=pages, include_circle_marks=False,
            dialog_title="Exportar Faca Mimaki (PDF)",
            default_name="FACA-MIMAKI.pdf",
        )

    @_guard_export
    def export_faca_iecho(self, path: str | None = None, pages=None) -> None:
        """Faca da IECHO: linhas retas de separação das cartelas (fora a
        fora) + bolinhas de registro, em DXF."""
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        if not self._cartela_enabled():
            if interactive:
                QMessageBox.information(
                    self, "PrintNest",
                    "Ative \"Produzir em cartelas\" (aba Cartelas) para gerar\n"
                    "a faca de refile (separação das cartelas).",
                )
            return
        sheets = self._select_export_sheets(
            self._effective_sheets(), pages, interactive, "Exportar Faca IECHO (DXF)"
        )
        if not sheets:
            return
        if interactive:
            path, _ = QFileDialog.getSaveFileName(
                self, "Exportar Faca IECHO (DXF)",
                str(Path(self._settings.last_dir) / "FACA-IECHO.dxf"), "DXF (*.dxf)",
            )
            if not path:
                return
        with _wait_cursor():
            sheet_width = sheets[0].material.width
            segments = []
            for index, layout in enumerate(sheets):
                dx = index * (sheet_width + SHEET_GAP_MM)
                for seg in self._cartela_segments_for(layout):
                    segments.append(SharedSegment(
                        Point2D(seg.start.x + dx, seg.start.y),
                        Point2D(seg.end.x + dx, seg.end.y),
                    ))
            if not segments:
                if interactive:
                    QMessageBox.warning(
                        self, "PrintNest",
                        "Nenhuma linha de cartela para exportar (a cartela\n"
                        "não coube na chapa — confira as medidas).",
                    )
                return
            marks = []
            if self._reg() in ("circles", "both"):
                marks = registration_marks_sheets(
                    sheets, self._result.artworks, sheet_width,
                    margin_mm=float(self._reg_margin.value()),
                    diameter_mm=float(self._reg_diameter.value()),
                )
            self._dxf_export.execute([], path, segments=segments, marks=marks)
        if interactive:
            self._toasts.success("Faca IECHO (cartelas) exportada em DXF")

    def export_producao_cartelas(self) -> None:
        """Exporta o pacote completo do fluxo de cartelas de uma vez:
        IMPRESSAO.pdf (com as duas marcas) + FACA-MIMAKI.pdf + FACA-IECHO.dxf."""
        if self._result is None:
            return
        if not self._cartela_enabled():
            QMessageBox.information(
                self, "PrintNest",
                "Ative \"Produzir em cartelas\" (aba Cartelas) para usar a\n"
                "exportação por máquina.",
            )
            return
        if self._reg() != "both":
            resp = QMessageBox.question(
                self, "PrintNest",
                "O registro atual não é \"Mimaki + IECHO\", então a impressão\n"
                "não vai sair com as duas marcas.\n\nExportar assim mesmo?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
        base, _ = QFileDialog.getSaveFileName(
            self, "Exportar produção (nome base dos 3 arquivos)",
            str(Path(self._settings.last_dir) / "TRABALHO"), "Todos (*)",
        )
        if not base:
            return
        base = str(Path(base).with_suffix(""))  # tira extensão se digitada
        self.export_pdf(f"{base}_IMPRESSAO.pdf")
        # cartelas identicas: a faca da Mimaki e a de UMA cartela (serve para
        # todas); no modo sequencial segue a faca da chapa inteira
        if self._cartela_identical_enabled() and self._single_cartela_layout() is not None:
            self.export_faca_mimaki_cartela(f"{base}_FACA-MIMAKI.pdf")
        else:
            self.export_faca_mimaki(f"{base}_FACA-MIMAKI.pdf")
        self.export_faca_iecho(f"{base}_FACA-IECHO.dxf")
        self._toasts.success(
            f"Produção exportada: {Path(base).name}_IMPRESSAO.pdf, "
            "_FACA-MIMAKI.pdf e _FACA-IECHO.dxf"
        )

    def _show_cartelas_tab(self) -> None:
        """Abre a aba lateral 'Cartelas' (fluxo cartela + refile)."""
        if hasattr(self, "_cartelas_tab"):
            self._props_tabs.setCurrentWidget(self._cartelas_tab)

    def _single_cartela_layout(self):
        """Layout sintetico com o conteudo da 1a cartela, em coordenadas
        LOCAIS da cartela (0,0 no canto dela). E a base da faca Mimaki no
        fluxo de cartelas identicas: uma faca serve para todas. None se o
        modo cartela esta desligado ou nao ha producao."""
        if not self._cartela_enabled() or self._result is None:
            return None
        sheets = self._effective_sheets()
        if not sheets:
            return None
        first = sheets[0]
        grid = self._cartela_grid_now(first.material, first.used_length)
        if grid is None:
            return None
        eps = 1e-6
        ox, oy = grid.slot_origin(0)
        items = [
            PlacedItem(
                it.artwork_id,
                Point2D(it.position.x - ox, it.position.y - oy),
                it.rotation,
            )
            for it in first.items
            if ox - eps <= it.position.x <= ox + grid.cell_w + eps
            and oy - eps <= it.position.y <= oy + grid.cell_h + eps
        ]
        if not items:
            return None
        cart_material = Material(
            name=f"{first.material.name}/cartela",
            width=grid.cell_w,
            margin=0.0,
            spacing=first.material.spacing,
            spacing_y=first.material.spacing_y,
        )
        return Layout(material=cart_material, items=tuple(items),
                      used_length=grid.cell_h)

    @_guard_export
    def export_faca_mimaki_cartela(self, path: str | None = None) -> None:
        """Faca da MIMAKI no fluxo de cartelas identicas: os contornos das
        peças de UMA cartela (+ quadro das marcas em L). Como todas as
        cartelas são copias exatas, essa unica faca corta a produção toda;
        a separação das cartelas sai na faca de refile (chapa toda)."""
        if self._result is None:
            return
        interactive = not isinstance(path, str) or not path
        layout = self._single_cartela_layout()
        if layout is None:
            if interactive:
                QMessageBox.information(
                    self, "PrintNest",
                    "Ative \"Produzir em cartelas\" (aba Cartelas) e gere a\n"
                    "chapa antes de exportar a faca de uma cartela.",
                )
            return
        self.export_faca_pdf(
            path, sheets_override=[layout], include_circle_marks=False,
            dialog_title="Exportar Faca Mimaki — 1 cartela (PDF)",
            default_name="FACA-MIMAKI-CARTELA.pdf",
        )

    def _cartela_mimaki_frames(self, layout):
        """Bbox das facas de CADA cartela da chapa (marcas em L por cartela).
        Vazio fora do fluxo de cartelas identicas."""
        if not self._cartela_identical_enabled() or self._result is None:
            return []
        grid = self._cartela_grid_now(layout.material, layout.used_length)
        if grid is None:
            return []
        return cartela_cut_frames(layout, self._result.artworks, grid)
