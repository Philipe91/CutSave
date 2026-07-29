"""A janela tem de caber em monitor pequeno, inclusive COM arquivo carregado.

Relato real (29/07/2026, PC da vendedora): "some funções, corta informação, a
biblioteca fica só uma lista". Medido na epoca: com um arquivo na producao a
janela exigia 2678x865 — nao cabia nem em Full HD.

A causa era altura/largura MINIMA herdada do conteudo: a barra da Faca sozinha
pedia 1676px e a aba Selecao 619px de altura. Quem tem de rolar e o painel,
nao a janela crescer.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# telas reais de loja: (largura, altura, apelido). A 2a e a 1a com escala do
# Windows em 125%, que e o que mais aperta.
TELAS = [
    (1920, 1080, "Full HD"),
    (1536, 864, "Full HD a 125%"),
    (1366, 768, "notebook comum"),
    (1280, 720, "monitor pequeno"),
    (1092, 614, "notebook a 125%"),
]


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela_com_arquivo(tmp_path, qapp):
    """Janela no estado de TRABALHO: a barra da Faca so existe com producao."""
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


@pytest.mark.parametrize(("larg", "alt", "apelido"), TELAS)
def test_janela_cabe_na_tela(janela_com_arquivo, larg, alt, apelido):
    m = janela_com_arquivo.minimumSizeHint()
    assert m.width() <= larg and m.height() <= alt, (
        f"nao cabe em {apelido} ({larg}x{alt}): "
        f"minimo da janela e {m.width()}x{m.height()}"
    )


def test_encolher_nao_esconde_os_paineis(janela_com_arquivo, qapp):
    # "some funcoes" era isto: ao apertar, painel sumia em vez de rolar
    w = janela_com_arquivo
    w.resize(1092, 614)
    qapp.processEvents()
    for nome in ("_props_tabs", "_view", "_table", "_prop_bar"):
        widget = getattr(w, nome, None)
        assert widget is not None, nome
        assert widget.isVisible(), f"{nome} sumiu ao encolher a janela"
        assert widget.width() > 0 and widget.height() > 0, f"{nome} ficou sem area"


@pytest.mark.parametrize(("larg", "alt", "apelido"), TELAS)
def test_painel_documento_nao_e_cortado(janela_com_arquivo, qapp, larg, alt, apelido):
    """O painel de campos rola quando nao cabe — nunca corta em silencio.

    Medido em 29/07: o painel recebia 320px para um conteudo de 542px e o
    corte acontecia ate em Full HD ("Chapas", "Registro" e o botao Aplicar
    ficavam fora). Corte sem rolagem = informacao perdida.
    """
    w = janela_com_arquivo
    w.resize(larg, alt)
    for _ in range(6):
        qapp.processEvents()
    doc = w._doc_widget
    scroll = doc.parentWidget().parentWidget()  # viewport -> QScrollArea
    precisa = doc.minimumSizeHint().width()
    # o que importa e a area VISIVEL (viewport), nao a largura do widget: com
    # a rolagem desligada o Qt deixa o widget com 542px e simplesmente esconde
    # o que passa da janelinha — foi assim que o corte passou despercebido
    visivel = scroll.viewport().width()
    # olhar o alcance da barra nao serve: com a politica AlwaysOff o Qt mantem
    # o alcance e so ESCONDE a barra, entao o teste passava com o painel
    # cortado. O que vale e a barra poder aparecer.
    rola = scroll.horizontalScrollBarPolicy() != Qt.ScrollBarAlwaysOff
    assert visivel >= precisa or rola, (
        f"em {apelido} o painel Documento e cortado: mostra {visivel}px "
        f"de {precisa}px e nao oferece rolagem"
    )


@pytest.mark.parametrize(("larg", "alt", "apelido"), TELAS)
def test_paineis_laterais_deixam_espaco_para_a_chapa(janela_com_arquivo, qapp, larg, alt, apelido):
    """Biblioteca + painel de campos nao podem engolir a area de trabalho."""
    w = janela_com_arquivo
    w.resize(larg, alt)
    for _ in range(6):
        qapp.processEvents()
    lados = w._library_wrap.width() + w._props_wrap.width()
    assert lados <= larg * 0.68, (
        f"em {apelido} os paineis ocupam {lados}px de {larg} — sobra pouco "
        f"para a chapa"
    )
    # 120 e nao 140: as alcas de recolher no divisor (pedido de 29/07) sao
    # visiveis de proposito e custam ~20px de largura no total. Na pratica
    # este e o caso em que a biblioteca ABRE RECOLHIDA (janela < 1200px), e
    # ai a chapa fica com ~500px — ver test_paineis_recolhem.
    assert w._view.width() >= 120, (
        f"em {apelido} a area de trabalho ficou com {w._view.width()}px"
    )


def test_barra_da_faca_rola_em_vez_de_espremer(janela_com_arquivo, qapp):
    # a barra junta Projeto/Objeto/Grupo + Faca e pede ~2660px. Numa janela
    # estreita ela tem de manter o tamanho e ROLAR, nunca ser cortada.
    w = janela_com_arquivo
    w.resize(1092, 614)
    qapp.processEvents()
    scroll = w._prop_bar_scroll
    assert w._prop_bar.width() >= w._prop_bar.minimumSizeHint().width(), (
        "a barra da Faca foi espremida abaixo do proprio minimo"
    )
    assert scroll.width() < w._prop_bar.width(), "sem rolagem, a barra seria cortada"
