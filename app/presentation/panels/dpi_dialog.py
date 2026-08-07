"""Escolha do DPI da exportacao em imagem, com um indicador VISUAL de peso.

Historico curto, porque explica o formato desta tela:

1. Chapa pesada exportada em JPEG a 500 DPI saia com pecas faltando, calada.
2. A primeira correcao RECUSAVA exportar acima do teto. Errado: o arquivo e do
   cliente, quem decide exportar e ele.
3. A segunda avisava, em texto, que o arquivo podia sair errado — e chegou a
   acusar falha num arquivo INTEIRO, exportado a 290 DPI.

Dai a forma de agora: um indicador de QUANTO VAI DEMORAR, e mais nada. O
programa nao promete defeito que talvez nao aconteca; aviso que erra queima a
confianca em todos os outros avisos. A unica coisa que ainda barra e o limite
do formato — que e fato, nao palpite: o JPEG nao guarda lado maior que 65.535
px, entao nao existe arquivo para gravar.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.infrastructure.exporters.pikepdf_print_exporter import NIVEIS, peso_exportacao
from app.presentation import theme

# verde no leve, ambar no pesado. Vermelho de proposito fora: vermelho le-se
# como "deu erro", e aqui nao ha erro nenhum — so demora.
COR_NIVEL = {
    "rapido": theme.SUCCESS,
    "normal": theme.SUCCESS,
    "demorado": theme.WARNING,
    "muito_demorado": theme.WARNING,
    "impossivel": theme.TEXT_MUTED,
}


class NivelBarra(QWidget):
    """Quatro tracinhos preenchidos conforme o peso da exportacao."""

    SEGMENTOS = len(NIVEIS)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._nivel = 0
        self._cor = theme.SUCCESS
        self.setFixedSize(72, 12)

    def set_nivel(self, nivel: str) -> None:
        self._nivel = NIVEIS.index(nivel) + 1 if nivel in NIVEIS else 0
        self._cor = COR_NIVEL.get(nivel, theme.TEXT_MUTED)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        vao = 4
        larg = (self.width() - vao * (self.SEGMENTOS - 1)) / self.SEGMENTOS
        for i in range(self.SEGMENTOS):
            aceso = i < self._nivel
            p.setBrush(QColor(self._cor if aceso else theme.BORDER))
            p.drawRoundedRect(
                int(i * (larg + vao)), 0, int(larg), self.height(), 3, 3
            )
        p.end()


class LeituraDpi(QWidget):
    """Linha 'Rápido ▮▮▯▯ · 12.400 × 8.900 px'. Reusada nas duas telas."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_SM)
        self._barra = NivelBarra()
        self._rotulo = QLabel("")
        self._tamanho = QLabel("")
        self._tamanho.setProperty("role", "caption")
        self._tamanho.setStyleSheet(f"color: {theme.TEXT_MUTED};")
        lay.addWidget(self._barra)
        lay.addWidget(self._rotulo)
        lay.addWidget(self._tamanho)
        lay.addStretch()

    def atualizar(self, largura_mm: float, altura_mm: float, dpi: int,
                  image_format: str) -> str:
        """Redesenha a leitura e devolve o nível, para quem precisar dele."""
        nivel, rotulo, tamanho = peso_exportacao(
            largura_mm, altura_mm, dpi, image_format
        )
        self._barra.set_nivel(nivel)
        self._rotulo.setText(rotulo)
        self._rotulo.setStyleSheet(f"color: {COR_NIVEL.get(nivel, theme.TEXT_MUTED)};")
        self._tamanho.setText(f"· {tamanho}")
        return nivel

    def limpar(self) -> None:
        self._barra.set_nivel("")
        self._rotulo.clear()
        self._tamanho.clear()


class DpiDialog(QDialog):
    """Pergunta o DPI mostrando, ao vivo, o peso daquele número."""

    def __init__(self, parent, largura_mm: float, altura_mm: float,
                 image_format: str, dpi_inicial: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exportar Imagem")
        self._w_mm = float(largura_mm)
        self._h_mm = float(altura_mm)
        self._fmt = image_format

        lay = QVBoxLayout(self)
        lay.setSpacing(theme.SPACE_MD)

        linha = QHBoxLayout()
        linha.addWidget(QLabel("Resolução (DPI):"))
        self._spin = QSpinBox()
        self._spin.setRange(30, 1200)
        self._spin.setSingleStep(10)
        self._spin.setValue(int(dpi_inicial))
        self._spin.valueChanged.connect(lambda _: self._atualizar())
        linha.addWidget(self._spin)
        linha.addStretch()
        lay.addLayout(linha)

        self._leitura = LeituraDpi()
        self._leitura.setMinimumWidth(330)
        lay.addWidget(self._leitura)

        self._botoes = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        self._botoes.accepted.connect(self.accept)
        self._botoes.rejected.connect(self.reject)
        lay.addWidget(self._botoes)
        self._atualizar()

    def dpi(self) -> int:
        return int(self._spin.value())

    def _atualizar(self) -> None:
        nivel = self._leitura.atualizar(self._w_mm, self._h_mm, self.dpi(), self._fmt)
        # demora nunca impede; o que impede e o formato nao guardar a imagem
        self._botoes.button(QDialogButtonBox.Ok).setEnabled(nivel != "impossivel")
