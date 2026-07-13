"""Personalizar Interface — diálogo do Theme Engine (live preview).

Toda mudança aplica NA HORA (sem fechar, sem reiniciar). Cancelar devolve o
estado de quando o diálogo abriu; Restaurar padrão volta ao PrintNest Original.
Exportar/Importar salvam temas em JSON (ex.: "Minha Empresa.json").
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.presentation import theme
from app.presentation.themes import palettes
from app.presentation.themes.manager import AUTO, ThemeManager


def _swatch_css(color: str) -> str:
    return (
        f"background:{color}; border:1px solid {theme.BORDER_STRONG};"
        f" border-radius:6px;"
    )


class ThemeSettingsDialog(QDialog):
    """Janela exclusiva de aparência (Opções → Personalizar Interface...)."""

    def __init__(self, manager: ThemeManager, parent=None) -> None:
        super().__init__(parent)
        self._m = manager
        self._snapshot = manager.snapshot()  # p/ Cancelar
        self.setWindowTitle("Personalizar Interface")
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(theme.SPACE_XL, theme.SPACE_LG,
                                theme.SPACE_XL, theme.SPACE_LG)
        root.setSpacing(theme.SPACE_MD)

        # ---- tema base ----
        box_t = QGroupBox("Tema")
        lt = QHBoxLayout(box_t)
        self._theme_combo = QComboBox()
        for key, (label, _p, _d) in palettes.THEMES.items():
            self._theme_combo.addItem(label, key)
        self._theme_combo.addItem("Automático (segue o Windows)", AUTO)
        idx = self._theme_combo.findData(manager.theme_key)
        self._theme_combo.setCurrentIndex(max(0, idx))
        self._theme_combo.currentIndexChanged.connect(self._on_theme)
        lt.addWidget(self._theme_combo, 1)
        root.addWidget(box_t)

        # ---- acento rapido ----
        box_a = QGroupBox("Cor principal (acento)")
        la = QHBoxLayout(box_a)
        for name, hexcolor in palettes.ACCENTS:
            b = QPushButton()
            b.setFixedSize(28, 28)
            b.setToolTip(name)
            b.setStyleSheet(_swatch_css(hexcolor))
            b.clicked.connect(lambda _=False, c=hexcolor: self._m.set_accent(c))
            la.addWidget(b)
        outro = QPushButton("Outra cor...")
        outro.clicked.connect(self._pick_accent)
        la.addWidget(outro)
        la.addStretch()
        root.addWidget(box_a)

        # ---- presets ----
        box_p = QGroupBox("Presets")
        lp = QHBoxLayout(box_p)
        self._preset_combo = QComboBox()
        for pname, *_rest in palettes.PRESETS:
            self._preset_combo.addItem(pname)
        lp.addWidget(self._preset_combo, 1)
        aplicar_p = QPushButton("Aplicar preset")
        aplicar_p.clicked.connect(
            lambda: self._m.apply_preset(self._preset_combo.currentText())
        )
        lp.addWidget(aplicar_p)
        root.addWidget(box_p)

        # ---- cores individuais (rolável) ----
        box_c = QGroupBox("Cores da interface (clique para trocar)")
        lc = QVBoxLayout(box_c)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setHorizontalSpacing(theme.SPACE_MD)
        grid.setVerticalSpacing(theme.SPACE_SM)
        self._token_buttons: dict[str, QPushButton] = {}
        for row, (token, label) in enumerate(palettes.CUSTOM_LABELS):
            grid.addWidget(QLabel(label), row, 0)
            b = QPushButton()
            b.setFixedSize(64, 24)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, t=token: self._pick_token(t))
            self._token_buttons[token] = b
            grid.addWidget(b, row, 1, alignment=Qt.AlignLeft)
        scroll.setWidget(inner)
        scroll.setMinimumHeight(220)
        lc.addWidget(scroll)
        root.addWidget(box_c, 1)

        # ---- botões ----
        row = QHBoxLayout()
        b_reset = QPushButton("Restaurar padrão")
        b_reset.clicked.connect(self._m.reset)
        b_exp = QPushButton("Exportar tema...")
        b_exp.clicked.connect(self._export)
        b_imp = QPushButton("Importar tema...")
        b_imp.clicked.connect(self._import)
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(self._cancel)
        b_ok = QPushButton("OK")
        b_ok.setProperty("accent", "true")
        b_ok.clicked.connect(self.accept)  # tudo ja esta aplicado (live)
        row.addWidget(b_reset)
        row.addWidget(b_exp)
        row.addWidget(b_imp)
        row.addStretch()
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        root.addLayout(row)

        self._m.theme_changed.connect(self._refresh_swatches)
        self._refresh_swatches()

    # ---- handlers ----
    def _on_theme(self) -> None:
        self._m.set_theme(self._theme_combo.currentData())

    def _pick_accent(self) -> None:
        c = QColorDialog.getColor(QColor(theme.ACCENT), self, "Cor principal")
        if c.isValid():
            self._m.set_accent(c.name())

    def _pick_token(self, token: str) -> None:
        atual = self._m.palette()[0].get(token, "#ffffff")
        base = atual if atual.startswith("#") else "#ffffff"
        c = QColorDialog.getColor(QColor(base), self, "Escolher cor")
        if c.isValid():
            self._m.set_override(token, c.name())

    def _refresh_swatches(self) -> None:
        colors, _dark = self._m.palette()
        for token, btn in self._token_buttons.items():
            value = colors.get(token, "#ffffff")
            css = value if value.startswith("#") else theme.SURFACE
            btn.setStyleSheet(_swatch_css(css))
            btn.setToolTip(value)

    def _cancel(self) -> None:
        self._m.restore(self._snapshot)
        self.reject()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar tema", "Meu Tema.json", "Tema PrintNest (*.json)"
        )
        if path:
            self._m.export_json(path)

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar tema", "", "Tema PrintNest (*.json)"
        )
        if not path:
            return
        try:
            self._m.import_json(path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Importar tema", str(exc))
