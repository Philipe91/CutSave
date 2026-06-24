"""Toasts: notificacoes discretas no canto inferior direito.

Para confirmar acoes sem interromper o fluxo (substituem varios QMessageBox de
"sucesso"): "Producao gerada", "PDF exportado", "DXF criado", "Projeto salvo".
Auto-somem em alguns segundos e se empilham.

    self._toasts = ToastManager(self)   # parent = janela principal
    self._toasts.success("PDF exportado")
"""

from __future__ import annotations

from contextlib import suppress

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from app.presentation import icons, theme
from app.presentation.widgets.alert import AlertLevel

_MARGIN = 18
_GAP = 10
_DURATION_MS = 3200


class _Toast(QFrame):
    def __init__(self, parent: QWidget, level: AlertLevel, message: str) -> None:
        super().__init__(parent)
        icon_name, color, _soft = level.value
        self.setStyleSheet(
            f"QFrame{{background:{theme.SURFACE}; border:1px solid {theme.BORDER};"
            f"border-left:4px solid {color}; border-radius:{theme.RADIUS}px;}}"
            f"QLabel{{background:transparent; border:none; color:{theme.TEXT};}}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM, theme.SPACE_LG, theme.SPACE_SM)
        lay.setSpacing(theme.SPACE_SM)
        ico = QLabel()
        ico.setPixmap(icons.pixmap(icon_name, color, 18))
        lay.addWidget(ico)
        lay.addWidget(QLabel(message))
        self.adjustSize()


class ToastManager:
    """Gerencia a pilha de toasts sobre a janela (canto inferior direito)."""

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._toasts: list[_Toast] = []

    def notify(self, level: AlertLevel, message: str) -> None:
        toast = _Toast(self._parent, level, message)
        self._toasts.append(toast)
        toast.show()
        self._reposition()
        QTimer.singleShot(_DURATION_MS, lambda: self._dismiss(toast))

    # atalhos
    def info(self, message: str) -> None:
        self.notify(AlertLevel.INFO, message)

    def success(self, message: str) -> None:
        self.notify(AlertLevel.SUCCESS, message)

    def warning(self, message: str) -> None:
        self.notify(AlertLevel.WARNING, message)

    def error(self, message: str) -> None:
        self.notify(AlertLevel.ERROR, message)

    def _dismiss(self, toast: _Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
            with suppress(RuntimeError):
                toast.deleteLater()
            self._reposition()

    def _reposition(self) -> None:
        # robusto a janela/toasts ja destruidos (ex.: timer dispara apos fechar)
        try:
            rect = self._parent.rect()
            y = rect.height() - _MARGIN
            for toast in reversed(self._toasts):
                size = toast.sizeHint()
                x = rect.width() - size.width() - _MARGIN
                y -= size.height()
                toast.setGeometry(x, y, size.width(), size.height())
                toast.raise_()
                y -= _GAP
        except RuntimeError:
            self._toasts.clear()
