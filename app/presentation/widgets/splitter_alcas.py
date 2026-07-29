"""Divisor com alça de recolher no meio, como no VS Code e no Figma.

Pedido do Philipe (29/07): "as setas estão quase invisíveis, deixe mais
visível, tente colocar onde eu marquei" — e o que ele marcou foi exatamente a
LINHA que separa a biblioteca da chapa, e a que separa a chapa do painel de
campos. É onde a mão já vai quando alguém quer mexer no tamanho do painel.

A alça continua sendo o divisor: arrastar para redimensionar funciona igual. O
botão ocupa só um pedaço no meio, o resto da altura segue arrastável.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QSplitter, QSplitterHandle, QToolButton

from app.presentation import icons, theme

_LARGURA = 15   # largura do divisor (o botão ocupa a mesma)
_ALTURA = 52    # altura do botão: alvo confortável sem virar barra
_ICONE = 11


class _Alca(QSplitterHandle):
    """Divisor com um botãozinho centralizado na vertical."""

    def __init__(self, orientation, parent) -> None:
        super().__init__(orientation, parent)
        self._seta: Callable[[], str] | None = None
        self._dica: Callable[[], str] | None = None
        self._btn = QToolButton(self)
        self._btn.setObjectName("handleBtn")
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setIconSize(QSize(_ICONE, _ICONE))
        self._btn.setFixedSize(_LARGURA, _ALTURA)
        self._btn.hide()  # só aparece depois de configurada

    def configurar(
        self,
        ao_clicar: Callable[[], None],
        seta: Callable[[], str],
        dica: Callable[[], str],
    ) -> None:
        self._seta = seta
        self._dica = dica
        self._btn.clicked.connect(ao_clicar)
        self._btn.show()
        self.atualizar()

    def atualizar(self) -> None:
        """Repinta a seta: ela aponta para o lado em que o painel vai se mover."""
        if self._seta is None:
            return
        self._btn.setIcon(icons.icon(self._seta(), theme.ICON, _ICONE))
        if self._dica is not None:
            self._btn.setToolTip(self._dica())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._btn.move(0, max(0, (self.height() - _ALTURA) // 2))


class SplitterComAlcas(QSplitter):
    """QSplitter cujos divisores podem recolher o painel vizinho."""

    def __init__(self, orientation) -> None:
        super().__init__(orientation)
        self.setHandleWidth(_LARGURA)

    def createHandle(self) -> QSplitterHandle:  # noqa: N802
        return _Alca(self.orientation(), self)

    def registrar_alca(
        self,
        indice: int,
        ao_clicar: Callable[[], None],
        seta: Callable[[], str],
        dica: Callable[[], str],
    ) -> None:
        """Liga a alça `indice` (a que fica ANTES do widget `indice`) a uma ação."""
        alca = self.handle(indice)
        if isinstance(alca, _Alca):
            alca.configurar(ao_clicar, seta, dica)

    def atualizar_alcas(self) -> None:
        """Chamar depois de recolher/abrir: as setas trocam de direção."""
        for i in range(self.count()):
            alca = self.handle(i)
            if isinstance(alca, _Alca):
                alca.atualizar()
