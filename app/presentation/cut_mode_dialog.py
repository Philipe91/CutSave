"""Modo Corte (laser/CNC): dialogo do nesting true-shape (Fase 5).

Vive FORA da MainWindow de proposito. O canvas do modo Impressao desenha
PieceItem, que e um QGraphicsRectItem — so sabe retangulo. O modo Corte
precisa mostrar o CONTORNO real encaixado, entao tem cena propria aqui e nao
encosta em nada do fluxo de impressao.

Fluxo: importar SVG/PDF/texto (Fase 3) -> lista de pecas com quantidade ->
Organizar (TrueShapePacker, Fase 2) -> preview -> retoque manual (arrastar /
girar a peca, TAREFA E3) -> Exportar DXF (Fase 4).

CRITICO: Organizar guarda os Layouts e Exportar grava ESSES layouts
(export_layouts), nunca recalcula. Com genetics_time o genetico nao e
deterministico — recalcular faria o DXF sair diferente do preview. O retoque
manual (E3) escreve DIRETO em self._layouts pela mesma razao: preview,
Exportar DXF, Enviar p/ Corel e SVG leem dali, entao nao ha como divergirem.
"""

from __future__ import annotations

import math
import os
import tempfile
from collections import Counter
from dataclasses import dataclass, replace
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.application.ports.vector_importer import IVectorImporter
from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.application.use_cases.run_true_shape_nesting import (
    NestingExportResult,
    RunTrueShapeNestingUseCase,
    placed_cut_contours,
    to_nesting_shapes,
)
from app.domain.geometry import Point2D
from app.domain.geometry.polygon_with_holes import PolygonWithHoles
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.domain.nesting.true_shape import NestingShape, TrueShapePacker
from app.infrastructure.corel_bridge import send_file_to_corel
from app.infrastructure.exporters.svg_layout_exporter import write_layout_svg
from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter
from app.infrastructure.importers.svg_vector_importer import SvgVectorImporter
from app.infrastructure.text.fonttools_text_vectorizer import FontToolsTextVectorizer
from app.presentation import faca_icons, icons, theme
from app.shared.errors import ValidationError

_VECTOR_FILTER = "Vetores (*.svg *.pdf);;SVG (*.svg);;PDF (*.pdf)"

# (rotulo, passo em graus) do combo de giro; passo 0 = sem giro.
_ROTATE_MODES = (
    ("Sem giro", 0),
    ("Reto (90°)", 90),
    ("Fino (45°)", 45),
    ("Muito fino (15°)", 15),
)

# Vao entre as chapas no preview (mm) — as chapas ficam lado a lado, como a
# maquina recebe folha por folha (estilo eCut).
_PREVIEW_SHEET_GAP_MM = 30.0

# Mensagens rotativas do carregamento (estilo dica de video game): espera com
# contexto em vez de barra muda — pedido do Philipe em 21/07.
_NEST_TIPS = (
    "Buscando o melhor aproveitamento de material — isso pode levar alguns minutos.",
    "Dica: quantidade 20 da mesma peça custa quase o mesmo cálculo que 1 — o motor reaproveita.",
    "Dica: em trabalhos grandes, suba o 'Tempo de otimização' para 30–60s. O encaixe só melhora.",
    "Você sabia? O botão Texto… transforma qualquer fonte do Windows em curvas de corte.",
    "As peças giram sozinhas quando isso economiza material — às vezes ficar em pé vence.",
    "Dica: 'Altura da folha' 0 = bobina/chapa corrida; acima de 0, divide em folhas numeradas.",
    "O preview é exatamente o que sai no DXF — o que você vê é o que corta.",
    "Depois de organizar, arraste qualquer peça no preview — e a tecla R gira a selecionada.",
)


# ---------------------------------------------------------------------------
# Ilustrações locais (receita de faca_icons: QPainter + cores do tema NA
# CHAMADA + lru_cache). Padrão replicado aqui de propósito — importar
# main_window traria as ~8 mil linhas junto (ver docstring do _ZoomView).
# ---------------------------------------------------------------------------


@lru_cache(maxsize=32)
def _rotate_pixmap(step: int, muted: str, accent: str, size: int = 26) -> QPixmap:
    """Leque de ângulos do 'Giro das peças': um raio por ângulo permitido no
    quadrante — passo 0 é um raio só (sem giro), passos finos abrem o leque."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    ox, oy = size * 0.16, size * 0.84  # origem do leque (canto inferior esquerdo)
    r = size * 0.72
    arc = QRectF(ox - r * 0.5, oy - r * 0.5, r, r)
    p.setPen(QPen(QColor(muted), 1.1))
    p.drawArc(arc, 0, 90 * 16)  # guia do quadrante
    p.setPen(QPen(QColor(accent), 1.4))
    for ang in ([0] if step == 0 else range(0, 91, step)):
        rad = math.radians(ang)
        p.drawLine(
            QPointF(ox, oy),
            QPointF(ox + r * math.cos(rad), oy - r * math.sin(rad)),
        )
    p.end()
    return pm


@lru_cache(maxsize=8)
def _inside_pixmap(cut: str, accent: str, size: int = 26) -> QPixmap:
    """'Preencher furos': peça pequena aproveitando o miolo de um 'O'."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = size / 2.0
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(cut), 1.3))
    p.drawEllipse(QPointF(c, c), size * 0.40, size * 0.40)  # contorno do 'O'
    p.drawEllipse(QPointF(c, c), size * 0.26, size * 0.26)  # furo (miolo)
    p.setPen(QPen(QColor(accent), 1.3))
    p.drawEllipse(QPointF(c, c), size * 0.12, size * 0.12)  # peça hospedada
    p.end()
    return pm


@dataclass
class CutPiece:
    """Uma entrada da lista: pode ter varios corpos (um SVG com 3 formas, uma
    palavra com 5 letras). Cada corpo vira uma peca independente no nesting —
    o agrupamento aqui e so para o usuario nao ver 40 linhas por palavra."""

    name: str
    shapes: tuple[PolygonWithHoles, ...]
    quantity: int = 1

    @property
    def body_count(self) -> int:
        return len(self.shapes) * self.quantity


class _CutPieceItem(QGraphicsPathItem):
    """Peca do arranjo no preview: selecionavel e arrastavel (retoque manual
    pos-nesting, TAREFA E3).

    O caminho fica em coordenadas da CENA (mm do layout) e pos() carrega so o
    DELTA do arrasto em andamento — ao soltar, o dialogo grava a posicao nova
    no PlacedItem e o caminho e reconstruido com pos() de volta a zero, entao
    cena e self._layouts nunca divergem. 'bounds' e o retangulo vermelho da
    chapa configurada: a peca nao sai dele durante o arrasto.
    """

    def __init__(self, path: QPainterPath, index: int, bounds: QRectF, on_moved,
                 sheet: int = 0, dx: float = 0.0) -> None:
        super().__init__(path)
        self.index = index  # posicao do PlacedItem em layout.items
        self.bounds = bounds
        self.sheet = sheet  # qual chapa (as chapas ficam lado a lado na cena)
        self.dx = dx        # deslocamento da chapa na cena (mm)
        self._on_moved = on_moved
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.SizeAllCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            value = self._clamped(value)
        return super().itemChange(change, value)

    def _clamped(self, pos: QPointF) -> QPointF:
        """Empurra o delta de volta para dentro da chapa configurada.
        Sobreposicao entre pecas e permitida de proposito (o operador pode
        querer); sair da chapa nao — viraria corte no vazio."""
        br = self.path().boundingRect().translated(pos)
        dx = dy = 0.0
        if br.left() < self.bounds.left():
            dx = self.bounds.left() - br.left()
        elif br.right() > self.bounds.right():
            dx = self.bounds.right() - br.right()
        if br.top() < self.bounds.top():
            dy = self.bounds.top() - br.top()
        elif br.bottom() > self.bounds.bottom():
            dy = self.bounds.bottom() - br.bottom()
        return QPointF(pos.x() + dx, pos.y() + dy)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if not self.pos().isNull():
            self._on_moved(self)


class _HintList(QListWidget):
    """Lista com texto de estado vazio — caixa branca muda parece software
    travado (Missao 2 da E3)."""

    def __init__(self, hint: str) -> None:
        super().__init__()
        self._hint = hint

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.count() == 0:
            p = QPainter(self.viewport())
            p.setPen(QColor(theme.TEXT_SECONDARY))
            p.drawText(
                self.viewport().rect().adjusted(12, 12, -12, -12),
                Qt.AlignCenter | Qt.TextWordWrap,
                self._hint,
            )


class _HintView(QGraphicsView):
    """Previa (janelinha da biblioteca) com texto de estado vazio — mesma
    razao da _HintList."""

    def __init__(self, scene, hint: str) -> None:
        super().__init__(scene)
        self._hint = hint

    def drawForeground(self, painter, rect) -> None:  # noqa: N802
        super().drawForeground(painter, rect)
        if self.scene().items():
            return
        painter.save()
        painter.resetTransform()  # coordenadas do viewport, nao da cena
        painter.setPen(QColor(theme.TEXT_SECONDARY))
        painter.drawText(self.viewport().rect(), Qt.AlignCenter, self._hint)
        painter.restore()


class _ZoomView(QGraphicsView):
    """QGraphicsView com zoom pela roda do mouse, arrasto para deslocar e
    duplo clique para "ajustar a janela". Clique numa peca seleciona e
    arrasta a peca (E3); em area vazia, a maozinha desloca a vista.

    NAO reaproveita o ZoomableGraphicsView da MainWindow de proposito:
    importa-lo aqui traria as ~8 mil linhas do main_window junto, so por
    causa de 15 linhas de zoom. Se o canvas um dia virar componente
    compartilhado, os dois devem convergir — ate la, esta e a duplicacao
    barata e consciente (o estado vazio abaixo espelha o drawForeground de
    la pela mesma razao).
    """

    _MIN, _MAX = 0.02, 60.0

    def __init__(self, scene) -> None:
        super().__init__(scene)
        # zoom no ponto do cursor (e o que o operador espera do Corel)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        # texto-guia do estado vazio ("" = sem guia) + passo ativo na faixa
        # ilustrada (0=Adicionar, 1=Organizar). O dialogo define no _sync.
        self.empty_hint = ""
        self.empty_step = 0

    def drawForeground(self, painter, rect) -> None:  # noqa: N802
        super().drawForeground(painter, rect)
        # estado vazio orientando: sem isto a primeira tela era uma caixa
        # branca muda apontando para um botao desabilitado.
        if not self.empty_hint:
            return
        painter.save()
        painter.resetTransform()  # desenha em coordenadas do viewport
        painter.setPen(QColor(theme.TEXT_MUTED))
        f = painter.font()
        f.setPointSizeF(f.pointSizeF() + 4)
        f.setWeight(QFont.DemiBold)
        painter.setFont(f)
        vr = self.viewport().rect()
        painter.drawText(vr, Qt.AlignCenter, self.empty_hint)
        # os 3 passos do fluxo ilustrados acima do texto, com o atual em
        # destaque (Adicionar -> Organizar -> Exportar)
        strip = faca_icons.cut_steps_pixmap(self.empty_step)
        tr = painter.fontMetrics().boundingRect(vr, Qt.AlignCenter, self.empty_hint)
        painter.drawPixmap(
            int(vr.center().x() - strip.width() / 2),
            max(8, int(tr.top() - strip.height() - 24)),
            strip,
        )
        painter.restore()

    def wheelEvent(self, event) -> None:
        passo = 1.25 if event.angleDelta().y() > 0 else 1 / 1.25
        escala = self.transform().m11() * passo
        if self._MIN <= escala <= self._MAX:
            self.scale(passo, passo)
        event.accept()

    def mousePressEvent(self, event) -> None:
        # clique numa peca: solta a maozinha para o item receber o arrasto
        if event.button() == Qt.LeftButton and isinstance(
            self.itemAt(event.position().toPoint()), _CutPieceItem
        ):
            self.setDragMode(QGraphicsView.NoDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def mouseDoubleClickEvent(self, event) -> None:
        self.fit()
        super().mouseDoubleClickEvent(event)

    def fit(self) -> None:
        """Enquadra a cena inteira. Chamado a cada redesenho — arranjo novo
        volta enquadrado, e o zoom do operador nao sobrevive de proposito
        (o desenho mudou embaixo dele)."""
        rect = self.scene().sceneRect()
        if not rect.isEmpty():
            self.fitInView(rect, Qt.KeepAspectRatio)


class _NestThread(QThread):
    """Roda o packer FORA da thread da UI. O NFP de dezenas de letras leva
    minutos e o 'Tempo de otimizacao' nao limita essa etapa — na thread da
    UI a janela congela e o Windows carimba 'Nao esta respondendo' (visto
    com 44 letras em 21/07)."""

    done = Signal(object, object)  # (layouts | None, excecao | None)

    def __init__(self, parent, compute) -> None:
        super().__init__(parent)
        self._compute = compute

    def run(self) -> None:
        try:
            self.done.emit(self._compute(), None)
        except Exception as exc:  # noqa: BLE001 - a UI mostra, nao decide
            self.done.emit(None, exc)


class CutModeDialog(QDialog):
    """Dialogo do Modo Corte. Dependencias injetaveis para teste headless."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        export_dxf: ExportDxfUseCase | None = None,
        svg_importer: IVectorImporter | None = None,
        pdf_importer: IVectorImporter | None = None,
        text_vectorizer: FontToolsTextVectorizer | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modo Corte (laser/CNC)")
        self.setMinimumSize(900, 600)

        self._svg = svg_importer or SvgVectorImporter()
        self._pdf = pdf_importer or PdfVectorImporter()
        self._text = text_vectorizer or FontToolsTextVectorizer()
        self._export_dxf = export_dxf

        self._pieces: list[CutPiece] = []
        # resultado do ultimo Organizar (o que o preview mostra e o que o
        # Exportar grava). None = ainda nao organizou / lista mudou.
        self._layouts: tuple[Layout, ...] = ()
        self._nested_shapes: list[NestingShape] = []
        self._unplaced: tuple[str, ...] = ()
        self._nest_thread: _NestThread | None = None
        self._tip_index = 0
        self._tip_timer = QTimer(self)
        self._tip_timer.setInterval(4000)
        self._tip_timer.timeout.connect(self._next_tip)
        # retoque manual (E3): item grafico por indice do PlacedItem na chapa
        # mostrada, e a pilha de desfazer (chapa, indice, PlacedItem antigo)
        self._gfx_by_index: dict[tuple[int, int], _CutPieceItem] = {}
        self._undo: list[tuple[int, int, PlacedItem]] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD)
        root.setSpacing(theme.SPACE_MD)
        root.addLayout(self._build_left(), 0)
        root.addLayout(self._build_right(), 1)

        # R gira a peca selecionada; Ctrl+Z desfaz o ultimo arrasto/giro.
        # Tecla solta nao rouba digitacao: campos de texto consomem o
        # ShortcutOverride antes de o atalho disparar.
        QShortcut(QKeySequence("R"), self, activated=self._rotate_selected)
        QShortcut(QKeySequence.Undo, self, activated=self._undo_manip)
        self._sync()

    # -- construcao da UI --------------------------------------------------------

    def _build_left(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(theme.SPACE_SM)

        title = QLabel("Peças")
        title.setProperty("role", "cardTitle")
        col.addWidget(title)

        self._list = _HintList("Nenhuma peça ainda.\nUse Arquivo… ou Texto… abaixo.")
        self._list.setIconSize(QSize(32, 32))  # miniatura da peça por linha
        self._list.setMinimumWidth(260)
        self._list.currentRowChanged.connect(self._sync)
        self._list.currentRowChanged.connect(self._draw_piece_preview)
        col.addWidget(self._list, 1)

        # janelinha da biblioteca: previa dos corpos do arquivo selecionado,
        # independente do nesting — pedido do Philipe em 21/07.
        self._piece_scene = QGraphicsScene(self)
        self._piece_view = _HintView(self._piece_scene, "Prévia da peça selecionada")
        self._piece_view.setRenderHint(QPainter.Antialiasing)
        self._piece_view.setBackgroundBrush(QBrush(QColor(theme.SURFACE_ALT)))
        self._piece_view.setFixedHeight(150)
        self._piece_view.setToolTip("Prévia da peça selecionada")
        col.addWidget(self._piece_view)

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Quantidade"))
        self._qty = QSpinBox()
        self._qty.setRange(1, 999)
        self._qty.valueChanged.connect(self._on_qty_changed)
        qty_row.addWidget(self._qty)
        qty_row.addStretch()
        col.addLayout(qty_row)

        btns = QHBoxLayout()
        self._btn_file = QPushButton("Arquivo...")
        self._btn_file.setIcon(icons.icon("file-plus"))
        self._btn_file.setToolTip("Importar SVG ou PDF vetorial")
        self._btn_file.clicked.connect(self._pick_vector_file)
        self._btn_text = QPushButton("Texto...")
        self._btn_text.setIcon(icons.icon("file-text"))
        self._btn_text.setToolTip("Digitar um texto e converter em curvas")
        self._btn_text.clicked.connect(self._pick_text)
        self._btn_del = QPushButton("Remover")
        self._btn_del.setIcon(icons.icon("trash-2"))
        self._btn_del.clicked.connect(self._remove_current)
        for b in (self._btn_file, self._btn_text, self._btn_del):
            btns.addWidget(b)
        col.addLayout(btns)
        return col

    def _build_right(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(theme.SPACE_SM)

        self._scene = QGraphicsScene(self)
        self._view = _ZoomView(self._scene)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setBackgroundBrush(QBrush(QColor(theme.SURFACE_ALT)))
        self._view.setMinimumHeight(280)
        self._view.setToolTip(
            "Roda do mouse: zoom · arrastar no vazio: deslocar · duplo clique: ajustar\n"
            "Clique numa peça: seleciona e arrasta · R: gira a selecionada · Ctrl+Z: desfaz"
        )
        col.addWidget(self._view, 1)

        self._sheet_pick = QComboBox()
        self._sheet_pick.setToolTip(
            "Chapa das estatísticas (todas aparecem lado a lado no preview)"
        )
        self._sheet_pick.currentIndexChanged.connect(self._draw_preview)
        self._sheet_pick.currentIndexChanged.connect(self._sync)  # stats da chapa
        sheet_row = QHBoxLayout()
        sheet_row.addWidget(QLabel("Chapa"))
        sheet_row.addWidget(self._sheet_pick, 1)
        self._btn_rotate = QPushButton("Girar")
        self._btn_rotate.setIcon(icons.icon("rotate-cw"))
        self._btn_rotate.clicked.connect(self._rotate_selected)
        sheet_row.addWidget(self._btn_rotate)
        col.addLayout(sheet_row)

        self._params = self._build_params()
        col.addWidget(self._params)

        # "imagem de carregamento": barra indeterminada, visivel so enquanto
        # a thread do nesting trabalha.
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        col.addWidget(self._progress)

        self._status = QLabel()
        self._status.setProperty("role", "caption")
        self._status.setWordWrap(True)
        col.addWidget(self._status)

        bar = QDialogButtonBox()
        self._btn_nest = bar.addButton("Organizar", QDialogButtonBox.ActionRole)
        self._btn_nest.setIcon(icons.icon("grid-3x3"))
        self._btn_nest.clicked.connect(self._on_nest)
        self._btn_corel = bar.addButton("Enviar p/ Corel", QDialogButtonBox.ActionRole)
        self._btn_corel.setIcon(icons.icon("send"))
        self._btn_corel.setToolTip(
            "Joga o arranjo organizado na página do CorelDRAW como curvas editáveis"
        )
        self._btn_corel.clicked.connect(self._send_to_corel)
        self._btn_export = bar.addButton("Exportar DXF", QDialogButtonBox.AcceptRole)
        self._btn_export.setIcon(icons.icon("download"))
        self._btn_export.clicked.connect(self._pick_export_path)
        bar.addButton("Fechar", QDialogButtonBox.RejectRole)
        bar.rejected.connect(self.reject)
        col.addWidget(bar)
        return col

    def _build_params(self) -> QGroupBox:
        box = QGroupBox("Material e nesting")
        form = QFormLayout(box)

        def spin(value: float, lo: float, hi: float, step: float = 1.0) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setValue(value)
            s.setSingleStep(step)
            s.setSuffix(" mm")
            s.setDecimals(2)
            # qualquer mudanca invalida o layout calculado (preview mentiria)
            s.valueChanged.connect(self._invalidate)
            return s

        self._width = spin(1000.0, 1.0, 100_000.0, 10.0)
        self._sheet_len = spin(0.0, 0.0, 100_000.0, 10.0)
        self._sheet_len.setToolTip("0 = chapa aberta / bobina (uma folha só)")
        self._gap = spin(2.0, 0.0, 500.0, 0.5)
        self._margin = spin(5.0, 0.0, 500.0, 0.5)
        form.addRow("Largura da chapa", self._width)
        form.addRow("Altura da folha", self._sheet_len)
        form.addRow("Folga entre peças", self._gap)
        form.addRow("Margem da chapa", self._margin)

        # giro estilo 'Fix angle' do eCut. CUIDADO com o instinto "mais fino
        # encaixa melhor": medido em 22/07 (trabalho 150mm, chapa 600, 10s),
        # 45°/15° encaixaram PIOR que 90° — mais rotações consomem o orçamento
        # do genético em poucas avaliações. O padrão segue Reto (90°).
        self._rotate_mode = QComboBox()
        self._rotate_mode.setIconSize(QSize(26, 26))
        for label, step in _ROTATE_MODES:
            self._rotate_mode.addItem(
                QIcon(_rotate_pixmap(step, theme.TEXT_MUTED, theme.ACCENT)), label, step
            )
        self._rotate_mode.setCurrentIndex(1)  # Reto (90°)
        self._rotate_mode.setToolTip(
            "Ângulos que o encaixe pode tentar. Reto (90°) costuma render mais:\n"
            "passos finos multiplicam as rotações e, no tempo padrão, encaixam\n"
            "pior — se usar, aumente também o 'Tempo de otimização'."
        )
        self._rotate_mode.currentIndexChanged.connect(self._invalidate)
        form.addRow("Giro das peças", self._rotate_mode)

        self._seconds = QDoubleSpinBox()
        self._seconds.setRange(0.5, 600.0)
        self._seconds.setValue(10.0)
        self._seconds.setSuffix(" s")
        self._seconds.setDecimals(1)
        self._seconds.setToolTip("Tempo do algoritmo genético — mais tempo, melhor encaixe")
        self._seconds.valueChanged.connect(self._invalidate)
        form.addRow("Tempo de otimização", self._seconds)

        # "Allow inside" do mercado: enche o miolo do "O", o vão do "8". Ligado
        # por padrão — é material que hoje vira sucata. Sai no DXF de dentro
        # para fora (a peça hospedada corta antes do contorno que a envolve).
        self._inside = QCheckBox("Preencher furos (peça dentro de peça)")
        self._inside.setIcon(QIcon(_inside_pixmap(theme.CUT, theme.ACCENT)))
        self._inside.setIconSize(QSize(26, 26))
        self._inside.setChecked(True)
        self._inside.setToolTip(
            "Aproveita o vão interno das peças (miolo do 'O') para encaixar peças menores"
        )
        self._inside.stateChanged.connect(self._invalidate)
        form.addRow("", self._inside)
        return box

    # -- entrada de pecas --------------------------------------------------------

    def add_vector_file(self, path: str) -> CutPiece:
        """Importa SVG/PDF pela extensao. Publico e sem QFileDialog para o
        teste headless chamar direto."""
        importer = self._pdf if path.lower().endswith(".pdf") else self._svg
        shapes = importer.load(path)
        if not shapes:
            raise ValidationError(f"Nenhuma forma fechada encontrada em {os.path.basename(path)}.")
        return self._add(CutPiece(os.path.basename(path), tuple(shapes)))

    def add_text(self, text: str, font_path: str, size_mm: float) -> CutPiece:
        """Texto digitado -> curvas. Cada corpo de cada letra vira uma peca no
        nesting (o 'i' entra como haste + pingo, soltos)."""
        glyphs = self._text.vectorize(text, font_path, size_mm)
        bodies = tuple(shape for glyph in glyphs for shape in glyph.shapes)
        if not bodies:
            raise ValidationError("O texto não gerou nenhuma curva.")
        return self._add(CutPiece(f'"{text}"', bodies))

    def _add(self, piece: CutPiece) -> CutPiece:
        self._pieces.append(piece)
        self._list.addItem(QListWidgetItem(self._piece_icon(piece), self._label(piece)))
        self._list.setCurrentRow(len(self._pieces) - 1)
        self._invalidate()
        return piece

    @staticmethod
    def _label(piece: CutPiece) -> str:
        return f"{piece.name}  ·  {len(piece.shapes)} corpo(s)  x{piece.quantity}"

    @classmethod
    def _piece_icon(cls, piece: CutPiece, size: int = 32) -> QIcon:
        """Miniatura da própria peça para a lista: todos os corpos dentro do
        quadradinho, furos vazados — mesma receita da prévia grande."""
        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        for shape in piece.shapes:
            path.addPath(
                cls._rings_path([ring.vertices for ring in (shape.outer, *shape.holes)])
            )
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        rect = path.boundingRect()
        if rect.width() > 0 and rect.height() > 0:
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            pad = 3
            scale = min((size - 2 * pad) / rect.width(), (size - 2 * pad) / rect.height())
            p.translate(size / 2.0, size / 2.0)
            p.scale(scale, scale)
            p.translate(-rect.center().x(), -rect.center().y())
            pen = QPen(QColor(theme.ACCENT))
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(QBrush(QColor(theme.ACCENT_SOFT)))
            p.drawPath(path)
            p.end()
        return QIcon(pm)

    def open_with_file(self, path: str) -> None:
        """Fluxo da macro do CorelDRAW (--modo-corte): importa o arquivo e JA
        dispara o Organizar em thread — a janela abre por cima do Corel
        trabalhando, como o eCut. Erro de importacao vira aviso (a janela
        abre vazia; o operador tenta pelo botao Arquivo...)."""
        self._guarded(lambda: self.add_vector_file(path))
        if self._pieces:
            self._on_nest()

    def _pick_vector_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar vetor", "", _VECTOR_FILTER)
        if path:
            self._guarded(lambda: self.add_vector_file(path))

    def _pick_text(self) -> None:
        dlg = _TextDialog(self)
        if dlg.exec() == QDialog.Accepted:
            text, font_path, size = dlg.values()
            self._guarded(lambda: self.add_text(text, font_path, size))

    def _remove_current(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        self._pieces.pop(row)
        self._list.takeItem(row)
        self._invalidate()

    def _on_qty_changed(self, value: int) -> None:
        row = self._list.currentRow()
        if row < 0 or self._pieces[row].quantity == value:
            return
        self._pieces[row].quantity = value
        self._list.item(row).setText(self._label(self._pieces[row]))
        self._invalidate()

    # -- nesting -----------------------------------------------------------------

    def _packer(self) -> TrueShapePacker:
        # approximation 0.5mm: simplifica o contorno SO para o calculo do NFP
        # (o DXF sai com o contorno original — garantia da Fase 4). Com o 0.1
        # padrao, um trabalho de dezenas de letras estourava o orcamento na
        # PRIMEIRA avaliacao e o genetico devolvia o chute inicial sem girar
        # nada; com 0.5 ele itera de verdade (benchmark 21/07: 21s -> 10s e
        # passa a girar quando compensa, ex. 24/36 letras em chapa estreita).
        return TrueShapePacker(
            gap=self._gap.value(),
            margin=self._margin.value(),
            genetics_time=self._seconds.value(),
            approximation=0.5,
            inside_check=self._inside.isChecked(),
        )

    def _use_case(self) -> RunTrueShapeNestingUseCase:
        if self._export_dxf is None:
            # import tardio: a camada de apresentacao so amarra infraestrutura
            # quando o usuario realmente vai exportar.
            from app.infrastructure.exporters.dxf_exporter import DxfExporter

            self._export_dxf = ExportDxfUseCase(DxfExporter())
        return RunTrueShapeNestingUseCase(self._packer(), self._export_dxf)

    def _all_shapes(self) -> list[NestingShape]:
        """Lista achatada com ids continuos entre as entradas — 'start' evita
        que dois lotes colidam no mesmo shape-0001. As COPIAS (quantidade)
        repetem o MESMO id/contorno de proposito: o cache de NFP do motor e
        por (id, rotacao), entao 20 copias custam o NFP de UMA (precondicao
        documentada do TrueShapePacker)."""
        step = self._rotate_mode.currentData()
        rotations = tuple(float(a) for a in range(0, 360, step)) if step else (0.0,)
        out: list[NestingShape] = []
        for piece in self._pieces:
            base = to_nesting_shapes(piece.shapes, rotations=rotations, start=len(out) + 1)
            for _ in range(piece.quantity):
                out.extend(base)
        return out

    def _nest_inputs(self) -> tuple[list[NestingShape], Material, float]:
        """Valida e congela as entradas ANTES de sair da thread da UI —
        a thread do nesting nao pode ler widget."""
        shapes = self._all_shapes()
        if not shapes:
            raise ValidationError("Adicione ao menos uma peça (arquivo ou texto).")
        return shapes, Material("Corte", self._width.value()), self._sheet_len.value()

    @staticmethod
    def _compute(
        uc: RunTrueShapeNestingUseCase,
        shapes: list[NestingShape],
        material: Material,
        length: float,
    ) -> tuple[Layout, ...]:
        """Parte pesada, segura para rodar em thread (so dominio, zero UI)."""
        if length > 0:
            return tuple(uc.pack_sheets(shapes, material, length))
        return (uc.pack(shapes, material),)

    def _on_nest(self) -> None:
        """Botao Organizar: mesmo calculo do nest(), mas numa thread com a
        barra de progresso — a janela continua respondendo. Erro vira aviso;
        o metodo publico continua levantando para o teste verificar."""
        if self._nest_thread is not None:
            return
        try:
            shapes, material, length = self._nest_inputs()
        except Exception as exc:  # noqa: BLE001 - fronteira de UI
            QMessageBox.warning(self, "Modo Corte", str(exc))
            return
        uc = self._use_case()
        self._set_busy(True)
        self._nest_thread = _NestThread(self, lambda: self._compute(uc, shapes, material, length))
        self._nest_thread.done.connect(
            lambda layouts, error: self._on_nest_done(shapes, layouts, error)
        )
        self._nest_thread.finished.connect(self._nest_thread.deleteLater)
        self._nest_thread.start()

    def _on_nest_done(self, shapes, layouts, error) -> None:
        self._nest_thread = None
        self._set_busy(False)
        if error is not None:
            QMessageBox.warning(self, "Modo Corte", str(error))
            return
        self._apply_nest(shapes, layouts)

    def nest(self) -> None:
        """Organizar sincrono (testes/automacao): calcula os layouts e
        desenha. Nao grava nada."""
        shapes, material, length = self._nest_inputs()
        self._apply_nest(shapes, self._compute(self._use_case(), shapes, material, length))

    def _apply_nest(self, shapes: list[NestingShape], layouts: tuple[Layout, ...]) -> None:
        self._nested_shapes = shapes
        self._layouts = layouts
        self._undo.clear()  # arranjo novo: retoques antigos nao fazem sentido
        # multiset, nao set: copias compartilham o id, entao "1 de 3 copias
        # colocada" precisa contar as outras 2 como fora.
        placed = Counter(item.artwork_id for layout in self._layouts for item in layout.items)
        unplaced: list[str] = []
        for shape in shapes:
            if placed.get(shape.artwork_id, 0) > 0:
                placed[shape.artwork_id] -= 1
            else:
                unplaced.append(shape.artwork_id)
        self._unplaced = tuple(unplaced)
        self._sheet_pick.blockSignals(True)
        self._sheet_pick.clear()
        self._sheet_pick.addItems(
            [
                f"Chapa {i + 1} ({layout.item_count} peça(s))"
                for i, layout in enumerate(self._layouts)
            ]
        )
        self._sheet_pick.blockSignals(False)
        self._sheet_pick.setCurrentIndex(0)
        self._draw_preview()
        self._sync()

    def _set_busy(self, busy: bool) -> None:
        """Trava a UI enquanto a thread trabalha: mexer em parametro no meio
        do calculo dessincronizaria preview e resultado."""
        self._progress.setVisible(busy)
        for widget in (
            self._list,
            self._qty,
            self._btn_file,
            self._btn_text,
            self._btn_del,
            self._params,
            self._sheet_pick,
            self._btn_rotate,
            self._btn_nest,
            self._btn_export,
            self._btn_corel,
        ):
            widget.setEnabled(not busy)
        if busy:
            bodies = sum(piece.body_count for piece in self._pieces)
            self._status.setText(
                f"Organizando {bodies} corpo(s)… a janela continua respondendo."
            )
            # o guia "Clique em Organizar" sairia por cima do calculo em curso
            self._view.empty_hint = ""
            self._view.viewport().update()
            self._tip_index = 0
            self._tip_timer.start()
        else:
            self._tip_timer.stop()
            self._sync()

    def _next_tip(self) -> None:
        self._status.setText(_NEST_TIPS[self._tip_index % len(_NEST_TIPS)])
        self._tip_index += 1

    def _invalidate(self) -> None:
        """Lista/parametro mudou: o layout calculado nao vale mais. Limpa o
        preview em vez de mostrar um desenho que nao corresponde ao DXF."""
        self._layouts = ()
        self._nested_shapes = []
        self._unplaced = ()
        self._undo.clear()
        self._gfx_by_index = {}
        self._sheet_pick.clear()
        self._scene.clear()
        self._sync()

    # -- preview -----------------------------------------------------------------

    def _draw_preview(self, *_, fit: bool = True) -> None:
        """Redesenha TODAS as chapas, lado a lado (estilo eCut) — o que nao
        coube na Chapa 1 aparece na Chapa 2 ao lado, nunca escondido atras do
        combo (trabalho real de 23/07: as letras grandes 'sumiam' porque
        estavam na chapa 2 e o preview mostrava so uma chapa por vez). 'fit'
        falso preserva o zoom do operador (usado no desfazer, que so move
        uma peca)."""
        self._scene.clear()
        self._gfx_by_index = {}
        if not self._layouts:
            return
        by_id = {s.artwork_id: s for s in self._nested_shapes}
        pen = QPen(QColor(theme.ACCENT))
        pen.setCosmetic(True)  # espessura constante em qualquer zoom
        fill = QBrush(QColor(theme.ACCENT_SOFT))
        dx = 0.0
        for si, layout in enumerate(self._layouts):
            length = layout.used_length or self._sheet_len.value() or 1.0
            self._scene.addRect(
                QRectF(dx, 0, layout.material.width, length),
                QPen(QColor(theme.BORDER_STRONG)),
                QBrush(QColor(theme.SURFACE)),
            )
            self._draw_sheet_limits(layout, length, dx)
            # mesmo retangulo vermelho do _draw_sheet_limits: limite do
            # arrasto — cada peca fica presa na PROPRIA chapa
            bounds = QRectF(dx, 0, layout.material.width, self._sheet_len.value() or length)
            for i, item in enumerate(layout.items):
                path = self._path(by_id[item.artwork_id], item)
                path.translate(dx, 0.0)
                gfx = _CutPieceItem(
                    path, i, bounds, self._on_piece_moved, sheet=si, dx=dx
                )
                gfx.setPen(pen)
                gfx.setBrush(fill)
                self._scene.addItem(gfx)
                self._gfx_by_index[(si, i)] = gfx
            dx += layout.material.width + _PREVIEW_SHEET_GAP_MM
        self._scene.setSceneRect(self._scene.itemsBoundingRect())
        if fit:
            self._view.fit()

    # -- retoque manual (E3): mover/girar escrevem em self._layouts --------------

    def _shape(self, artwork_id: str) -> NestingShape:
        return next(s for s in self._nested_shapes if s.artwork_id == artwork_id)

    def _sheet_index(self) -> int:
        return min(max(self._sheet_pick.currentIndex(), 0), len(self._layouts) - 1)

    def _commit_item(self, sheet: int, index: int, new_item: PlacedItem) -> None:
        """PONTO CENTRAL da E3: grava o PlacedItem manipulado em
        self._layouts. Preview, Exportar DXF, Enviar p/ Corel e SVG leem
        daqui, entao todos enxergam o retoque sem caminho novo de
        exportacao."""
        layout = self._layouts[sheet]
        self._undo.append((sheet, index, layout.items[index]))
        items = list(layout.items)
        items[index] = new_item
        self._layouts = (
            *self._layouts[:sheet],
            replace(layout, items=tuple(items)),
            *self._layouts[sheet + 1 :],
        )
        self._sync()  # stats da chapa (bloco/aproveitamento) mudam junto

    def _refresh_gfx(self, gfx: _CutPieceItem, item: PlacedItem) -> None:
        """Reconstroi o caminho na posicao gravada e zera o delta — a cena
        volta a ser espelho fiel de self._layouts."""
        path = self._path(self._shape(item.artwork_id), item)
        path.translate(gfx.dx, 0.0)  # a chapa da peca fica deslocada na cena
        gfx.setPath(path)
        gfx.setPos(QPointF(0, 0))

    def _on_piece_moved(self, gfx: _CutPieceItem) -> None:
        """Soltou o arrasto: pos() e o delta em mm (cena e layout compartilham
        a escala)."""
        sheet = gfx.sheet
        old = self._layouts[sheet].items[gfx.index]
        delta = gfx.pos()
        new_item = replace(
            old,
            position=Point2D(old.position.x + delta.x(), old.position.y + delta.y()),
            rotation=float(old.rotation),
        )
        self._commit_item(sheet, gfx.index, new_item)
        self._refresh_gfx(gfx, new_item)

    def _rotate_selected(self) -> None:
        """Tecla R / botao Girar: gira a(s) peca(s) selecionada(s) no passo do
        combo 'Giro das peças' (90° quando o combo esta em 'Sem giro' — o
        giro manual nao pode ficar refem do parametro do nesting)."""
        if not self._layouts:
            return
        for gfx in self._scene.selectedItems():
            if isinstance(gfx, _CutPieceItem):
                self._rotate_piece(gfx)

    def _rotate_piece(self, gfx: _CutPieceItem) -> None:
        sheet = gfx.sheet
        old = self._layouts[sheet].items[gfx.index]
        step = self._rotate_mode.currentData() or 90
        degrees = (float(old.rotation) + step) % 360.0
        shape = self._shape(old.artwork_id)
        # gira em torno do CENTRO atual da peca (o que o operador espera);
        # position e o canto min do bbox girado (convencao do placed_cut_contours)
        outer = placed_cut_contours(shape, old)[0]
        cx = outer.origin.x + outer.size.width / 2
        cy = outer.origin.y + outer.size.height / 2
        bb = shape.contour.rotated(degrees).bounding_box
        # bounds esta em coords da CENA (chapa deslocada); a conta do clamp e
        # em coords da CHAPA, entao volta o deslocamento antes
        b = gfx.bounds.translated(-gfx.dx, 0.0)
        x = min(max(cx - bb.width / 2, b.left()), max(b.left(), b.right() - bb.width))
        y = min(max(cy - bb.height / 2, b.top()), max(b.top(), b.bottom() - bb.height))
        new_item = replace(old, position=Point2D(x, y), rotation=degrees)
        self._commit_item(sheet, gfx.index, new_item)
        self._refresh_gfx(gfx, new_item)

    def _undo_manip(self) -> None:
        """Ctrl+Z do retoque manual. So do retoque: o Organizar recomeca a
        historia (a pilha e limpa junto com os layouts)."""
        if not self._undo or not self._layouts:
            return
        sheet, index, old_item = self._undo.pop()
        layout = self._layouts[sheet]
        items = list(layout.items)
        items[index] = old_item
        self._layouts = (
            *self._layouts[:sheet],
            replace(layout, items=tuple(items)),
            *self._layouts[sheet + 1 :],
        )
        # todas as chapas estao na cena: o desfazer atualiza a peca direto,
        # sem precisar trocar de chapa no combo
        gfx = self._gfx_by_index.get((sheet, index))
        if gfx is not None:
            self._refresh_gfx(gfx, old_item)
        self._sync()

    def _draw_sheet_limits(self, layout: Layout, length: float, dx: float = 0.0) -> None:
        """Linha VERMELHA da area configurada + tracejada da margem.

        Sem isso o operador nao tem como saber se o arranjo cabe no que ele
        pediu: o retangulo branco mostra o comprimento USADO, e com "Altura da
        folha" 0 (bobina) esse comprimento nao tem nada a ver com o
        configurado. Pedido do Philipe em 22/07, depois de olhar um preview e
        nao saber onde ficava a chapa dele.

        Em bobina (altura 0) o que esta configurado e SO a largura, entao o
        retangulo vermelho acompanha o comprimento usado — quem manda ali e a
        largura, e as duas linhas verticais mostram o limite.
        """
        altura = self._sheet_len.value() or length
        vermelho = QPen(QColor(theme.ERROR))
        vermelho.setCosmetic(True)
        self._scene.addRect(
            QRectF(dx, 0, layout.material.width, altura), vermelho, QBrush(Qt.NoBrush)
        )

        margem = self._margin.value()
        util_w = layout.material.width - 2 * margem
        util_h = altura - 2 * margem
        if margem > 0 and util_w > 0 and util_h > 0:
            tracejada = QPen(QColor(theme.ERROR))
            tracejada.setCosmetic(True)
            tracejada.setStyle(Qt.DashLine)
            self._scene.addRect(
                QRectF(dx + margem, margem, util_w, util_h), tracejada, QBrush(Qt.NoBrush)
            )

    @staticmethod
    def _path(shape: NestingShape, item) -> QPainterPath:
        """Mesma reconstrucao do DXF (placed_cut_contours) — preview e
        exportacao NAO podem divergir."""
        return CutModeDialog._rings_path(
            [contour.points for contour in placed_cut_contours(shape, item)]
        )

    @staticmethod
    def _rings_path(rings) -> QPainterPath:
        """Aneis -> QPainterPath: cada anel vira subpath e o preenchimento
        par-impar abre os furos."""
        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        for points in rings:
            path.moveTo(points[0].x, points[0].y)
            for point in points[1:]:
                path.lineTo(point.x, point.y)
            path.closeSubpath()
        return path

    def _draw_piece_preview(self) -> None:
        """Janelinha da biblioteca: os corpos do arquivo selecionado, com
        furos vazados, independente do nesting."""
        self._piece_scene.clear()
        row = self._list.currentRow()
        if row < 0:
            return
        pen = QPen(QColor(theme.ACCENT))
        pen.setCosmetic(True)
        fill = QBrush(QColor(theme.ACCENT_SOFT))
        for shape in self._pieces[row].shapes:
            rings = [ring.vertices for ring in (shape.outer, *shape.holes)]
            self._piece_scene.addPath(self._rings_path(rings), pen, fill)
        self._piece_scene.setSceneRect(self._piece_scene.itemsBoundingRect())
        self._piece_view.fitInView(self._piece_scene.sceneRect(), Qt.KeepAspectRatio)

    # -- exportacao --------------------------------------------------------------

    def export(self, output_path: str) -> NestingExportResult:
        """Grava os layouts JA calculados (nunca recalcula: ver docstring do
        modulo)."""
        if not self._layouts:
            raise ValidationError("Clique em Organizar antes de exportar.")
        return self._use_case().export_layouts(
            self._nested_shapes,
            self._layouts,
            output_path,
            per_sheet=len(self._layouts) > 1,
        )

    def export_svg(self, output_path: str, sheet_index: int | None = None) -> str:
        """SVG do layout organizado (a chapa do preview, ou sheet_index) —
        mesma reconstrucao do DXF, em curvas magenta, para voltar ao Corel."""
        if not self._layouts:
            raise ValidationError("Clique em Organizar antes de enviar.")
        index = self._sheet_pick.currentIndex() if sheet_index is None else sheet_index
        index = min(max(index, 0), len(self._layouts) - 1)
        layout = self._layouts[index]
        by_id = {s.artwork_id: s for s in self._nested_shapes}
        pieces = [placed_cut_contours(by_id[item.artwork_id], item) for item in layout.items]
        height = layout.used_length or self._sheet_len.value() or 1.0
        return write_layout_svg(pieces, layout.material.width, height, output_path)

    def _send_to_corel(self) -> None:
        """Botao 'Enviar p/ Corel' (Apply do eCut): grava o SVG do arranjo e
        a ponte COM importa na pagina ativa do CorelDRAW."""

        def run() -> None:
            svg = self.export_svg(os.path.join(tempfile.gettempdir(), "printnest_layout.svg"))
            send_file_to_corel(svg)
            QMessageBox.information(
                self,
                "Modo Corte",
                "Arranjo enviado para a página do CorelDRAW (curvas magenta).",
            )

        self._guarded(run)

    def _pick_export_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar DXF", "corte.dxf", "DXF (*.dxf)")
        if not path:
            return

        def run() -> None:
            result = self.export(path)
            QMessageBox.information(
                self,
                "Modo Corte",
                "DXF gerado:\n" + "\n".join(result.dxf_paths),
            )

        self._guarded(run)

    # -- utilidades --------------------------------------------------------------

    def reject(self) -> None:
        """Fechar com a thread viva destruiria o QThread no meio do calculo
        (crash). Segura o fechamento e avisa."""
        if self._nest_thread is not None:
            self._status.setText("Aguarde terminar de organizar para fechar.")
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self._nest_thread is not None:
            event.ignore()
            self._status.setText("Aguarde terminar de organizar para fechar.")
            return
        super().closeEvent(event)

    def _guarded(self, action) -> None:
        """Erro de dominio/importacao vira caixa de aviso — nunca traceback na
        cara do operador."""
        try:
            action()
        except Exception as exc:  # noqa: BLE001 - fronteira de UI
            QMessageBox.warning(self, "Modo Corte", str(exc))

    def _sync(self) -> None:
        row = self._list.currentRow()
        has_piece = row >= 0
        self._qty.setEnabled(has_piece)
        self._btn_del.setEnabled(has_piece)
        self._btn_del.setToolTip(
            "Tira a peça selecionada da lista"
            if has_piece
            else "Disponível com uma peça selecionada na lista"
        )
        if has_piece:
            self._qty.blockSignals(True)
            self._qty.setValue(self._pieces[row].quantity)
            self._qty.blockSignals(False)
        organized = bool(self._layouts)
        self._btn_nest.setEnabled(bool(self._pieces))
        # botao apagado e MUDO faz o usuario achar que travou: o tooltip do
        # desabilitado sempre diz o que o destrava.
        self._btn_nest.setToolTip(
            "Encaixa as peças na chapa (nesting)"
            if self._pieces
            else "Disponível depois de adicionar uma peça (arquivo ou texto)"
        )
        for btn, hint in (
            (self._btn_export, "Grava o arranjo organizado em DXF"),
            (
                self._btn_corel,
                "Joga o arranjo organizado na página do CorelDRAW como curvas editáveis",
            ),
            (self._btn_rotate, "Gira a peça selecionada no preview (tecla R)"),
        ):
            btn.setEnabled(organized)
            btn.setToolTip(hint if organized else "Disponível depois de Organizar")
        self._sync_primary()
        self._sync_empty_hint()
        self._status.setText(self._status_text())

    def _sync_primary(self) -> None:
        """Enfase de acao PRIMARIA no botao do passo atual: Organizar quando
        ha peca solta, Exportar quando ja organizou. Token accent do
        theme.qss — trocar a property exige repolir o estilo."""
        primary = self._btn_export if self._layouts else self._btn_nest
        for btn in (self._btn_nest, self._btn_export):
            accent = "true" if btn is primary else "false"
            if btn.property("accent") != accent:
                btn.setProperty("accent", accent)
                btn.style().unpolish(btn)
                btn.style().polish(btn)

    def _sync_empty_hint(self) -> None:
        """Texto-guia do preview vazio: sempre o proximo passo POSSIVEL,
        nunca um botao desabilitado."""
        if not self._pieces:
            hint, step = "Adicione um arquivo (SVG/PDF) ou um texto", 0
        elif not self._layouts:
            hint, step = "Clique em Organizar", 1
        else:
            hint, step = "", 0  # organizado: o arranjo fala por si
        if (hint, step) != (self._view.empty_hint, self._view.empty_step):
            self._view.empty_hint = hint
            self._view.empty_step = step
            self._view.viewport().update()

    def _status_text(self) -> str:
        bodies = sum(piece.body_count for piece in self._pieces)
        if not self._pieces:
            # NAO dizer "clique em Organizar" aqui: o botao esta desabilitado
            return "Adicione um arquivo (SVG/PDF) ou um texto para começar."
        if not self._layouts:
            return f"{bodies} corpo(s) na lista. Clique em Organizar."
        placed = sum(layout.item_count for layout in self._layouts)
        index = min(max(self._sheet_pick.currentIndex(), 0), len(self._layouts) - 1)
        text = (
            f"{placed} de {bodies} corpo(s) encaixados em {len(self._layouts)} chapa(s). "
            + self._sheet_stats(self._layouts[index])
        )
        if self._unplaced:
            text += f" {len(self._unplaced)} não coube(ram) — aumente a chapa ou a folha."
        return text + " Arraste peças para ajustar; R gira a selecionada."

    def _sheet_stats(self, layout: Layout) -> str:
        """Numeros da chapa mostrada, estilo eCut ('993 x 635 mm 75% /
        Usage 38%'): tamanho do bloco ocupado, quanto da chapa ele toma e o
        aproveitamento (area liquida das pecas sobre a area da chapa)."""
        if not layout.items or layout.used_length <= 0:
            return ""
        by_id = {s.artwork_id: s for s in self._nested_shapes}
        min_x = min_y = float("inf")
        max_x = max_y = 0.0
        pieces_area = 0.0
        for item in layout.items:
            shape = by_id[item.artwork_id]
            # rotacao nao muda area; bbox vem do outer reconstruido
            pieces_area += shape.contour.area - sum(h.area for h in shape.holes)
            outer = placed_cut_contours(shape, item)[0]
            origin, size = outer.origin, outer.size
            min_x = min(min_x, origin.x)
            min_y = min(min_y, origin.y)
            max_x = max(max_x, origin.x + size.width)
            max_y = max(max_y, origin.y + size.height)
        block_w, block_h = max_x - min_x, max_y - min_y
        sheet_area = layout.material.width * layout.used_length
        return (
            f"Bloco {block_w:.0f} × {block_h:.0f} mm "
            f"({block_w * block_h / sheet_area:.0%} da chapa) · "
            f"aproveitamento {pieces_area / sheet_area:.0%}."
        )


class _TextDialog(QDialog):
    """Texto + fonte + corpo, para a vetorizacao da Fase 3C."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Texto em curvas")
        form = QFormLayout(self)

        self._text = QLineEdit()
        form.addRow("Texto", self._text)

        self._font = QLineEdit()
        self._font.setPlaceholderText("Arquivo .ttf / .otf")
        pick = QPushButton("Procurar...")
        pick.clicked.connect(self._pick_font)
        row = QHBoxLayout()
        row.addWidget(self._font, 1)
        row.addWidget(pick)
        holder = QWidget()
        holder.setLayout(row)
        form.addRow("Fonte", holder)

        self._size = QDoubleSpinBox()
        self._size.setRange(1.0, 5000.0)
        self._size.setValue(50.0)
        self._size.setSuffix(" mm")
        form.addRow("Corpo", self._size)

        bar = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bar.accepted.connect(self.accept)
        bar.rejected.connect(self.reject)
        form.addRow(bar)

    def _pick_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Fonte", "", "Fontes (*.ttf *.otf)")
        if path:
            self._font.setText(path)

    def values(self) -> tuple[str, str, float]:
        return self._text.text(), self._font.text(), self._size.value()
