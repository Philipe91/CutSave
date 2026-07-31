"""O botão "Modo Corte" da ribbon tem destaque PRÓPRIO, e não o do "Gerar Faca".

São dois botões que fazem coisas diferentes: o "Gerar Faca" cria o contorno de
corte da arte; o "Modo Corte" abre o fluxo separado de laser/CNC. Pintar os dois
com o mesmo azul convida o operador a clicar no errado, e o Modo Corte sem
destaque nenhum simplesmente desaparecia no meio da barra.

Estes testes travam as três decisões: destaque existe, é DIFERENTE do CTA, e o
ícone não é a tesoura (a tesoura é a faca).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.presentation import icons, theme  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(tmp_path, qapp):
    import tests.presentation.test_main_window as t

    # o QSS entra ANTES de qualquer medição: sem ele a geometria mente
    theme.apply(qapp)
    w = t._window(tmp_path)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def _botao_modo_corte(janela) -> QToolButton:
    for btn in janela._ribbon.findChildren(QToolButton):
        if btn.text().strip() == "Modo Corte":
            return btn
    raise AssertionError("botao 'Modo Corte' nao encontrado na ribbon")


def test_modo_corte_tem_destaque_proprio(janela):
    assert _botao_modo_corte(janela).property("accent") == "corte"


def test_nao_usa_o_mesmo_destaque_do_gerar_faca(janela):
    """O CTA da faca continua sendo o azul padrão; o Modo Corte, não."""
    assert janela._ct_gerar.property("accent") == "true"
    assert _botao_modo_corte(janela).property("accent") != "true"


def test_as_duas_cores_sao_diferentes(qapp):
    """Destacado NÃO pode virar 'igualzinho ao Gerar Faca'."""
    theme.apply(qapp)
    qss = qapp.styleSheet()
    assert 'QToolButton[accent="corte"]' in qss
    assert theme.ACCENT_PRESSED != theme.ACCENT, (
        "o azul do Modo Corte coincidiu com o do CTA — o destaque some"
    )


def test_o_bloco_novo_nao_derruba_a_regra_seguinte(qapp):
    """Armadilha registrada no projeto: caractere não-ASCII em comentário de
    QSS mata a regra logo abaixo. Aqui a vítima seria o rótulo de legenda."""
    theme.apply(qapp)
    assert 'QLabel[role="caption"]' in qapp.styleSheet()


def test_o_icone_nao_e_a_tesoura(janela):
    """A tesoura é a linguagem da FACA. O Modo Corte é laser/CNC."""
    btn = _botao_modo_corte(janela)
    atual = btn.icon().pixmap(18, 18).toImage()
    tesoura = icons.pixmap("scissors", theme.ICON_ON_ACCENT, 18).toImage()
    assert atual != tesoura


def test_o_icone_e_o_alvo(janela):
    """Escolha do dono: o alvo (ponto focal do laser)."""
    btn = _botao_modo_corte(janela)
    esperado = icons.pixmap("target", theme.ICON_ON_ACCENT, 18).toImage()
    assert btn.icon().pixmap(18, 18).toImage() == esperado


def test_o_svg_do_alvo_existe_no_repositorio():
    """O ícone vive num arquivo: se ele sumir, `icons.icon` devolve um QIcon
    VAZIO e o botão fica sem símbolo no cliente, sem erro nenhum. O spec varre
    assets/** inteiro, então basta o arquivo existir aqui."""
    from app.shared.resources import resource_path

    assert (resource_path("assets/icons") / "target.svg").exists()


def test_a_janela_continua_cabendo_no_notebook(janela, qapp):
    """O botão colorido é mais largo (texto em negrito). Se ele empurrar o
    mínimo da janela acima de 1366px, quem tem notebook comum perde área."""
    janela.resize(1366, 768)
    for _ in range(6):
        qapp.processEvents()
    minimo = janela.minimumSizeHint()
    assert minimo.width() <= 1366, (
        f"a barra passou a exigir {minimo.width()}px de largura"
    )
