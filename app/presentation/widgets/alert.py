"""Alert: faixa de aviso contextual padronizada (info / sucesso / aviso / erro).

Usada para o software NUNCA falhar em silencio: explica o que houve e, quando
util, oferece uma acao. Some quando nao ha aviso.

    alert = Alert()
    alert.show_message(AlertLevel.WARNING, "Faca compartilhada quadra o contorno.",
                       action_text="Trocar", on_action=trocar_modo)
    alert.clear()
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from app.presentation import icons, theme


class AlertLevel(Enum):
    INFO = ("info", theme.INFO, theme.INFO_SOFT)
    SUCCESS = ("circle-check", theme.SUCCESS, theme.SUCCESS_SOFT)
    WARNING = ("triangle-alert", theme.WARNING, theme.WARNING_SOFT)
    ERROR = ("circle-x", theme.ERROR, theme.ERROR_SOFT)


class Alert(QFrame):
    """Faixa de aviso com icone, texto e botao de acao opcional."""

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
        icon_name, color, soft = level.value
        self.setStyleSheet(
            f"QFrame{{background:{soft}; border:1px solid {color};"
            f"border-left:4px solid {color}; border-radius:{theme.RADIUS_SM}px;}}"
            f"QLabel{{color:{theme.TEXT}; background:transparent; border:none;}}"
        )
        self._icon.setPixmap(icons.pixmap(icon_name, color, 18))
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

    def clear(self) -> None:
        """Esconde o alerta (sem aviso ativo)."""
        self.hide()
