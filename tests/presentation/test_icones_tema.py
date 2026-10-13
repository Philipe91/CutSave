"""Icones da barra de status e das alcas do splitter seguem o tema ao vivo.

Cenario (13/10/2026): trocar para o tema escuro deixava os icones da barra de
status e a seta das alcas na cor do tema claro (pixmap renderizado uma vez so).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.presentation import icons, theme  # noqa: E402
from app.presentation.themes import palettes  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget  # noqa: E402


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    original = theme.current_palette()
    yield app
    theme.set_palette(original, dark_ui=False)
    icons.clear_cache()
    theme.apply(app)


def _cor_do_traco(pm) -> QColor:
    """Cor do pixel mais opaco (traco fino antialiasado quase nunca e 255)."""
    img = pm.toImage()
    melhor = None
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if melhor is None or c.alpha() > melhor.alpha():
                melhor = c
    assert melhor is not None and melhor.alpha() >= 100, "pixmap vazio"
    return QColor(melhor.red(), melhor.green(), melhor.blue())


def _mesma_cor(c: QColor, hexcolor: str) -> bool:
    # o antialias arredonda 1 unidade no canal (ex.: #8a8a8f x #8a8a8e)
    alvo = QColor(hexcolor)
    return all(abs(a - b) <= 3 for a, b in (
        (c.red(), alvo.red()), (c.green(), alvo.green()), (c.blue(), alvo.blue())))


def _trocar_para_escuro(app):
    theme.set_palette(palettes.DARK, dark_ui=True)
    icons.clear_cache()
    theme.apply(app)
    app.processEvents()


def test_barra_de_status_recolore_os_icones(qapp):
    from app.presentation.panels.status_bar import StatusBarController

    win = QMainWindow()
    StatusBarController(win.statusBar())
    labels = [w for w in win.statusBar().findChildren(QLabel)
              if w.pixmap() is not None and not w.pixmap().isNull()]
    assert labels
    _trocar_para_escuro(qapp)
    for lab in labels:
        assert _mesma_cor(_cor_do_traco(lab.pixmap()), palettes.DARK["TEXT_MUTED"])
    win.deleteLater()


def test_refresh_icons_da_barra_de_status(qapp):
    from app.presentation.panels.status_bar import StatusBarController

    win = QMainWindow()
    ctl = StatusBarController(win.statusBar())
    theme.set_palette(palettes.DARK, dark_ui=True)
    icons.clear_cache()
    ctl.refresh_icons()
    labels = [w for w in win.statusBar().findChildren(QLabel)
              if w.pixmap() is not None and not w.pixmap().isNull()]
    for lab in labels:
        assert _mesma_cor(_cor_do_traco(lab.pixmap()), palettes.DARK["TEXT_MUTED"])
    win.deleteLater()


def test_alca_do_splitter_recolore_a_seta(qapp):
    from app.presentation.widgets.splitter_alcas import SplitterComAlcas

    pai = QWidget()
    sp = SplitterComAlcas(Qt.Horizontal)
    sp.setParent(pai)
    sp.addWidget(QWidget())
    sp.addWidget(QWidget())
    sp.registrar_alca(1, lambda: None, lambda: "chevron-left", lambda: "dica")
    alca = sp.alca(1)
    assert alca is not None
    _trocar_para_escuro(qapp)
    pm = alca.icon().pixmap(12, 12)
    assert _mesma_cor(_cor_do_traco(pm), palettes.DARK["ICON"])
    theme.set_palette(palettes.LIGHT, dark_ui=False)
    icons.clear_cache()
    sp.refresh_icons()
    assert _mesma_cor(_cor_do_traco(alca.icon().pixmap(12, 12)), palettes.LIGHT["ICON"])
    pai.deleteLater()
