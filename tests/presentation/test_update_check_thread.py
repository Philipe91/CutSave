"""Consulta de atualizacao: fechar o app com a rede pendurada nao derruba nada,
e o "Procurar atualizacoes..." nunca fica mudo (13/10/2026).

Cenario real: o timeout da rede nao cobre o DNS; com o DNS pendurado o
encerrar() esperava 8 s e depois a QThread era destruida viva ("QThread:
Destroyed while thread is still running" -> abort do processo).
"""

from __future__ import annotations

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.infrastructure.updates import Novidade  # noqa: E402
from app.presentation import update_check  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget  # noqa: E402

_URL = "https://exemplo.com/manifesto.json"


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def rede_pendurada(monkeypatch):
    liberar = threading.Event()
    chamadas = []

    def _checar(url, versao):
        chamadas.append(url)
        liberar.wait(10)
        return Novidade("9.9.9", "https://exemplo.com/x.exe", "")

    monkeypatch.setattr(update_check, "url_segura", lambda u: True)
    monkeypatch.setattr(update_check, "checar", _checar)
    yield liberar, chamadas
    liberar.set()


def _esperar(qapp, cond, segundos=3.0):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_encerrar_nao_espera_a_rede_pendurada(qapp, rede_pendurada):
    liberar, chamadas = rede_pendurada
    janela = QWidget()
    checker = update_check.UpdateChecker(janela)
    checker.checar_em_segundo_plano(_URL)
    assert _esperar(qapp, lambda: chamadas)
    t0 = time.monotonic()
    checker.encerrar()
    assert time.monotonic() - t0 < 1.0  # antes: ate 8 s e depois abort
    # janela (e o checker, filho dela) destruidos com a consulta ainda viva
    janela.deleteLater()
    qapp.processEvents()
    liberar.set()
    qapp.processEvents()  # resposta tardia nao pode quebrar nem abrir aviso


def test_resposta_depois_de_encerrar_e_ignorada(qapp, rede_pendurada,
                                                monkeypatch):
    liberar, chamadas = rede_pendurada
    mostrados = []
    janela = QWidget()
    checker = update_check.UpdateChecker(janela)
    monkeypatch.setattr(checker, "_mostrar", lambda n, m: mostrados.append(n))
    checker.checar_em_segundo_plano(_URL)
    assert _esperar(qapp, lambda: chamadas)
    checker.encerrar()
    liberar.set()
    _esperar(qapp, lambda: False, 0.3)
    assert mostrados == []
    janela.deleteLater()


def test_resposta_chega_na_thread_da_interface(qapp, rede_pendurada,
                                               monkeypatch):
    liberar, _ = rede_pendurada
    vistos = []
    janela = QWidget()
    checker = update_check.UpdateChecker(janela)
    monkeypatch.setattr(
        checker, "_mostrar",
        lambda n, m: vistos.append(threading.current_thread()
                                   is threading.main_thread()))
    checker.checar_em_segundo_plano(_URL)
    liberar.set()
    assert _esperar(qapp, lambda: vistos)
    assert vistos == [True]
    janela.deleteLater()


def test_manual_durante_consulta_automatica_responde(qapp, rede_pendurada,
                                                    monkeypatch):
    # clicou "Procurar atualizacoes..." com a consulta da abertura em curso:
    # antes o clique era descartado e nada aparecia (parecia quebrado)
    liberar, chamadas = rede_pendurada
    vistos = []
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda *a, **k: vistos.append(a[2]) or QMessageBox.Ok)
    monkeypatch.setattr(update_check, "checar",
                        lambda u, v: (chamadas.append(u), liberar.wait(10),
                                      None)[2])
    janela = QWidget()
    checker = update_check.UpdateChecker(janela)
    checker.checar_em_segundo_plano(_URL)              # automatico
    assert _esperar(qapp, lambda: chamadas)
    checker.checar_em_segundo_plano(_URL, manual=True)  # clique no menu
    liberar.set()
    assert _esperar(qapp, lambda: vistos)
    assert "recente" in vistos[0].lower()
    janela.deleteLater()
