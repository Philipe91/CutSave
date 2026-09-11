"""Janela de acompanhamento da exportacao em imagem (11/09/2026).

O que ela promete: o trabalho roda fora da thread da UI, a janela so fecha
quando ele termina, Cancelar chega ao trabalho e o desfecho (resultado ou
excecao) volta para quem chamou. Tempo e estimativa sao funcoes puras.
"""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.infrastructure.exporters.pikepdf_print_exporter import ExportacaoCancelada  # noqa: E402
from app.presentation.panels import export_progress_dialog as mod
from app.presentation.panels.export_progress_dialog import (
    ExportandoImagemDialog,
    estimativa_restante,
    formatar_tempo,
)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- funcoes puras ----
def test_formatar_tempo():
    assert formatar_tempo(0) == "0:00"
    assert formatar_tempo(65) == "1:05"
    assert formatar_tempo(3599.6) == "60:00"  # nao vira hora
    assert formatar_tempo(-3) == "0:00"


def test_estimativa_so_depois_de_uma_fracao_minima():
    assert estimativa_restante(10, 0.05) is None  # cedo demais: nao chuta
    assert estimativa_restante(10, 0.5) == 10
    assert estimativa_restante(30, 0.1) == 270
    assert estimativa_restante(0, 0.5) is None


# ---- janela ----
def test_executa_o_trabalho_e_devolve_o_resultado(qapp):
    def trabalho(progresso, cancelado):
        progresso(0.0, "Montando o documento…")
        progresso(0.5, "Exportando")
        return ["chapa.png"]

    dlg = ExportandoImagemDialog()
    resultado, erro = dlg.executar(trabalho)
    assert resultado == ["chapa.png"] and erro is None
    assert not dlg.rodando()
    assert dlg.etapa() == "Exportando"
    assert dlg._barra.value() == 50


def test_excecao_do_trabalho_volta_para_quem_chamou(qapp):
    def trabalho(progresso, cancelado):
        raise RuntimeError("disco cheio")

    resultado, erro = ExportandoImagemDialog().executar(trabalho)
    assert resultado is None
    assert isinstance(erro, RuntimeError) and "disco cheio" in str(erro)


def test_cancelar_chega_ao_trabalho(qapp):
    def trabalho(progresso, cancelado):
        progresso(0.2, "Exportando")
        fim = time.monotonic() + 5.0
        while not cancelado():  # o exportador consulta entre faixas
            if time.monotonic() > fim:
                return "nao cancelou"
            time.sleep(0.01)
        raise ExportacaoCancelada()

    dlg = ExportandoImagemDialog()
    QTimer.singleShot(100, dlg._cancelar)
    resultado, erro = dlg.executar(trabalho)
    assert resultado is None
    assert isinstance(erro, ExportacaoCancelada)
    assert "cancelando" in dlg.tempo().lower()


def test_esc_e_fechar_viram_cancelar_enquanto_roda(qapp):
    def trabalho(progresso, cancelado):
        while not cancelado():
            time.sleep(0.01)
        raise ExportacaoCancelada()

    dlg = ExportandoImagemDialog()
    QTimer.singleShot(100, dlg.reject)  # Esc
    _, erro = dlg.executar(trabalho)
    assert isinstance(erro, ExportacaoCancelada)


def test_dica_avanca_e_da_a_volta(qapp):
    dlg = ExportandoImagemDialog()
    primeira = dlg.dica()
    dlg._proxima_dica()
    assert dlg.dica() != primeira
    for _ in range(len(mod._EXPORT_TIPS) - 1):
        dlg._proxima_dica()
    assert dlg.dica() == primeira


def test_tempo_mostra_estimativa_depois_da_primeira_fracao(qapp):
    dlg = ExportandoImagemDialog()
    dlg._inicio = time.monotonic() - 20
    dlg._on_progresso(0.0, "Montando o documento…")
    assert "calculando" in dlg.tempo()
    dlg._on_progresso(0.5, "Exportando")
    assert "restante ~0:20" in dlg.tempo()
    assert dlg.tempo().startswith("Decorrido 0:20")
