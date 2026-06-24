"""Barra de status inferior (estilo CorelDRAW/Affinity).

Mostra, da esquerda para a direita: quantidade de pecas e de chapas, area
utilizada (%), e — alinhados a direita — posicao do cursor (mm), zoom e modo
de visualizacao. Atualizado pela janela conforme a producao e o mouse mudam.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar

from app.presentation import icons, theme


class StatusBarController:
    """Cria e atualiza os campos da QStatusBar."""

    def __init__(self, status_bar: QStatusBar) -> None:
        self._bar = status_bar
        self._pieces = self._add_left("layers", "0 pecas")
        self._sheets = self._add_left("file-text", "0 chapas")
        self._area = self._add_left("grid-3x3", "0%")
        # permanentes (direita)
        self._mode = self._add_right("eye", "—")
        self._zoom = self._add_right("maximize", "100%")
        self._cursor = self._add_right("ruler", "0, 0 mm")

    def _add_left(self, icon_name: str, text: str) -> QLabel:
        ico = QLabel()
        ico.setPixmap(icons.pixmap(icon_name, theme.TEXT_MUTED, 14))
        label = QLabel(text)
        label.setProperty("role", "caption")
        label.setContentsMargins(2, 0, theme.SPACE_MD, 0)
        self._bar.addWidget(ico)
        self._bar.addWidget(label)
        return label

    def _add_right(self, icon_name: str, text: str) -> QLabel:
        ico = QLabel()
        ico.setPixmap(icons.pixmap(icon_name, theme.TEXT_MUTED, 14))
        label = QLabel(text)
        label.setProperty("role", "caption")
        label.setContentsMargins(2, 0, theme.SPACE_MD, 0)
        self._bar.addPermanentWidget(ico)
        self._bar.addPermanentWidget(label)
        return label

    # ---- atualizacoes ----
    def set_production(self, pieces: int, sheets: int) -> None:
        self._pieces.setText(f"{pieces} peca(s)")
        self._sheets.setText(f"{sheets} chapa(s)")

    def set_area(self, pct: float) -> None:
        self._area.setText(f"{pct:.0f}% usado")

    def set_zoom(self, factor: float) -> None:
        self._zoom.setText(f"{factor * 100:.0f}%")

    def set_cursor(self, x: float, y: float) -> None:
        self._cursor.setText(f"{x:.0f}, {y:.0f} mm")

    def set_mode(self, text: str) -> None:
        self._mode.setText(text)
