"""Janela de acompanhamento da exportacao em imagem.

Ate 11/09/2026 a exportacao em imagem rodava na thread da UI com um
indicador na barra de status: entre uma faixa e outra (5-30s a 300 DPI) nada
se movia e o Windows carimbava "Nao esta respondendo" na barra de titulo.
Numa chapa de 40 pecas o operador nao tinha como saber se faltavam 30
segundos ou 30 minutos — e matou o processo no meio achando que travou.

Aqui a exportacao roda em QThread (mesmo padrao do _NestThread do Modo
Corte) e a janela mostra: a etapa que o exportador manda, a barra, o tempo
decorrido com estimativa do restante, uma dica rotativa (estilo _NEST_TIPS)
e o botao Cancelar. O exportador consulta o Cancelar entre faixas (~5s) e,
cancelado, nao deixa arquivo parcial na pasta.

Nada aqui toca em widget fora da thread da UI: o worker so emite sinais.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from app.presentation import theme

# Mensagens rotativas da espera (estilo dica de video game, como no Modo
# Corte): espera com contexto em vez de barra muda.
_EXPORT_TIPS = (
    "Dica: a 150 DPI a chapa exporta em segundos; 300 DPI leva ~4× mais e só "
    "faz diferença em foto vista de perto.",
    "Você sabia? Exportar em PDF preserva as tintas CMYK da arte byte a byte "
    "— e sai na hora, sem rasterizar.",
    "Dica: JPEG grava CMYK com o perfil embutido; PNG só guarda RGB. Para o "
    "RIP, prefira JPEG ou PDF.",
    "O perfil de cor escolhido vai EMBUTIDO no arquivo: o RIP lê e a chapa "
    "imprime igual em qualquer máquina.",
    "Chapa com muitas cópias da mesma arte custa quase o mesmo que uma: a "
    "imagem entra no documento uma vez só.",
    "Dica: Arquivo › Salvar projeto guarda arquivos, quantidades e parâmetros "
    "— reabra e exporte de novo sem remontar.",
    "Você sabia? O Modo Corte organiza peças irregulares pelo contorno real "
    "(true-shape) e exporta DXF para laser/CNC.",
    "Dica: 'Faca · este arquivo' gera o contorno de corte sozinho — ajuste a "
    "sensibilidade se a arte tiver fundo claro.",
    "As marcas de registro entram na impressão e no DXF na mesma coordenada: "
    "impressão e corte batem.",
    "Dica: em Visualização, 'Tela dividida' mostra impressão e faca lado a "
    "lado — confira o corte antes de exportar.",
    "Cancelar interrompe entre faixas e não deixa arquivo pela metade na pasta.",
)
_INTERVALO_DICA_MS = 6000
_INTERVALO_RELOGIO_MS = 1000
# abaixo disso a estimativa chuta demais (a primeira faixa ainda nem saiu)
_FRACAO_MINIMA_ESTIMATIVA = 0.10


def formatar_tempo(segundos: float) -> str:
    """Segundos -> 'm:ss' (1:05). Minutos passam de 59 sem virar hora: o
    operador compara com o relógio da parede, não faz conta."""
    s = max(0, int(round(segundos)))
    return f"{s // 60}:{s % 60:02d}"


def estimativa_restante(decorrido_s: float, fracao: float) -> float | None:
    """Quanto falta, extrapolando o ritmo até aqui. None enquanto a fração é
    pequena demais para a conta valer alguma coisa."""
    if fracao < _FRACAO_MINIMA_ESTIMATIVA or decorrido_s <= 0:
        return None
    return max(0.0, decorrido_s / fracao - decorrido_s)


Trabalho = Callable[[Callable[[float, str], None], Callable[[], bool]], object]


class ExportThread(QThread):
    """Roda o trabalho FORA da thread da UI e guarda o resultado.

    'trabalho' recebe (progresso, cancelado): progresso(fracao, texto) vira
    sinal para a janela; cancelado() devolve True depois de cancelar(). O
    resultado e a excecao ficam em atributos, alem do sinal 'done' — assim a
    janela le o desfecho depois de wait() mesmo se a fila de sinais nao
    rodou (teste que dubla o exec(), por exemplo)."""

    progresso = Signal(float, str)
    done = Signal(object, object)  # (resultado | None, excecao | None)

    def __init__(self, parent, trabalho: Trabalho) -> None:
        super().__init__(parent)
        self._trabalho = trabalho
        self._cancelado = False
        self.resultado: object = None
        self.erro: BaseException | None = None

    def cancelar(self) -> None:
        # escrito na UI, lido pelo worker entre faixas: bool e atomico
        self._cancelado = True

    def cancelado(self) -> bool:
        return self._cancelado

    def run(self) -> None:
        try:
            self.resultado = self._trabalho(self._emitir, self.cancelado)
        except Exception as exc:  # noqa: BLE001 - a UI mostra, nao decide
            self.erro = exc
        self.done.emit(self.resultado, self.erro)

    def _emitir(self, fracao: float, texto: str) -> None:
        self.progresso.emit(float(fracao), str(texto or ""))


class ExportandoImagemDialog(QDialog):
    """Modal sem X: so fecha quando a thread termina (Esc = Cancelar).

    Uso: resultado, erro = ExportandoImagemDialog(parent).executar(trabalho).
    'erro' e a excecao do trabalho (inclusive ExportacaoCancelada) ou None."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exportando imagem")
        self.setModal(True)
        # sem X nem "?" — fechar no meio destruiria a thread viva
        self.setWindowFlags(
            (self.windowFlags() | Qt.CustomizeWindowHint)
            & ~Qt.WindowCloseButtonHint & ~Qt.WindowContextHelpButtonHint
        )
        self.setMinimumWidth(480)

        self._thread: ExportThread | None = None
        self._inicio = time.monotonic()
        self._fracao = 0.0
        self._cancelando = False
        self._tip_index = 0

        lay = QVBoxLayout(self)
        lay.setSpacing(theme.SPACE_MD)
        lay.setContentsMargins(theme.SPACE_LG, theme.SPACE_LG, theme.SPACE_LG, theme.SPACE_LG)

        self._etapa = QLabel("Preparando…")
        self._etapa.setStyleSheet(f"font-size: {theme.FONT_LG}px; font-weight: 600;")
        lay.addWidget(self._etapa)

        self._barra = QProgressBar()
        self._barra.setRange(0, 0)  # indeterminado ate a primeira fracao
        self._barra.setTextVisible(True)
        lay.addWidget(self._barra)

        self._tempo = QLabel()
        self._tempo.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        lay.addWidget(self._tempo)

        self._dica = QLabel(_EXPORT_TIPS[0])
        self._dica.setWordWrap(True)
        self._dica.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_SM}px;")
        self._dica.setMinimumHeight(2 * (theme.FONT_SM + 6))  # duas linhas sem pular
        lay.addWidget(self._dica)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        self._btn_cancelar = QPushButton("Cancelar")
        self._btn_cancelar.clicked.connect(self._cancelar)
        botoes.addWidget(self._btn_cancelar)
        lay.addLayout(botoes)

        self._relogio = QTimer(self)
        self._relogio.setInterval(_INTERVALO_RELOGIO_MS)
        self._relogio.timeout.connect(self._atualizar_tempo)
        self._dica_timer = QTimer(self)
        self._dica_timer.setInterval(_INTERVALO_DICA_MS)
        self._dica_timer.timeout.connect(self._proxima_dica)
        self._atualizar_tempo()

    # ---- ciclo ----
    def executar(self, trabalho: Trabalho) -> tuple[object, BaseException | None]:
        """Roda 'trabalho' na thread, mostra a janela ate ele terminar e
        devolve (resultado, excecao)."""
        self._thread = ExportThread(self, trabalho)
        self._thread.progresso.connect(self._on_progresso)
        self._thread.finished.connect(self._fechar)  # so fecha com a thread parada
        self._inicio = time.monotonic()
        self._relogio.start()
        self._dica_timer.start()
        self._thread.start()
        self.exec()
        self._thread.wait()  # exec() dublado em teste: garante o desfecho
        self._relogio.stop()
        self._dica_timer.stop()
        return self._thread.resultado, self._thread.erro

    def rodando(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _fechar(self) -> None:
        self._relogio.stop()
        self._dica_timer.stop()
        self.accept()

    # ---- cancelar ----
    def _cancelar(self) -> None:
        if not self.rodando() or self._cancelando:
            return
        self._cancelando = True
        self._thread.cancelar()
        self._btn_cancelar.setEnabled(False)
        self._btn_cancelar.setText("Cancelando…")
        self._etapa.setText("Cancelando — aguardando a faixa atual terminar…")
        self._atualizar_tempo()

    def reject(self) -> None:  # Esc
        if self.rodando():
            self._cancelar()
            return
        super().reject()

    def closeEvent(self, event) -> None:  # Alt+F4 / fechar pela barra de tarefas
        if self.rodando():
            event.ignore()
            self._cancelar()
            return
        super().closeEvent(event)

    # ---- atualizacoes (thread da UI) ----
    def _on_progresso(self, fracao: float, texto: str) -> None:
        if texto and not self._cancelando:
            self._etapa.setText(texto)
        self._fracao = max(0.0, min(1.0, fracao))
        if self._fracao <= 0:
            self._barra.setRange(0, 0)
        else:
            if self._barra.maximum() == 0:
                self._barra.setRange(0, 100)
            self._barra.setValue(int(round(self._fracao * 100)))
        self._atualizar_tempo()

    def _atualizar_tempo(self) -> None:
        decorrido = time.monotonic() - self._inicio
        texto = f"Decorrido {formatar_tempo(decorrido)}"
        if self._cancelando:
            texto += " · cancelando…"
        else:
            restante = estimativa_restante(decorrido, self._fracao)
            if restante is None:
                texto += " · restante: calculando…"
            else:
                texto += f" · restante ~{formatar_tempo(restante)}"
        self._tempo.setText(texto)

    def _proxima_dica(self) -> None:
        self._tip_index += 1
        self._dica.setText(_EXPORT_TIPS[self._tip_index % len(_EXPORT_TIPS)])

    # ---- leitura (testes) ----
    def etapa(self) -> str:
        return self._etapa.text()

    def dica(self) -> str:
        return self._dica.text()

    def tempo(self) -> str:
        return self._tempo.text()
