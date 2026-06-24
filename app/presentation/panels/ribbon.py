"""Ribbon: barra de ferramentas agrupada de uma linha (estilo Affinity/LightBurn).

Reaproveita as QActions ja existentes da janela e as organiza em grupos
(Arquivo | Editar | Organizar | Producao | Exibir), com icone+texto e separadores
entre grupos. Botoes com menu (Exportar, Alinhar...) usam popup instantaneo.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QToolBar, QToolButton, QWidget

from app.presentation import icons, theme


def tool_button(
    action: QAction, icon_name: str, *, accent: bool = False, show_text: bool = True
) -> QToolButton:
    """Botao da ribbon ligado a uma QAction (herda enabled/tooltip/triggered)."""
    btn = QToolButton()
    btn.setDefaultAction(action)
    btn.setIcon(icons.icon(icon_name, theme.ICON_ON_ACCENT if accent else theme.ICON, 18))
    style = Qt.ToolButtonTextBesideIcon if show_text else Qt.ToolButtonIconOnly
    btn.setToolButtonStyle(style)
    btn.setCursor(Qt.PointingHandCursor)
    if accent:
        btn.setProperty("accent", "true")
    return btn


def menu_button(
    text: str, icon_name: str, actions: Sequence[QAction], *, tip: str = ""
) -> QToolButton:
    """Botao com menu suspenso (ex.: Exportar, Alinhar, Distribuir)."""
    btn = QToolButton()
    btn.setText(text)
    btn.setIcon(icons.icon(icon_name, theme.ICON, 18))
    btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    btn.setPopupMode(QToolButton.InstantPopup)
    btn.setCursor(Qt.PointingHandCursor)
    if tip:
        btn.setToolTip(tip)
    menu = QMenu(btn)
    for action in actions:
        menu.addAction(action)
    btn.setMenu(menu)
    return btn


def populate_ribbon(toolbar: QToolBar, groups: Sequence[tuple[str, Sequence[QWidget]]]) -> None:
    """Preenche a toolbar com os grupos (titulo, widgets), separados por linhas."""
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    for index, (_title, widgets) in enumerate(groups):
        if index:
            toolbar.addSeparator()
        for widget in widgets:
            toolbar.addWidget(widget)
