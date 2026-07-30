"""Aviso de atualizacao na interface: consulta em thread e avisa o usuario.

A consulta faz REDE, entao nunca roda na thread da interface — foi exatamente
esse tipo de coisa que deixava a janela congelada. Aqui ela vai para um QThread
e o resultado volta por sinal.

O aviso automatico aparece UMA VEZ por versao: quem clicou "Agora nao" nao e
perturbado de novo por aquela versao (o dispensado fica em QSettings, mesmo
escopo do tour). Ja o "Procurar atualizacoes..." do menu Ajuda sempre responde,
inclusive quando esta tudo em dia — check manual mudo parece que quebrou.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from app import __version__
from app.infrastructure.updates import Novidade, checar, url_segura

_ORG, _APP = "PrintNest", "PrintNestPremium"
_CHAVE_DISPENSADA = "atualizacao/dispensada"


def versao_dispensada() -> str:
    return str(QSettings(_ORG, _APP).value(_CHAVE_DISPENSADA, "") or "")


def dispensar(versao: str) -> None:
    QSettings(_ORG, _APP).setValue(_CHAVE_DISPENSADA, versao)


class _Consulta(QObject):
    """Consulta o manifesto fora da thread da interface."""

    pronto = Signal(object)  # Novidade ou None

    def __init__(self, url: str, versao_atual: str) -> None:
        super().__init__()
        self._url = url
        self._versao = versao_atual

    def run(self) -> None:
        try:
            resultado = checar(self._url, self._versao)
        except Exception:  # a checagem ja engole tudo; isto e cinto e suspensorio
            resultado = None
        self.pronto.emit(resultado)


class UpdateChecker(QObject):
    """Dispara a consulta e mostra o resultado. Viva enquanto a janela viver."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._window = window
        self._thread: QThread | None = None
        self._consulta: _Consulta | None = None
        self._manual = False

    def checar_em_segundo_plano(self, url: str, *, manual: bool = False) -> None:
        """Consulta sem travar a janela. `manual=True` responde sempre."""
        if not url_segura(url):
            if manual:
                QMessageBox.information(
                    self._window, "PrintNest",
                    "A verificação de atualizações não está disponível "
                    "nesta versão.\n\n"
                    "Quando houver uma versão nova, você será avisado pelo "
                    "canal de suporte onde comprou o PrintNest.",
                )
            return
        if self._thread is not None and self._thread.isRunning():
            return  # ja tem uma consulta em curso
        self._manual = manual
        self._thread = QThread(self)
        self._consulta = _Consulta(url, __version__)
        self._consulta.moveToThread(self._thread)
        self._thread.started.connect(self._consulta.run)
        self._consulta.pronto.connect(self._responder)
        self._consulta.pronto.connect(self._thread.quit)
        self._thread.start()

    def encerrar(self) -> None:
        """Espera a consulta terminar. Chamado no closeEvent da janela: fechar
        com a QThread viva faz o Qt abortar o processo ("QThread: Destroyed
        while thread is still running"), que o usuário vê como o programa
        fechando sozinho. O timeout da rede limita a espera."""
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(8000)

    def _responder(self, novidade: object) -> None:
        manual = self._manual
        if not isinstance(novidade, Novidade):
            if manual:
                QMessageBox.information(
                    self._window, "PrintNest",
                    f"Você já está na versão mais recente ({__version__}).",
                )
            return  # automatico e offline: silencio, nao atrapalha quem trabalha
        if not manual and versao_dispensada() == novidade.versao:
            return  # ja disse "agora nao" para esta versao
        self._mostrar(novidade, manual)

    def _mostrar(self, novidade: Novidade, manual: bool) -> None:
        caixa = QMessageBox(self._window)
        caixa.setWindowTitle("PrintNest")
        caixa.setIcon(QMessageBox.Information)
        caixa.setText(
            f"<b>PrintNest {novidade.versao} disponível</b><br>"
            f"Você está na {__version__}."
        )
        if novidade.notas:
            caixa.setInformativeText(novidade.notas)
        baixar = caixa.addButton("Abrir download", QMessageBox.AcceptRole)
        caixa.addButton("Agora não", QMessageBox.RejectRole)
        pular = (
            None if manual
            else caixa.addButton("Não avisar sobre esta", QMessageBox.DestructiveRole)
        )
        caixa.exec()

        clicado = caixa.clickedButton()
        if clicado is baixar:
            # url_segura ja barrou esquema estranho na origem; reconferido aqui
            # porque isto ABRE algo no sistema do cliente
            if url_segura(novidade.url):
                QDesktopServices.openUrl(QUrl(novidade.url))
        elif pular is not None and clicado is pular:
            dispensar(novidade.versao)
