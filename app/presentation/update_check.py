"""Aviso de atualizacao na interface: consulta em thread e avisa o usuario.

A consulta faz REDE, entao nunca roda na thread da interface — foi exatamente
esse tipo de coisa que deixava a janela congelada. Ela roda numa thread Python
DAEMON e o resultado volta por sinal (fila do Qt -> thread da interface).

Por que nao QThread (13/10/2026): o timeout da rede nao cobre o DNS. Com o DNS
pendurado, fechar o app esperava 8 s e depois a QThread era destruida viva
("QThread: Destroyed while thread is still running" -> abort do processo). Uma
thread daemon nao segura o fechamento: o processo sai e ela morre junto.

O aviso automatico aparece UMA VEZ por versao: quem clicou "Agora nao" nao e
perturbado de novo por aquela versao (o dispensado fica em QSettings, mesmo
escopo do tour). Ja o "Procurar atualizacoes..." do menu Ajuda sempre responde,
inclusive quando esta tudo em dia — check manual mudo parece que quebrou.
"""

from __future__ import annotations

import contextlib
import threading

from PySide6.QtCore import QObject, QSettings, QUrl, Signal
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
    """Ponte thread -> interface: o sinal emitido na thread daemon chega na
    thread da interface (conexao enfileirada). SEM pai de proposito: a thread
    segura a referencia, entao fechar a janela no meio da consulta nao destroi
    o emissor debaixo dela."""

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
        # app ja fechando: ninguem mais para avisar
        with contextlib.suppress(RuntimeError):
            self.pronto.emit(resultado)


class UpdateChecker(QObject):
    """Dispara a consulta e mostra o resultado. Viva enquanto a janela viver."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._window = window
        self._thread: threading.Thread | None = None
        self._consulta: _Consulta | None = None
        self._manual = False
        self._encerrado = False

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
        if self._thread is not None and self._thread.is_alive():
            # ja tem uma consulta em curso: aproveita a resposta dela, mas o
            # clique MANUAL tem de responder — antes era descartado e o menu
            # "Procurar atualizacoes..." ficava mudo (13/10/2026)
            self._manual = self._manual or manual
            return
        self._manual = manual
        self._encerrado = False
        consulta = _Consulta(url, __version__)
        consulta.pronto.connect(self._responder)
        self._consulta = consulta
        self._thread = threading.Thread(
            target=consulta.run, name="printnest-update-check", daemon=True
        )
        self._thread.start()

    def encerrar(self) -> None:
        """Chamado no closeEvent da janela. NAO espera a rede: a thread e
        daemon (morre com o processo) e a resposta tardia e descartada.
        Antes esperava ate 8 s e, com o DNS pendurado, a QThread era
        destruida viva e o Qt abortava o processo (13/10/2026)."""
        self._encerrado = True
        consulta = self._consulta
        if consulta is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                consulta.pronto.disconnect(self._responder)

    def _responder(self, novidade: object) -> None:
        if self._encerrado:
            return  # janela fechando: resposta tardia nao abre aviso
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
