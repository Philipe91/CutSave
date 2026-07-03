"""Dialogo de ativacao de licenca (PrintNest).

Mostra o ID da Maquina (o cliente envia ao vendedor), aceita a chave e ativa.
Usado no startup (quando o app nao esta licenciado) e pelo menu Ajuda -> Licenca.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.licensing.manager import LicenseManager
from app.presentation import theme


class ActivationDialog(QDialog):
    """Ativacao node-locked: ID da maquina + colar chave + Ativar."""

    def __init__(self, manager: LicenseManager, parent=None, *, blocking: bool = False) -> None:
        super().__init__(parent)
        self._m = manager
        self._blocking = blocking  # True no startup (sem licenca -> nao usa)
        self.setWindowTitle("Ativacao do PrintNest")
        self.setMinimumWidth(520)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_XL, theme.SPACE_LG, theme.SPACE_XL, theme.SPACE_LG)
        lay.setSpacing(theme.SPACE_MD)

        self._status = QLabel()
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        # ID da maquina + copiar
        lay.addWidget(self._caption("1. Envie este ID da Maquina para comprar/ativar:"))
        id_row = QHBoxLayout()
        self._id_field = QLineEdit(self._m.machine_id)
        self._id_field.setReadOnly(True)
        f = self._id_field.font()
        f.setPointSize(f.pointSize() + 2)
        self._id_field.setFont(f)
        id_row.addWidget(self._id_field, 1)
        copy = QPushButton("Copiar")
        copy.clicked.connect(self._copy_id)
        id_row.addWidget(copy)
        lay.addLayout(id_row)

        # colar a chave
        lay.addWidget(self._caption("2. Cole aqui a chave de licenca que voce recebeu:"))
        self._key_field = QPlainTextEdit()
        self._key_field.setPlaceholderText("PNEST1. ...")
        self._key_field.setFixedHeight(84)
        lay.addWidget(self._key_field)

        activate = QPushButton("  Ativar")
        activate.setProperty("accent", "true")
        activate.clicked.connect(self._activate)
        lay.addWidget(activate)

        # botoes: fechar/sair + (se licenciado) desativar
        self._buttons = QDialogButtonBox()
        self._deact = QPushButton("Desativar (transferir de PC)")
        self._deact.clicked.connect(self._deactivate)
        self._buttons.addButton(self._deact, QDialogButtonBox.ActionRole)
        close_text = "Sair" if blocking else "Fechar"
        self._close_btn = self._buttons.addButton(close_text, QDialogButtonBox.RejectRole)
        self._buttons.rejected.connect(self._on_close)
        lay.addWidget(self._buttons)

        self._refresh()

    def _caption(self, text: str) -> QLabel:
        lb = QLabel(text)
        lb.setProperty("role", "caption")
        return lb

    def _copy_id(self) -> None:
        QApplication.clipboard().setText(self._m.machine_id)

    def _activate(self) -> None:
        key = self._key_field.toPlainText().strip()
        if not key:
            QMessageBox.information(self, "PrintNest", "Cole a chave de licenca primeiro.")
            return
        ok, msg = self._m.activate(key)
        if ok:
            QMessageBox.information(self, "PrintNest", msg)
            self.accept()  # libera o app (startup) ou fecha
        else:
            QMessageBox.warning(self, "Ativacao", msg)
        self._refresh()

    def _deactivate(self) -> None:
        if not self._m.is_licensed():
            return
        r = QMessageBox.question(
            self, "Desativar",
            "Isto libera a licenca deste PC para ativar em outro. Continuar?",
        )
        if r == QMessageBox.Yes:
            self._m.deactivate()
            self._refresh()

    def _on_close(self) -> None:
        # no startup, fechar sem licenca = sair do programa
        if self._blocking and not self._m.is_licensed():
            self.reject()
        else:
            self.accept()

    def _refresh(self) -> None:
        self._status.setText(self._m.status_text())
        self._deact.setVisible(self._m.is_licensed())
        if self._blocking:
            self._close_btn.setText("Fechar" if self._m.is_licensed() else "Sair")
