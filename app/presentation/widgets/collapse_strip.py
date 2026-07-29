"""Tira fina que devolve um painel recolhido.

É a "aba" que o CorelDRAW deixa no lugar do docker recolhido: sobra uma faixa
estreita com o nome, e clicar nela reabre. Sem essa faixa quem recolhe sem
querer acha que perdeu o painel — o comando de voltar existiria só no menu.

O nome é desenhado girado 90°, porque na vertical um texto normal não caberia
em 26px de largura.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.presentation import icons, theme

_SETA = 12  # lado do ícone de seta desenhado no topo da faixa


class CollapseStrip(QWidget):
    """Faixa vertical clicável com o nome do painel recolhido."""

    LARGURA = 26  # quem posiciona o splitter precisa saber o tamanho recolhido

    def __init__(self, texto: str, ao_clicar, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._texto = texto
        self._ao_clicar = ao_clicar
        self.setObjectName("collapseStrip")
        self.setFixedWidth(self.LARGURA)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Mostrar {texto}")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def sizeHint(self) -> QSize:
        largura_texto = self.fontMetrics().horizontalAdvance(self._texto) + 24
        return QSize(self.LARGURA, largura_texto)

    def minimumSizeHint(self) -> QSize:
        return QSize(self.LARGURA, 60)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self._ao_clicar()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        # cores lidas na hora de pintar, não no construtor: assim a faixa
        # acompanha a troca de tema ao vivo
        painter.fillRect(self.rect(), QColor(theme.SURFACE_ALT))
        # borda do lado da chapa: sem ela a faixa se dissolve no fundo da
        # janela e não parece um painel fechado, parece sujeira
        painter.setPen(QColor(theme.BORDER))
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        # seta no topo, sem girar: é ela que diz "clique aqui para abrir".
        # Só o nome na vertical não passa a ideia de botão.
        seta = icons.icon("chevron-right", theme.ICON, _SETA).pixmap(_SETA, _SETA)
        painter.drawPixmap((self.width() - _SETA) // 2, 8, seta)

        painter.setPen(QColor(theme.TEXT_MUTED))
        # gira o sistema de coordenadas e escreve de baixo para cima, que é
        # como os painéis laterais de editor costumam rotular. Depois do giro,
        # AlignRight é o TOPO da faixa — é lá que o rótulo tem de ficar, senão
        # ele afunda no rodapé e ninguém vê. O recuo maior desse lado deixa a
        # seta livre.
        painter.translate(0, self.height())
        painter.rotate(-90)
        painter.drawText(
            self.rect().transposed().adjusted(12, 0, -(_SETA + 14), 0),
            Qt.AlignRight | Qt.AlignVCenter,
            self._texto,
        )
        painter.end()
