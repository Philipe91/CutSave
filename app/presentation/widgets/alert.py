"""Alert: faixa de aviso contextual padronizada (info / sucesso / aviso / erro).

Usada para o software NUNCA falhar em silencio: explica o que houve e, quando
útil, oferece uma ação. Some quando não ha aviso.

    alert = Alert()
    alert.show_message(AlertLevel.WARNING, "Faca compartilhada quadra o contorno.",
                       action_text="Trocar", on_action=trocar_modo)
    alert.clear()
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from app.presentation import icons, theme


class AlertLevel(Enum):
    # Guarda o NOME do token, nao a cor: o enum nasce no import (tema claro,
    # antes do apply_startup) e congelava #fdeaea etc. No tema escuro o texto
    # (TEXT vivo, quase branco) ia sobre fundo claro -> aviso ilegivel
    # (13/10/2026). A cor e resolvida na hora de pintar (color/soft).
    INFO = ("info", "INFO", "INFO_SOFT")
    SUCCESS = ("circle-check", "SUCCESS", "SUCCESS_SOFT")
    WARNING = ("triangle-alert", "WARNING", "WARNING_SOFT")
    ERROR = ("circle-x", "ERROR", "ERROR_SOFT")

    @property
    def icon_name(self) -> str:
        return self.value[0]

    @property
    def color(self) -> str:
        """Cor forte do nivel no tema ATUAL."""
        return getattr(theme, self.value[1])

    @property
    def soft(self) -> str:
        """Fundo suave do nivel no tema ATUAL."""
        return getattr(theme, self.value[2])


class Alert(QFrame):
    """Faixa de aviso com icone, texto e botão de ação opcional."""

    def __init__(self) -> None:
        super().__init__()
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM, theme.SPACE_MD, theme.SPACE_SM)
        self._lay.setSpacing(theme.SPACE_SM)

        self._icon = QLabel()
        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._action = QPushButton()
        self._action.setCursor(Qt.PointingHandCursor)
        self._action.hide()
        self._action_conn = None
        self._level: AlertLevel | None = None

        self._lay.addWidget(self._icon, 0, Qt.AlignTop)
        self._lay.addWidget(self._text, 1)
        self._lay.addWidget(self._action, 0, Qt.AlignVCenter)
        self.hide()

    def show_message(
        self,
        level: AlertLevel,
        message: str,
        *,
        action_text: str | None = None,
        on_action=None,
    ) -> None:
        self._level = level
        self._apply_colors()
        self._text.setText(message)
        if self._action_conn is not None:
            self._action.clicked.disconnect(self._action_conn)
            self._action_conn = None
        if action_text and on_action is not None:
            self._action.setText(action_text)
            self._action_conn = self._action.clicked.connect(lambda: on_action())
            self._action.show()
        else:
            self._action.hide()
        self.show()

    def _apply_colors(self) -> None:
        level = self._level
        if level is None:
            return
        color, soft = level.color, level.soft
        css = (
            f"QFrame{{background:{soft}; border:1px solid {color};"
            f"border-left:4px solid {color}; border-radius:{theme.RADIUS_SM}px;}}"
            f"QLabel{{color:{theme.TEXT}; background:transparent; border:none;}}"
        )
        # so reaplica se mudou: setStyleSheet gera novo PaletteChange e, sem
        # este guarda, o changeEvent abaixo entraria em laco
        if css != self.styleSheet():
            self.setStyleSheet(css)
            self._icon.setPixmap(icons.pixmap(level.icon_name, color, 18))

    def changeEvent(self, event) -> None:
        # faixa ja visivel quando o usuario troca o tema (Personalizar
        # Interface): theme.apply troca a paleta do app -> recolore aqui
        if event.type() in (QEvent.ApplicationPaletteChange,
                            QEvent.PaletteChange):
            self._apply_colors()
        super().changeEvent(event)

    def clear(self) -> None:
        """Esconde o alerta (sem aviso ativo)."""
        self.hide()
