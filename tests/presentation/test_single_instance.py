"""IPC de instancia unica (CorelDRAW/CLI): o servidor recebe os caminhos."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.presentation.single_instance import start_server  # noqa: E402
from PySide6.QtNetwork import QLocalSocket  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# nome unico de teste: nao colide com um PrintNest real em execucao
_TEST_NAME = "PrintNestPro.test.ipc"


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_servidor_recebe_os_caminhos(qapp):
    recebidos = {}
    server = start_server(
        lambda files: recebidos.setdefault("files", files), name=_TEST_NAME
    )
    try:
        sock = QLocalSocket()
        sock.connectToServer(_TEST_NAME)
        assert sock.waitForConnected(800)
        for _ in range(5):
            qapp.processEvents()
        sock.write(b"/x/a.pdf\n/y/b.png")
        sock.flush()
        sock.waitForBytesWritten(800)
        for _ in range(5):
            qapp.processEvents()
        sock.disconnectFromServer()
        for _ in range(15):
            qapp.processEvents()
        assert recebidos.get("files") == ["/x/a.pdf", "/y/b.png"]
    finally:
        server.close()
