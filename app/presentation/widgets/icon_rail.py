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

        # botão de recolher no TOPO do trilho: é a "aba" visível do docker.
        # Aberto ele aponta para fora (recolher), recolhido aponta para dentro
        # (trazer de volta) — sem ele, recolher dependia de clicar no ícone já
        # aceso, que é um gesto que ninguém descobre sozinho.
        self._btn_collapse = QToolButton()
        self._btn_collapse.setObjectName("collapseBtn")
        self._btn_collapse.setFixedSize(_BTN, 22)
        self._btn_collapse.setIconSize(QSize(14, 14))
        self._btn_collapse.setCursor(Qt.PointingHandCursor)
        self._btn_collapse.clicked.connect(lambda: self.set_collapsed(not self._collapsed))
        rl.addWidget(self._btn_collapse)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idClicked.connect(self._on_rail_clicked)

        self._content = content       # some quando o painel recolhe
        self._collapsed = False
        self._paint_collapse_button()

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

    # ---------------- recolher (mecanismo dos dockers do Corel) ----------------
    collapsedChanged = Signal(bool)  # noqa: N815

    def is_collapsed(self) -> bool:
        return self._collapsed

    def rail_width(self) -> int:
        """Largura do trilho — é o tamanho do painel quando recolhido."""
        return self._rail.width() or self._rail.sizeHint().width()

    def set_collapsed(self, on: bool) -> None:
        """Recolhe o painel deixando só o trilho de ícones.

        É o "Collapse docker" do CorelDRAW: recolhido sobra a aba, e clicar
        nela reabre. Aqui a aba já existe — é o trilho — então recolher é só
        esconder o conteúdo. Vale ~300px de volta para a chapa, que num
        notebook de 1366 é a diferença entre 418px e 722px de área de
        trabalho.
        """
        if on == self._collapsed:
            return
        self._collapsed = on
        self._content.setVisible(not on)
        # grupo exclusivo não deixa desmarcar o botão aceso; solto por um
        # instante para o trilho poder ficar sem nenhum aceso quando recolhido
        self._group.setExclusive(False)
        for i, btn in enumerate(self._buttons):
            btn.setChecked(not on and i == self.currentIndex())
        self._group.setExclusive(True)
        self._paint_collapse_button()
        self.collapsedChanged.emit(on)

    def _on_rail_clicked(self, index: int) -> None:
        """Recolhido, qualquer ícone reabre. Aberto, o ícone ATIVO recolhe."""
        if self._collapsed:
            self.set_collapsed(False)
            self.setCurrentIndex(index)
        elif index == self.currentIndex():
            self.set_collapsed(True)
        else:
            self.setCurrentIndex(index)

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

    def _paint_collapse_button(self) -> None:
        """A seta aponta para onde o painel vai: fora recolhe, dentro reabre."""
        nome = "chevron-left" if self._collapsed else "chevron-right"
        self._btn_collapse.setIcon(icons.icon(nome, theme.ICON, 14))
        self._btn_collapse.setToolTip(
            "Mostrar o painel (F11)" if self._collapsed else "Recolher o painel (F11)"
        )

    def refresh_icons(self) -> None:
        """Trocou o tema: re-renderiza os ícones com as cores novas."""
        self._paint_all()
        self._paint_collapse_button()
