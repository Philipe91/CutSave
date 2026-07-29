"""Recolher os painéis laterais devolve espaço para a chapa.

É o mecanismo dos dockers do CorelDRAW ("Collapse docker": recolhido sobra a
aba, clicar nela reabre). Medido em 29/07/2026 com um arquivo carregado:

    tela        chapa aberta -> biblioteca recolhida
    1920x1080      972px    ->  1276px
    1366x768       418px    ->   722px
    1092x614       144px    ->   448px

Num notebook a 125% a area de trabalho TRIPLICA. Por isso estes testes olham
o ganho real, nao so se o widget sumiu da tela.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def sem_escolha_anterior():
    """A escolha do usuario mora em QSettings e vazaria de um teste ao outro."""
    s = QSettings("PrintNest", "PrintNest")
    s.remove("paineis")
    yield
    s.remove("paineis")


@pytest.fixture
def janela(tmp_path, qapp):
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w.resize(1600, 900)
    w.show()
    qapp.processEvents()
    w.add_paths([t._two_page_pdf(tmp_path)])
    w.generate(blocking=True)
    qapp.processEvents()
    yield w
    w.close()


def _assentar(qapp, vezes: int = 8) -> None:
    for _ in range(vezes):
        qapp.processEvents()


def test_recolher_biblioteca_aumenta_a_chapa(janela, qapp):
    w = janela
    w.resize(1366, 768)
    _assentar(qapp)
    antes = w._view.width()

    w._set_biblioteca_visivel(False)
    _assentar(qapp)

    assert not w._library_wrap.isVisible(), "a biblioteca continuou na tela"
    assert w._library_strip.isVisible(), "sumiu sem deixar a faixa de voltar"
    assert w._view.width() > antes + 200, (
        f"recolher rendeu so {w._view.width() - antes}px de chapa "
        f"({antes} -> {w._view.width()})"
    )


def test_a_faixa_traz_a_biblioteca_de_volta(janela, qapp):
    w = janela
    w._set_biblioteca_visivel(False)
    _assentar(qapp)
    largura_recolhida = w._view.width()

    # e o que acontece ao clicar na faixa
    w._library_strip._ao_clicar()
    _assentar(qapp)

    assert w._library_wrap.isVisible(), "a faixa nao trouxe a biblioteca de volta"
    assert not w._library_strip.isVisible()
    assert w._view.width() < largura_recolhida, "a chapa nao devolveu o espaco"


def test_recolher_propriedades_deixa_o_trilho(janela, qapp):
    w = janela
    w.resize(1366, 768)
    _assentar(qapp)
    antes = w._view.width()

    w._set_propriedades_visivel(False)
    _assentar(qapp)

    assert w._props_tabs.is_collapsed()
    assert w._props_tabs.isVisible(), "o trilho tem de ficar: e a aba de voltar"
    assert w._props_wrap.width() <= w._props_tabs.rail_width() + 8, (
        f"recolhido o painel ainda ocupa {w._props_wrap.width()}px"
    )
    assert w._view.width() > antes + 200


def test_clicar_no_icone_ativo_recolhe_e_reabre(janela, qapp):
    """O clique do trilho e o caminho real do usuario — nao pode entrar em laco."""
    w = janela
    tabs = w._props_tabs
    ativo = tabs.currentIndex()

    tabs._on_rail_clicked(ativo)  # clique no icone ja aceso
    _assentar(qapp)
    assert tabs.is_collapsed()
    assert w._act_propriedades.isChecked() is False, "o menu Exibir ficou dessincronizado"

    tabs._on_rail_clicked(1)  # recolhido, qualquer icone reabre naquela secao
    _assentar(qapp)
    assert not tabs.is_collapsed()
    assert tabs.currentIndex() == 1
    assert w._act_propriedades.isChecked() is True


def test_menu_exibir_liga_e_desliga(janela, qapp):
    w = janela
    w._act_biblioteca.trigger()  # estava marcado: desmarca e recolhe
    _assentar(qapp)
    assert not w._library_wrap.isVisible()

    w._act_biblioteca.trigger()
    _assentar(qapp)
    assert w._library_wrap.isVisible()


def test_tela_estreita_abre_com_a_biblioteca_recolhida(tmp_path, qapp):
    """No notebook da loja os tres paineis juntos deixavam a chapa com 144px."""
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w.resize(1092, 614)
    w.show()
    _assentar(qapp)
    assert not w._library_wrap.isVisible(), (
        "janela estreita devia abrir com a biblioteca recolhida"
    )
    w.close()


def test_tela_larga_abre_com_tudo_aberto(tmp_path, qapp):
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w.resize(1600, 900)
    w.show()
    _assentar(qapp)
    assert w._library_wrap.isVisible()
    assert not w._props_tabs.is_collapsed()
    w.close()


def test_recolher_por_causa_da_tela_nao_vira_escolha_do_usuario(tmp_path, qapp):
    """Senao ele levaria o arquivo para um monitor grande e continuaria estreito."""
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w.resize(1092, 614)
    w.show()
    _assentar(qapp)
    w.close()

    assert QSettings("PrintNest", "PrintNest").value("paineis/biblioteca", None) is None

    w2 = t._window(tmp_path)
    w2.resize(1600, 900)
    w2.show()
    _assentar(qapp)
    assert w2._library_wrap.isVisible(), "voltou recolhida num monitor grande"
    w2.close()


def test_a_setinha_da_biblioteca_esta_visivel_e_recolhe(janela, qapp):
    """Pedido do Philipe (29/07): o botao de recolher tem de SE VER.

    Antes so existia o F9, o menu Exibir e um clique no icone ja aceso do
    trilho — nenhum deles se descobre olhando a tela.
    """
    w = janela
    botao = w._btn_recolher_lib
    assert botao.isVisible(), "a setinha da biblioteca nao esta na tela"
    assert botao.width() >= 20 and botao.height() >= 18, (
        f"a setinha ficou pequena demais para acertar: {botao.width()}x{botao.height()}"
    )
    assert not botao.icon().isNull(), "a setinha esta sem icone"

    botao.click()
    _assentar(qapp)
    assert not w._library_wrap.isVisible(), "a setinha nao recolheu a biblioteca"


def test_o_trilho_tem_botao_visivel_de_recolher(janela, qapp):
    w = janela
    botao = w._props_tabs._btn_collapse
    assert botao.isVisible(), "o painel da direita nao tem botao de recolher"
    assert not botao.icon().isNull()

    botao.click()  # recolhe
    _assentar(qapp)
    assert w._props_tabs.is_collapsed()
    assert botao.isVisible(), "o botao sumiu junto com o painel: nao ha volta"
    assert w._act_propriedades.isChecked() is False, "o menu Exibir dessincronizou"

    botao.click()  # e o MESMO botao traz de volta
    _assentar(qapp)
    assert not w._props_tabs.is_collapsed()
    assert w._act_propriedades.isChecked() is True


def test_alca_no_divisor_recolhe_e_reabre(janela, qapp):
    """Pedido do Philipe (29/07): a alca tem de estar NO DIVISOR, no meio.

    Ele marcou de vermelho as duas linhas — biblioteca|chapa e chapa|painel.
    Botao dentro do painel passava batido.
    """
    from app.presentation.widgets.splitter_alcas import _Alca

    w = janela
    sp = w._main_splitter
    for indice, nome in ((1, "biblioteca"), (2, "painel de campos")):
        alca = sp.handle(indice)
        assert isinstance(alca, _Alca), f"o divisor da {nome} nao tem alca"
        assert alca._btn.isVisible(), f"a alca da {nome} nao esta na tela"
        assert not alca._btn.icon().isNull(), f"a alca da {nome} esta sem seta"
        assert alca._btn.width() >= 12 and alca._btn.height() >= 40, (
            f"alca da {nome} pequena demais: "
            f"{alca._btn.width()}x{alca._btn.height()}"
        )
        # e ela fica no MEIO da altura, nao colada no topo
        centro = alca._btn.y() + alca._btn.height() / 2
        assert abs(centro - alca.height() / 2) <= 2, (
            f"a alca da {nome} nao esta centralizada na vertical"
        )

    sp.handle(1)._btn.click()
    _assentar(qapp)
    assert not w._library_wrap.isVisible(), "a alca nao recolheu a biblioteca"
    sp.handle(1)._btn.click()
    _assentar(qapp)
    assert w._library_wrap.isVisible(), "a mesma alca nao trouxe de volta"

    sp.handle(2)._btn.click()
    _assentar(qapp)
    assert w._props_tabs.is_collapsed(), "a alca nao recolheu o painel"
    sp.handle(2)._btn.click()
    _assentar(qapp)
    assert not w._props_tabs.is_collapsed()


def test_tutorial_reabre_o_painel_recolhido(janela, qapp):
    """Passo que aponta para botao recolhido apontaria para o nada.

    E a reclamacao de 28/07 de volta ("so aparece a mensagem, nao mostra onde
    clicar"), agora por um caminho novo: o painel recolhido.
    """
    from app.presentation import tutorials

    w = janela
    w._set_biblioteca_visivel(False)
    w._set_propriedades_visivel(False)
    _assentar(qapp)

    # o passo do "Colocar na chapa" — o botao mora DENTRO da biblioteca
    passo = next(p for p in tutorials.guiado(w) if p.target is w._btn_place)
    assert passo.preparar is not None, (
        "o passo aponta para um botao da biblioteca sem reabrir a biblioteca"
    )
    passo.preparar()
    _assentar(qapp)
    assert w._library_wrap.isVisible(), "o tutorial nao reabriu a biblioteca"
    assert w._btn_place.isVisible(), "o botao do passo continua fora da tela"

    # e o mesmo para a aba Documento, que mora no painel da direita
    tutorials._abrir_documento(w, 0)()
    _assentar(qapp)
    assert not w._props_tabs.is_collapsed(), "o tutorial nao reabriu o painel"


def test_escolha_do_usuario_e_lembrada(tmp_path, qapp):
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w.resize(1600, 900)
    w.show()
    _assentar(qapp)
    w._act_biblioteca.trigger()  # escolha explicita: recolher
    _assentar(qapp)
    w.close()

    w2 = t._window(tmp_path)
    w2.resize(1600, 900)
    w2.show()
    _assentar(qapp)
    assert not w2._library_wrap.isVisible(), "a escolha do usuario nao foi lembrada"
    w2.close()
