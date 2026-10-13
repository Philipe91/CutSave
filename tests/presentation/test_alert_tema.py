"""Avisos (Alert/Toast/medidor de DPI) seguem o tema ATUAL, nao o do import.

Cenario real (13/10/2026): o AlertLevel capturava as cores do tema claro no
import do modulo; no tema escuro o texto (TEXT vivo, quase branco) ia sobre o
fundo claro #fdeaea -> faixa de erro ilegivel.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.presentation import theme  # noqa: E402

# importados AQUI, com o tema claro ativo — exatamente como o __main__ faz
# (widgets importados antes do apply_startup); o bug so aparece assim
from app.presentation.panels import dpi_dialog  # noqa: E402
from app.presentation.themes import palettes  # noqa: E402
from app.presentation.widgets.alert import Alert, AlertLevel  # noqa: E402
from app.presentation.widgets.toast import _Toast  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402


@pytest.fixture
def escuro():
    app = QApplication.instance() or QApplication([])
    original = theme.current_palette()
    theme.set_palette(palettes.DARK, dark_ui=True)
    yield app
    theme.set_palette(original, dark_ui=False)


def test_alert_level_resolve_cor_do_tema_atual(escuro):
    for lvl in AlertLevel:
        nome = lvl.name
        assert lvl.color == getattr(theme, nome)
        assert lvl.soft == getattr(theme, nome + "_SOFT")
        assert lvl.soft == palettes.DARK[nome + "_SOFT"]


def test_faixa_de_erro_legivel_no_tema_escuro(escuro):
    a = Alert()
    a.show_message(AlertLevel.ERROR, "Falhou")
    css = a.styleSheet()
    assert palettes.DARK["ERROR_SOFT"] in css
    assert palettes.contrast(theme.TEXT, AlertLevel.ERROR.soft) >= 4.5
    a.deleteLater()


def test_faixa_visivel_acompanha_troca_de_tema(escuro):
    a = Alert()
    a.show_message(AlertLevel.WARNING, "Atencao")
    assert palettes.DARK["WARNING_SOFT"] in a.styleSheet()
    theme.set_palette(palettes.LIGHT, dark_ui=False)
    theme.apply(escuro)
    escuro.processEvents()
    assert palettes.LIGHT["WARNING_SOFT"] in a.styleSheet()
    a.deleteLater()


def test_toast_usa_cor_do_tema_atual(escuro):
    pai = QWidget()
    t = _Toast(pai, AlertLevel.SUCCESS, "ok")
    css = t.styleSheet()
    assert palettes.DARK["SUCCESS"] in css
    assert palettes.DARK["SURFACE"] in css
    pai.deleteLater()


def test_medidor_dpi_usa_cor_do_tema_atual(escuro):
    barra = dpi_dialog.NivelBarra()
    barra.set_nivel("normal")
    assert barra._cor == palettes.DARK["SUCCESS"]
    barra.set_nivel("impossivel")
    assert barra._cor == palettes.DARK["TEXT_MUTED"]
    barra.deleteLater()
