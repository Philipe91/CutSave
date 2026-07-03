"""Gerador visual de licencas (uso do VENDEDOR) — emissao em 10 segundos.

Cole o ID da Maquina do cliente, o nome/e-mail e (opcional) a validade; clique
em Gerar. A chave aparece pronta para copiar e enviar. Usa a chave privada
local (tools/license_private_key.pem). Rode com:

    .venv\\Scripts\\python.exe tools/license_studio.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from tools.issuer import issue_license, load_private_key  # noqa: E402


class LicenseStudio(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PrintNest — Emissor de Licencas")
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title = QLabel("Emissor de Licencas (uso interno)")
        title.setStyleSheet("font-size:16px; font-weight:600;")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)
        self._mid = QLineEdit()
        self._mid.setPlaceholderText("PN-XXXX-XXXX-XXXX-XXXX")
        self._customer = QLineEdit()
        self._customer.setPlaceholderText("Nome da grafica <email>")
        self._expires = QLineEdit()
        self._expires.setPlaceholderText("vazio = perpetua · ou AAAA-MM-DD")
        form.addRow("ID da Maquina:", self._mid)
        form.addRow("Cliente:", self._customer)
        form.addRow("Validade:", self._expires)
        root.addLayout(form)

        gen = QPushButton("Gerar licenca")
        gen.clicked.connect(self._generate)
        root.addWidget(gen)

        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("A chave gerada aparece aqui...")
        self._out.setFixedHeight(96)
        root.addWidget(self._out)

        row = QHBoxLayout()
        self._copy = QPushButton("Copiar chave")
        self._copy.setEnabled(False)
        self._copy.clicked.connect(self._copy_key)
        row.addStretch()
        row.addWidget(self._copy)
        root.addLayout(row)

        # falha cedo se a chave privada nao existir
        try:
            load_private_key()
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self, "Chave privada", str(exc))

    def _generate(self) -> None:
        try:
            key = issue_license(
                self._mid.text(),
                self._customer.text(),
                expires=self._expires.text().strip(),
            )
        except (ValueError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Erro", str(exc))
            return
        self._out.setPlainText(key)
        self._copy.setEnabled(True)

    def _copy_key(self) -> None:
        QApplication.clipboard().setText(self._out.toPlainText())
        QMessageBox.information(self, "Copiado", "Chave copiada. Envie ao cliente.")


def main() -> None:
    app = QApplication(sys.argv)
    w = LicenseStudio()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
