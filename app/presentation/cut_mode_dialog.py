"""Modo Corte (laser/CNC): dialogo do nesting true-shape (Fase 5).

Vive FORA da MainWindow de proposito. O canvas do modo Impressao desenha
PieceItem, que e um QGraphicsRectItem — so sabe retangulo. O modo Corte
precisa mostrar o CONTORNO real encaixado, entao tem cena propria aqui e nao
encosta em nada do fluxo de impressao.

Fluxo: importar SVG/PDF/texto (Fase 3) -> lista de pecas com quantidade ->
Organizar (TrueShapePacker, Fase 2) -> preview -> Exportar DXF (Fase 4).

CRITICO: Organizar guarda os Layouts e Exportar grava ESSES layouts
(export_layouts), nunca recalcula. Com genetics_time o genetico nao e
deterministico — recalcular faria o DXF sair diferente do preview.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
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
from app.domain.geometry.polygon_with_holes import PolygonWithHoles
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.nesting.true_shape import NestingShape, TrueShapePacker
from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter
from app.infrastructure.importers.svg_vector_importer import SvgVectorImporter
from app.infrastructure.text.fonttools_text_vectorizer import FontToolsTextVectorizer
from app.presentation import theme
from app.shared.errors import ValidationError

_VECTOR_FILTER = "Vetores (*.svg *.pdf);;SVG (*.svg);;PDF (*.pdf)"

# (rotulo, passo em graus) do combo de giro; passo 0 = sem giro.
_ROTATE_MODES = (
    ("Sem giro", 0),
    ("Reto (90°)", 90),
    ("Fino (45°)", 45),
    ("Muito fino (15°)", 15),
)

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
)


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

        root = QHBoxLayout(self)
        root.setContentsMargins(theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD)
        root.setSpacing(theme.SPACE_MD)
        root.addLayout(self._build_left(), 0)
        root.addLayout(self._build_right(), 1)
        self._sync()

    # -- construcao da UI --------------------------------------------------------

    def _build_left(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(theme.SPACE_SM)

        title = QLabel("Peças")
        title.setProperty("role", "cardTitle")
        col.addWidget(title)

        self._list = QListWidget()
        self._list.setMinimumWidth(260)
        self._list.currentRowChanged.connect(self._sync)
        self._list.currentRowChanged.connect(self._draw_piece_preview)
        col.addWidget(self._list, 1)

        # janelinha da biblioteca: previa dos corpos do arquivo selecionado,
        # independente do nesting — pedido do Philipe em 21/07.
        self._piece_scene = QGraphicsScene(self)
        self._piece_view = QGraphicsView(self._piece_scene)
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
        self._btn_file.setToolTip("Importar SVG ou PDF vetorial")
        self._btn_file.clicked.connect(self._pick_vector_file)
        self._btn_text = QPushButton("Texto...")
        self._btn_text.setToolTip("Digitar um texto e converter em curvas")
        self._btn_text.clicked.connect(self._pick_text)
        self._btn_del = QPushButton("Remover")
        self._btn_del.clicked.connect(self._remove_current)
        for b in (self._btn_file, self._btn_text, self._btn_del):
            btns.addWidget(b)
        col.addLayout(btns)
        return col

    def _build_right(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(theme.SPACE_SM)

        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setBackgroundBrush(QBrush(QColor(theme.SURFACE_ALT)))
        self._view.setMinimumHeight(280)
        col.addWidget(self._view, 1)

        self._sheet_pick = QComboBox()
        self._sheet_pick.setToolTip("Chapa mostrada no preview")
        self._sheet_pick.currentIndexChanged.connect(self._draw_preview)
        self._sheet_pick.currentIndexChanged.connect(self._sync)  # stats da chapa
        sheet_row = QHBoxLayout()
        sheet_row.addWidget(QLabel("Chapa"))
        sheet_row.addWidget(self._sheet_pick, 1)
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
        self._btn_nest.clicked.connect(self._on_nest)
        self._btn_export = bar.addButton("Exportar DXF", QDialogButtonBox.AcceptRole)
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

        # giro estilo 'Fix angle' do eCut: quanto mais fino o passo, melhor o
        # entrelacamento das pecas — e mais demorado o calculo.
        self._rotate_mode = QComboBox()
        for label, step in _ROTATE_MODES:
            self._rotate_mode.addItem(label, step)
        self._rotate_mode.setCurrentIndex(1)  # Reto (90°)
        self._rotate_mode.setToolTip(
            "Passo do giro das peças: mais fino encaixa melhor, porém demora mais"
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
        self._list.addItem(QListWidgetItem(self._label(piece)))
        self._list.setCurrentRow(len(self._pieces) - 1)
        self._invalidate()
        return piece

    @staticmethod
    def _label(piece: CutPiece) -> str:
        return f"{piece.name}  ·  {len(piece.shapes)} corpo(s)  x{piece.quantity}"

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
            self._btn_nest,
            self._btn_export,
        ):
            widget.setEnabled(not busy)
        if busy:
            bodies = sum(piece.body_count for piece in self._pieces)
            self._status.setText(
                f"Organizando {bodies} corpo(s)… a janela continua respondendo."
            )
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
        self._sheet_pick.clear()
        self._scene.clear()
        self._sync()

    # -- preview -----------------------------------------------------------------

    def _draw_preview(self) -> None:
        self._scene.clear()
        index = self._sheet_pick.currentIndex()
        if not self._layouts or not 0 <= index < len(self._layouts):
            return
        layout = self._layouts[index]
        length = layout.used_length or self._sheet_len.value() or 1.0
        self._scene.addRect(
            QRectF(0, 0, layout.material.width, length),
            QPen(QColor(theme.BORDER_STRONG)),
            QBrush(QColor(theme.SURFACE)),
        )
        by_id = {s.artwork_id: s for s in self._nested_shapes}
        pen = QPen(QColor(theme.ACCENT))
        pen.setCosmetic(True)  # espessura constante em qualquer zoom
        fill = QBrush(QColor(theme.ACCENT_SOFT))
        for item in layout.items:
            self._scene.addPath(self._path(by_id[item.artwork_id], item), pen, fill)
        self._scene.setSceneRect(self._scene.itemsBoundingRect())
        self._view.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

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
        if has_piece:
            self._qty.blockSignals(True)
            self._qty.setValue(self._pieces[row].quantity)
            self._qty.blockSignals(False)
        self._btn_nest.setEnabled(bool(self._pieces))
        self._btn_export.setEnabled(bool(self._layouts))
        self._status.setText(self._status_text())

    def _status_text(self) -> str:
        bodies = sum(piece.body_count for piece in self._pieces)
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
        return text

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
