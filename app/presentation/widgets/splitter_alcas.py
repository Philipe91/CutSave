"""Divisor com alça REDONDA de recolher, flutuando sobre a linha.

Pedido do Philipe (29/07), em duas etapas. Primeiro: "as setas estão quase
invisíveis, tente colocar onde eu marquei" — e ele marcou as duas linhas que
separam os painéis. Depois, vendo a alça em cápsula alta: "tá parecendo um
scroll de mouse". Escolheu entre 5 modelos o círculo na linha.

O diagnóstico dele estava certo: uma cápsula alta e estreita parada no meio de
um trilho é literalmente a silhueta de uma barra de rolagem. Círculo não é —
não existe barra de rolagem redonda.

Onde o botão mora, e por que não é obvio: um filho é RECORTADO pelo pai, então
um círculo de 24px dentro de uma linha de 9px sairia cortado. E ele também não
pode ser filho do próprio QSplitter — o QSplitter ADOTA qualquer filho novo
como painel, e os dois círculos viravam painéis 4 e 5 (o recolhimento parava de
redimensionar, porque sizes() deixava de ter 3 itens). Então ele é filho do
widget que CONTÉM o splitter, posicionado por cima da linha.

Assim o divisor fica com 9px em vez dos 15 da versão em cápsula — são ~20px
devolvidos para a chapa nos dois divisores, que em notebook é exatamente o que
faltava.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtWidgets import QSplitter, QToolButton

from app.presentation import icons, theme

_DIVISOR = 9   # largura da linha: só o que a mão precisa para arrastar
_LADO = 24     # diâmetro do círculo
_ICONE = 12


class _AlcaRedonda(QToolButton):
    """Círculo centrado na linha que separa dois painéis."""

    def __init__(self, parent, seta: Callable[[], str], dica: Callable[[], str]) -> None:
        super().__init__(parent)
        self._seta = seta
        self._dica = dica
        self.setObjectName("handleBtn")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(_LADO, _LADO)
        self.setIconSize(QSize(_ICONE, _ICONE))
        self.atualizar()

    def atualizar(self) -> None:
        """Repinta a seta: ela aponta para o lado em que o painel vai."""
        self.setIcon(icons.icon(self._seta(), theme.ICON, _ICONE))
        self.setToolTip(self._dica())


class SplitterComAlcas(QSplitter):
    """QSplitter cujos divisores ganham um botão redondo de recolher."""

    def __init__(self, orientation) -> None:
        super().__init__(orientation)
        self.setHandleWidth(_DIVISOR)
        self._pedidos: dict[int, tuple] = {}
        self._alcas: dict[int, _AlcaRedonda] = {}
        self.splitterMoved.connect(lambda *_: self._posicionar())

    def registrar_alca(
        self,
        indice: int,
        ao_clicar: Callable[[], None],
        seta: Callable[[], str],
        dica: Callable[[], str],
    ) -> None:
        """Liga a alça `indice` (a linha ANTES do painel `indice`) a uma ação.

        O botão só nasce quando o splitter já tem um pai — na montagem da
        janela ele ainda não tem, e o círculo precisa do pai para não ser
        adotado como painel."""
        self._pedidos[indice] = (ao_clicar, seta, dica)
        self._posicionar()
        # segunda passada: na montagem as linhas do splitter ainda não têm
        # geometria, e sem isto o círculo nasce no canto errado
        QTimer.singleShot(0, self._posicionar)

    def alca(self, indice: int) -> _AlcaRedonda | None:
        return self._alcas.get(indice)

    def atualizar_alcas(self) -> None:
        """Chamar depois de recolher/abrir: as setas trocam de direção."""
        for alca in self._alcas.values():
            alca.atualizar()
        self._posicionar()
        QTimer.singleShot(0, self._posicionar)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._posicionar()

    def _posicionar(self) -> None:
        pai = self.parentWidget()
        if pai is None:
            return  # ainda montando a janela; a próxima passada resolve
        for indice, cfg in self._pedidos.items():
            alca = self._alcas.get(indice)
            if alca is None:
                ao_clicar, seta, dica = cfg
                alca = _AlcaRedonda(pai, seta, dica)
                alca.clicked.connect(ao_clicar)
                self._alcas[indice] = alca
                alca.show()
            linha = self.handle(indice)
            if linha is None:
                continue
            # coordenadas do PAI: o círculo não vive dentro do splitter
            centro = self.mapTo(pai, linha.geometry().center())
            meio = self.mapTo(pai, QPoint(0, self.height() // 2))
            alca.move(centro.x() - _LADO // 2, meio.y() - _LADO // 2)
            alca.raise_()  # o círculo passa por cima da mesa e do painel
