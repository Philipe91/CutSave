"""Ícones em alta resolução (H1): o pixmap acompanha o devicePixelRatio da tela.

O que estes testes protegem, e que custou caro descobrir:

1. **dpr = 1 é no-op.** Quem está a 100% (a maioria dos clientes de hoje) tem
   de continuar vendo exatamente o mesmo desenho de antes. Qualquer mudança
   aqui é regressão, não melhoria.
2. **Não escalar duas vezes.** O QPainter aberto sobre um pixmap com
   devicePixelRatio JÁ aplica o fator sozinho. Chamar `painter.scale(dpr, dpr)`
   por cima disso desenha o ícone `dpr` vezes maior do que o quadro e ele sai
   recortado — foi o defeito real da primeira tentativa, e visualmente ele
   passa despercebido em alguns ícones.
3. **O dpr entra na chave do cache.** Sem isso o primeiro monitor a pedir o
   ícone congela a resolução dele para o resto da sessão.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.presentation import faca_icons, icons, theme  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

DPRS = (1.0, 1.25, 1.5, 2.0)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _fracao_ocupada(pm) -> float:
    """Largura do desenho (o que não é transparente) como fração do quadro.

    É assim que o escalonamento duplo aparece: o desenho vaza do quadro e a
    fração desaba, porque só sobra um pedaço dele."""
    img = pm.toImage()
    xs = [
        x
        for y in range(img.height())
        for x in range(img.width())
        if img.pixelColor(x, y).alpha() > 8
    ]
    return (max(xs) - min(xs) + 1) / img.width() if xs else 0.0


@pytest.mark.parametrize("dpr", DPRS)
def test_pixmap_tem_a_resolucao_do_monitor(qapp, dpr):
    pm = icons._pixmap("scissors", theme.ICON, 26, dpr)
    assert pm.width() == round(26 * dpr)
    assert pm.height() == round(26 * dpr)
    assert pm.devicePixelRatio() == pytest.approx(dpr)


@pytest.mark.parametrize("dpr", DPRS)
@pytest.mark.parametrize("nome", ["scissors", "download", "magnet", "eye"])
def test_desenho_nao_e_escalado_duas_vezes(qapp, dpr, nome):
    """O ícone ocupa a MESMA fração do quadro em qualquer dpr.

    Se o fator for aplicado duas vezes, o desenho vaza e a fração cai (foi
    0,50 contra 0,85 no ícone 'download' quando o defeito existia). Se não for
    aplicado nenhuma vez, o desenho encolhe para um canto."""
    referencia = _fracao_ocupada(icons._pixmap(nome, theme.ICON, 26, 1.0))
    obtida = _fracao_ocupada(icons._pixmap(nome, theme.ICON, 26, dpr))
    assert obtida == pytest.approx(referencia, abs=0.06)


def test_dpr_faz_parte_da_chave_do_cache(qapp):
    a = icons._pixmap("scissors", theme.ICON, 26, 1.0)
    b = icons._pixmap("scissors", theme.ICON, 26, 2.0)
    assert a is not b
    assert a is icons._pixmap("scissors", theme.ICON, 26, 1.0)  # ainda cacheia


def test_a_100_por_cento_nada_muda(qapp):
    """dpr=1 tem de devolver o pixmap de sempre: mesmo tamanho, dpr neutro."""
    pm = icons._pixmap("scissors", theme.ICON, 26, 1.0)
    assert (pm.width(), pm.height()) == (26, 26)
    assert pm.devicePixelRatio() == 1.0


def test_blank_respeita_lados_diferentes(qapp):
    """As faixas de passos e as cartelas não são quadradas."""
    pm = icons.blank(224, 84, 1.5)
    assert (pm.width(), pm.height()) == (336, 126)
    assert pm.devicePixelRatio() == pytest.approx(1.5)


@pytest.mark.parametrize("dpr", DPRS)
def test_miniaturas_da_faca_acompanham(qapp, dpr):
    pm = faca_icons._mode_pixmap(
        "contour", theme.CUT, theme.TEXT_MUTED, theme.ACCENT, 26, dpr)
    assert pm.width() == round(26 * dpr)
    assert pm.devicePixelRatio() == pytest.approx(dpr)


@pytest.mark.parametrize("dpr", DPRS)
def test_faixa_de_passos_acompanha(qapp, dpr):
    pm = faca_icons._steps_pixmap(
        0, theme.CUT, theme.TEXT_MUTED, theme.ACCENT, faca_icons._STEPS, dpr)
    assert pm.devicePixelRatio() == pytest.approx(dpr)
    assert pm.width() == round((3 * 96 + 2 * 26) * dpr)


def test_sem_aplicacao_grafica_o_fator_e_neutro():
    """device_ratio() nunca pode explodir num contexto sem interface: o valor
    neutro 1.0 é o que mantém os testes de domínio idênticos."""
    assert icons.device_ratio() >= 1.0
