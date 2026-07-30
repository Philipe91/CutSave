"""Aviso de atualizacao na interface: nao vaza requisicao, nao trava, nao mente."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.infrastructure.updates import Novidade  # noqa: E402
from app.presentation import update_check  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(tmp_path, qapp):
    import tests.presentation.test_main_window as t
    return t._window(tmp_path)


@pytest.fixture
def sem_rede(monkeypatch):
    """Falha o teste se QUALQUER requisicao for feita."""
    def proibido(*_a, **_k):
        raise AssertionError("o app fez requisicao de rede quando nao devia")

    monkeypatch.setattr(update_check, "checar", proibido)
    return proibido


def test_sem_url_nenhuma_nao_faz_requisicao(janela, sem_rede, monkeypatch):
    # Sem endereco NENHUM (nem no config do cliente, nem embutido no exe) o app
    # nao fala com servidor algum. A partir da 1.0.0 o embutido vem preenchido,
    # entao o "desligado" precisa ser encenado aqui — sem isto o teste passaria
    # por engano (o except do _Consulta.run engole o AssertionError do sem_rede)
    # e ainda deixaria uma QThread orfa.
    from app.infrastructure import updates

    monkeypatch.setattr(updates, "URL_MANIFESTO_PADRAO", "")
    assert janela._settings.update_url == ""
    assert janela._update_url() == ""
    janela._check_updates_on_start()  # sem_rede explode se tentar


def test_usa_o_endereco_embutido_sem_config_do_cliente(janela, monkeypatch):
    # o cliente nao edita config.json: o endereco tem de vir do executavel
    from app.infrastructure import updates

    monkeypatch.setattr(updates, "URL_MANIFESTO_PADRAO", "https://site/versao.json")
    assert janela._settings.update_url == ""
    assert janela._update_url() == "https://site/versao.json"

    # e o config do cliente, quando existe, tem prioridade
    janela._settings.update_url = "https://cliente/v.json"
    assert janela._update_url() == "https://cliente/v.json"


def test_desligar_o_aviso_na_abertura_e_respeitado(janela, sem_rede):
    janela._settings.update_url = "https://exemplo.invalido/versao.json"
    janela._settings.update_check_on_start = False
    janela._check_updates_on_start()  # sem_rede explode se tentar


def test_menu_ajuda_tem_procurar_atualizacoes(janela):
    rotulos = []
    for acao in janela.menuBar().actions():
        if acao.text().replace("&", "").startswith("Ajuda"):
            rotulos = [a.text() for a in acao.menu().actions()]
    assert any("atualiza" in r.lower() for r in rotulos), rotulos


def test_check_manual_sem_url_avisa_em_vez_de_ficar_mudo(janela, monkeypatch, sem_rede):
    # check manual mudo parece que o programa quebrou
    # (mesma encenação do teste acima: com o endereço embutido preenchido, este
    # ramo só existe se não houver endereço nenhum — sem o monkeypatch a
    # consulta REAL sobe uma QThread que ninguém encerra e a suíte trava)
    from app.infrastructure import updates

    monkeypatch.setattr(updates, "URL_MANIFESTO_PADRAO", "")
    vistos = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **k: vistos.append(a[2]) or QMessageBox.Ok
    )
    janela._check_updates_manual()
    assert vistos and "atualiza" in vistos[0].lower()


def test_versao_ja_dispensada_nao_avisa_de_novo(janela, monkeypatch):
    # quem clicou "Nao avisar sobre esta" nao pode ser perturbado a cada abertura
    monkeypatch.setattr(update_check, "versao_dispensada", lambda: "2.0.0")
    mostrados = []
    checker = janela._updater()
    monkeypatch.setattr(checker, "_mostrar", lambda n, m: mostrados.append(n))
    checker._manual = False
    checker._responder(Novidade("2.0.0", "https://x/y.exe", ""))
    assert mostrados == []

    # mas o check MANUAL responde mesmo assim
    checker._manual = True
    checker._responder(Novidade("2.0.0", "https://x/y.exe", ""))
    assert len(mostrados) == 1


def test_sem_novidade_no_automatico_fica_calado(janela, monkeypatch):
    vistos = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **k: vistos.append(a[2]) or QMessageBox.Ok
    )
    checker = janela._updater()
    checker._manual = False
    checker._responder(None)
    assert vistos == []  # offline na abertura nao atrapalha quem so quer trabalhar

    checker._manual = True  # no manual, confirma que esta em dia
    checker._responder(None)
    assert vistos and "recente" in vistos[0].lower()


def test_encerrar_sem_consulta_nao_quebra(janela):
    # closeEvent chama isto mesmo se ninguem nunca checou atualizacao
    janela._updater().encerrar()
