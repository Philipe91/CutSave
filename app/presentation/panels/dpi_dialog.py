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
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.infrastructure.color_profiles import (
    caminho_do_perfil_padrao,
    descricao_do_perfil,
    perfil_e_cmyk,
    perfis_cmyk_do_sistema,
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


class OpcoesDeCor(QWidget):
    """Espaco de cor + perfil + qualidade da exportacao em imagem.

    Reusado nas DUAS portas de saida, como o LeituraDpi: o dialogo do menu
    "Exportar Imagem" e o painel do Centro de Exportacao. Nasceu widget
    porque a primeira versao so existia no dialogo — e o Centro de
    Exportacao, que e por onde o cliente exporta de verdade, passava reto
    pelas opcoes (relatado em 03/09/2026, logo depois de eu entregar).

    'formato_conhecido=False' e o caso do Centro de Exportacao: la o PNG/JPEG
    so e decidido na hora de dar o nome do arquivo, entao a tela nao pode
    desabilitar nada por formato — quem resolve e o exportador, que ignora o
    CMYK quando o arquivo sai PNG.
    """

    def __init__(self, parent=None, *, color_space_inicial: str = "rgb",
                 icc_inicial: str = "", quality_inicial: int = 95,
                 sugerir_cmyk: bool = False,
                 formato_conhecido: bool = True,
                 compacto: bool = False) -> None:
        super().__init__(parent)
        self._perfis = perfis_cmyk_do_sistema()
        self._formato_conhecido = formato_conhecido
        self._compacto = compacto
        self._fmt = "jpeg"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_XS)

        # QFormLayout e nao linhas soltas: os rotulos ficam alinhados numa
        # coluna so (foi assim que o painel do Centro de Exportacao apareceu
        # com os campos escadeados, 03/09/2026).
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(theme.SPACE_XS)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._espaco = QComboBox()
        self._espaco.addItem("RGB", "rgb")
        self._espaco.addItem("CMYK", "cmyk")
        # CMYK so existe se a maquina tiver algum perfil de destino
        self._espaco.model().item(1).setEnabled(bool(self._perfis))
        inicial = (color_space_inicial or "rgb").lower()
        if sugerir_cmyk and self._perfis:
            inicial = "cmyk"  # arte CMYK: ja abre no espaco dela
        self._espaco.setCurrentIndex(1 if inicial == "cmyk" and self._perfis else 0)
        self._espaco.currentIndexChanged.connect(lambda _: self.atualizar())
        form.addRow("Espaço de cor:", self._espaco)

        self._perfil = QComboBox()
        self._perfil.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._perfil.setMinimumContentsLength(12)
        for p in self._perfis:
            self._perfil.addItem(p.nome, p.caminho)
        self._selecionar_perfil(icc_inicial or caminho_do_perfil_padrao())
        self._botao_perfil = QPushButton("Escolher…")
        self._botao_perfil.clicked.connect(self._escolher_perfil)
        campo_perfil = QWidget()
        cp = QHBoxLayout(campo_perfil)
        cp.setContentsMargins(0, 0, 0, 0)
        cp.setSpacing(theme.SPACE_XS)
        cp.addWidget(self._perfil, 1)
        cp.addWidget(self._botao_perfil)
        self._rotulo_perfil = QLabel("Perfil:")
        form.addRow(self._rotulo_perfil, campo_perfil)
        self._campo_perfil = campo_perfil

        self._qualidade = QSpinBox()
        self._qualidade.setRange(1, 100)
        self._qualidade.setValue(int(quality_inicial))
        form.addRow("Qualidade (JPEG):", self._qualidade)
        lay.addLayout(form)

        # O que a opcao CMYK NAO faz, dito na hora da escolha: depois de a
        # chapa estar impressa a explicacao chega tarde.
        #
        # No modo compacto (painel estreito do Centro de Exportacao) o texto
        # vai numa linha so + tooltip: QLabel com wordWrap reporta altura
        # minima errada dentro de um painel apertado, e o layout inteiro
        # colapsava com os campos desenhados por cima uns dos outros.
        self._nota = QLabel("")
        self._nota.setWordWrap(not compacto)
        self._nota.setProperty("role", "caption")
        self._nota.setStyleSheet(f"color: {theme.TEXT_MUTED};")
        if compacto:
            self._nota.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        lay.addWidget(self._nota)
        self.atualizar()

    # ---- respostas ----
    def color_space(self) -> str:
        """'cmyk' so quando o formato guarda CMYK — PNG nunca guarda."""
        if self._formato_conhecido and self._fmt != "jpeg":
            return "rgb"
        return str(self._espaco.currentData())

    def icc_path(self) -> str:
        return str(self._perfil.currentData() or "")

    def quality(self) -> int:
        return int(self._qualidade.value())

    # ---- estado ----
    def set_formato(self, fmt: str) -> None:
        self._fmt = (fmt or "jpeg").lower()
        self.atualizar()

    def atualizar(self) -> None:
        jpeg = (not self._formato_conhecido) or self._fmt == "jpeg"
        # PNG nao guarda CMYK nem qualidade: limite do FORMATO, nao nosso
        self._espaco.setEnabled(jpeg)
        self._qualidade.setEnabled(jpeg)
        cmyk = self.color_space() == "cmyk"
        self._rotulo_perfil.setVisible(cmyk)
        self._campo_perfil.setVisible(cmyk)
        longo = curto = ""
        if not jpeg:
            longo = curto = "PNG não guarda CMYK — a imagem sai em RGB."
        elif cmyk:
            longo = (
                "O CMYK é convertido a partir do RGB da rasterização, então "
                "tinta pura não volta igual (preto K vira preto de quatro "
                "cores). Para cor idêntica à arte, exporte em PDF."
            )
            curto = "Convertido do RGB — cor exata só em PDF."
            if not self._formato_conhecido:
                longo += " Salvando como PNG, sai em RGB."
        elif not self._perfis:
            longo = curto = "Nenhum perfil CMYK instalado nesta máquina."
        self._nota.setText(curto if self._compacto else longo)
        self._nota.setToolTip(longo)
        self._nota.setVisible(bool(longo))

    # ---- interacao ----
    def _selecionar_perfil(self, caminho: str | None) -> None:
        if not caminho:
            return
        i = self._perfil.findData(caminho)
        if i < 0:
            nome = descricao_do_perfil(caminho)
            if nome is None:
                return
            self._perfil.addItem(nome, caminho)
            i = self._perfil.count() - 1
        self._perfil.setCurrentIndex(i)

    def _escolher_perfil(self) -> None:
        """Perfil da propria grafica do cliente, de qualquer pasta."""
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Escolher perfil de cor", "", "Perfil ICC (*.icc *.icm)"
        )
        if not caminho:
            return
        if not perfil_e_cmyk(caminho):
            QMessageBox.warning(
                self, "PrintNest",
                "Este arquivo não é um perfil CMYK — escolha o perfil de "
                "saída que a sua gráfica usa.",
            )
            return
        self._selecionar_perfil(caminho)


class ExportarImagemDialog(QDialog):
    """Opcoes da exportacao em imagem, na forma que o operador de grafica ja
    conhece do Corel: formato, resolucao, espaco de cor, perfil e qualidade
    numa tela so, com o peso da exportacao ao vivo."""

    def __init__(self, parent, largura_mm: float, altura_mm: float,
                 image_format: str, dpi_inicial: int, *,
                 color_space_inicial: str = "rgb",
                 icc_inicial: str = "",
                 quality_inicial: int = 95,
                 sugerir_cmyk: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exportar Imagem")
        self._w_mm = float(largura_mm)
        self._h_mm = float(altura_mm)

        lay = QVBoxLayout(self)
        lay.setSpacing(theme.SPACE_MD)

        self._formato = QComboBox()
        self._formato.addItem("JPEG", "jpeg")
        self._formato.addItem("PNG", "png")
        self._formato.setCurrentIndex(0 if image_format == "jpeg" else 1)
        self._formato.currentIndexChanged.connect(lambda _: self._atualizar())
        lay.addLayout(_linha("Formato:", self._formato))

        self._spin = QSpinBox()
        self._spin.setRange(30, 1200)
        self._spin.setSingleStep(10)
        self._spin.setValue(int(dpi_inicial))
        self._spin.valueChanged.connect(lambda _: self._atualizar())
        lay.addLayout(_linha("Resolução (DPI):", self._spin))

        self._leitura = LeituraDpi()
        self._leitura.setMinimumWidth(330)
        lay.addWidget(self._leitura)

        self._cor = OpcoesDeCor(
            self, color_space_inicial=color_space_inicial,
            icc_inicial=icc_inicial, quality_inicial=quality_inicial,
            sugerir_cmyk=sugerir_cmyk,
        )
        lay.addWidget(self._cor)

        self._botoes = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        self._botoes.accepted.connect(self.accept)
        self._botoes.rejected.connect(self.reject)
        lay.addWidget(self._botoes)
        self._atualizar()

    # ---- respostas ----
    def dpi(self) -> int:
        return int(self._spin.value())

    def formato(self) -> str:
        return str(self._formato.currentData())

    def color_space(self) -> str:
        return self._cor.color_space()

    def icc_path(self) -> str:
        return self._cor.icc_path()

    def quality(self) -> int:
        return self._cor.quality()

    def _atualizar(self) -> None:
        fmt = self.formato()
        self._cor.set_formato(fmt)
        nivel = self._leitura.atualizar(self._w_mm, self._h_mm, self.dpi(), fmt)
        # demora nunca impede; o que impede e o formato nao guardar a imagem
        self._botoes.button(QDialogButtonBox.Ok).setEnabled(nivel != "impossivel")


def _linha(rotulo: str, *widgets) -> QHBoxLayout:
    linha = QHBoxLayout()
    linha.addWidget(QLabel(rotulo))
    for w in widgets:
        linha.addWidget(w)
    linha.addStretch()
    return linha


