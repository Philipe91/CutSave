"""CollapsibleCard: cartao moderno e recolhivel.

Substitui o antigo ``_section`` (faixas coloridas berrantes) por um cartao
sobrio: borda suave unica, cabecalho discreto com seta, conteudo com padding
uniforme. Clicar no cabecalho abre/fecha.

    card = CollapsibleCard("Material")
    card.body.addWidget(meu_widget)
    layout.addWidget(card)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from app.presentation import icons, theme


class CollapsibleCard(QFrame):
    """Cartao com cabecalho clicavel que mostra/esconde o conteudo."""

    def __init__(self, title: str, *, collapsed: bool = False) -> None:
        super().__init__()
        self.setObjectName("card")
        self._title = title

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = QPushButton()
        self._header.setObjectName("cardHeader")
        self._header.setCheckable(True)
        self._header.setChecked(not collapsed)
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.toggled.connect(self._sync)
        outer.addWidget(self._header)

        self._content = QWidget()
        self.body = QVBoxLayout(self._content)
        self.body.setContentsMargins(theme.SPACE_MD, 0, theme.SPACE_MD, theme.SPACE_MD)
        self.body.setSpacing(theme.SPACE_SM)
        outer.addWidget(self._content)

        self._sync()

    def _sync(self) -> None:
        open_ = self._header.isChecked()
        self._header.setIcon(
            icons.icon("chevron-down" if open_ else "chevron-right", theme.TEXT_MUTED, 16)
        )
        self._header.setText(f"  {self._title}")
        self._content.setVisible(open_)

    def set_collapsed(self, collapsed: bool) -> None:
        self._header.setChecked(not collapsed)
