"""Ciclo de vida da thread de encaixe do Modo Corte.

ESCOPO — leia antes de mexer:
Este arquivo NAO trata do BUG-QA-1 (os modulos do Modo Corte que morriam com
0xC0000005). Aquilo era outra coisa: as fixtures chamavam deleteLater() e
ninguem drenava os eventos DeferredDelete, entao as janelas se acumulavam e o
pytest_sessionfinish fechava todas de uma vez. Corrigido em tests/conftest.py
e vigiado por tests/qa/test_qa_g2_saida_limpa.py.

O que este arquivo trava e um defeito INDEPENDENTE e mais estreito: a
referencia self._nest_thread caia no sinal `done`, que sai de dentro de run().
No PySide6 a entrega de `done` e ENFILEIRADA para a thread principal (medido),
entao na pratica run() quase sempre ja retornou quando o slot roda — a corrida
existe, mas e de milissegundos. Nao ha crash conhecido causado por ela; os
testes abaixo existem para que a invariante nao volte a ser violada, nao para
comemorar uma correcao de crash.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.presentation import cut_mode_dialog as mod  # noqa: E402
from app.presentation.cut_mode_dialog import CutModeDialog  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_XMLNS = 'xmlns="http://www.w3.org/2000/svg"'


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp):
    dlg = CutModeDialog()
    dlg._seconds.setValue(0.5)
    yield dlg
    dlg.deleteLater()


def _rect_svg(tmp_path, w=40.0, h=20.0, name="peca.svg") -> str:
    path = tmp_path / name
    path.write_text(
        f'<svg {_XMLNS} width="100mm" height="100mm" viewBox="0 0 100 100">'
        f'<rect x="0" y="0" width="{w}" height="{h}"/></svg>',
        encoding="utf-8",
    )
    return str(path)


def test_done_nao_esquece_a_thread(dialog, monkeypatch):
    """`done` e emitido de DENTRO de run(): a thread pode estar viva.

    Zerando a referencia aqui, reject()/closeEvent() enxergavam None e
    liberavam destruir o dialogo — que e o PAI da QThread.
    """
    monkeypatch.setattr(mod.QMessageBox, "warning", lambda *a, **k: None)
    sentinela = object()
    dialog._nest_thread = sentinela

    dialog._on_nest_done([], None, RuntimeError("falha qualquer"))

    assert dialog._nest_thread is sentinela
    dialog._nest_thread = None  # a fixture nao pode tentar esperar a sentinela


def test_a_referencia_cai_quando_a_thread_termina(dialog, qapp, tmp_path):
    """`finished` (nao `done`) e quem pode esquecer a thread com seguranca."""
    dialog.add_vector_file(_rect_svg(tmp_path))
    dialog._compute = lambda uc, shapes, material, length: ()

    dialog._on_nest()
    thread = dialog._nest_thread
    assert thread is not None, "_on_nest deveria ter guardado a thread"
    assert thread.wait(30000), "a thread de encaixe nao terminou"

    # `finished` chega pelo laco de eventos: sem drenar, a referencia fica.
    for _ in range(200):
        qapp.processEvents()
        if dialog._nest_thread is None:
            break
    assert dialog._nest_thread is None


def test_nao_fecha_com_a_thread_rodando(dialog, monkeypatch):
    """Enquanto a thread roda, fechar e recusado — destruir o dialogo levaria
    junto uma QThread em execucao (ela e filha dele)."""

    class _Viva:
        def isRunning(self):
            return True

    dialog._nest_thread = _Viva()
    evento = QCloseEvent()
    evento.accept()

    dialog.closeEvent(evento)

    assert not evento.isAccepted()
    assert "Aguarde" in dialog._status.text()
    dialog._nest_thread = None


def test_encerrar_thread_sobrevive_a_thread_ja_destruida(dialog):
    """`finished` tambem dispara deleteLater(): quando _encerrar_thread roda
    depois disso, tocar no objeto levanta RuntimeError. Nao pode vazar."""

    class _Morta:
        def isRunning(self):
            raise RuntimeError("Internal C++ object already deleted.")

    dialog._nest_thread = _Morta()
    dialog._encerrar_thread()
    assert dialog._nest_thread is None
