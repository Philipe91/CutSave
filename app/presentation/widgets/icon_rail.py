"""IconRailTabs: painel de abas com trilho vertical de ícones (estilo VS Code).

Substitui o QTabWidget do inspector: as abas de texto viravam "..." quando o
painel ficava estreito; ícones num trilho vertical nunca são cortados por
largura. Um título no topo do conteúdo mostra o nome da seção atual, para o
ícone sozinho não perder o rótulo.

A API imita o subconjunto de QTabWidget que a MainWindow usa (currentIndex,
setCurrentIndex, setTabText, currentWidget, setCurrentWidget, count, tabText,
widget e o sinal currentChanged), então os call sites existentes não mudam.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.presentation import icons, theme

_BTN = 38          # lado do botão do trilho
_ICON_SIZE = 20    # ícone dentro do botão


class IconRailTabs(QWidget):
    """Trilho de ícones à direita + páginas empilhadas à esquerda."""

    currentChanged = Signal(int)  # noqa: N815 (espelha o nome do QTabWidget)

    def __init__(self) -> None:
        super().__init__()
        self._icon_names: list[str] = []
        self._texts: list[str] = []
        self._buttons: list[QToolButton] = []

        # título da seção atual (o trilho só tem ícones)
        self._title = QLabel()
        self._title.setObjectName("railTitle")

        self._stack = QStackedWidget()

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self._title)
        cl.addWidget(self._stack, 1)

        self._rail = QWidget()
        self._rail.setObjectName("railBar")
        self._rail.setFixedWidth(_BTN + 2 * theme.SPACE_XS)
        rl = QVBoxLayout(self._rail)
        rl.setContentsMargins(theme.SPACE_XS, theme.SPACE_SM, theme.SPACE_XS, theme.SPACE_SM)
        rl.setSpacing(theme.SPACE_XS)
        rl.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idClicked.connect(self.setCurrentIndex)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(content, 1)
        root.addWidget(self._rail)

        self._stack.currentChanged.connect(self._on_current_changed)

    # ---------------- montagem ----------------
    def addTab(self, page: QWidget, icon_name: str, text: str) -> None:  # noqa: N802
        """Adiciona uma seção: 'icon_name' é um SVG de assets/icons."""
        index = self._stack.count()
        self._icon_names.append(icon_name)
        self._texts.append(text)

        btn = QToolButton()
        btn.setObjectName("railBtn")
        btn.setCheckable(True)
        btn.setFixedSize(_BTN, _BTN)
        btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(text)
        btn.setChecked(index == 0)
        self._buttons.append(btn)
        self._group.addButton(btn, index)
        self._rail.layout().addWidget(btn)

        self._stack.addWidget(page)
        self._paint_button(index)
        if index == 0:
            self._title.setText(text)

    # ---------------- API compatível com QTabWidget ----------------
    def count(self) -> int:
        return self._stack.count()

    def widget(self, index: int) -> QWidget:
        return self._stack.widget(index)

    def currentIndex(self) -> int:  # noqa: N802
        return self._stack.currentIndex()

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        self._stack.setCurrentIndex(index)

    def currentWidget(self) -> QWidget:  # noqa: N802
        return self._stack.currentWidget()

    def setCurrentWidget(self, page: QWidget) -> None:  # noqa: N802
        self._stack.setCurrentWidget(page)

    def tabText(self, index: int) -> str:  # noqa: N802
        return self._texts[index]

    def setTabText(self, index: int, text: str) -> None:  # noqa: N802
        """Usado pela seleção: 'Seleção' -> 'Peça' / 'Grupo (3)'."""
        self._texts[index] = text
        self._buttons[index].setToolTip(text)
        if index == self.currentIndex():
            self._title.setText(text)

    # ---------------- interno ----------------
    def _on_current_changed(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            self._title.setText(self._texts[index])
            self._paint_all()
        self.currentChanged.emit(index)

    def _paint_button(self, index: int) -> None:
        """Ícone azul quando ativo, neutro quando não (cores do tema ATUAL)."""
        active = index == self._stack.currentIndex()
        color = theme.ACCENT if active else theme.ICON
        self._buttons[index].setIcon(icons.icon(self._icon_names[index], color, _ICON_SIZE))

    def _paint_all(self) -> None:
        for i in range(len(self._buttons)):
            self._paint_button(i)

    def refresh_icons(self) -> None:
        """Trocou o tema: re-renderiza os ícones com as cores novas."""
        self._paint_all()
