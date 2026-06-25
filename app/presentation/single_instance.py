"""Instancia unica + IPC (Qt QLocalServer/QLocalSocket).

Permite que o PrintNest se comporte como o RDWorks: ao abrir um arquivo (ex.:
pelo botao da macro do CorelDRAW) com o programa JA aberto, o arquivo entra na
SESSAO ATUAL em vez de abrir outra janela.

Fluxo:
- Ao iniciar, tenta conectar ao servidor local. Se conseguir, ja ha uma
  instancia rodando: envia os caminhos (ou nada, so para trazer a janela a
  frente) e encerra.
- Se nao conseguir, esta e a primeira instancia: cria o servidor e escuta. Ao
  receber caminhos, repassa para um callback (a janela os abre).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "PrintNestPro.singleton.v1"
_TIMEOUT_MS = 800


def forward_to_running(paths: list[str]) -> bool:
    """Se houver uma instancia aberta, entrega os caminhos a ela e retorna True.
    Lista vazia tambem e valida (so traz a janela existente para a frente)."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(_TIMEOUT_MS):
        sock.abort()
        return False
    sock.write("\n".join(paths).encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(_TIMEOUT_MS)
    sock.disconnectFromServer()
    if sock.state() != QLocalSocket.UnconnectedState:
        sock.waitForDisconnected(_TIMEOUT_MS)
    return True


def start_server(on_paths: Callable[[list[str]], None]) -> QLocalServer:
    """Cria o servidor local desta (primeira) instancia. Ao receber uma conexao,
    decodifica os caminhos e chama on_paths(list[str]) (vazia = so trazer a
    frente). Mantenha uma referencia ao retorno (senao o GC o fecha)."""
    QLocalServer.removeServer(SERVER_NAME)  # limpa socket orfao de um crash anterior
    server = QLocalServer()
    server.listen(SERVER_NAME)

    def _handle() -> None:
        conn = server.nextPendingConnection()
        if conn is None:
            return
        buf = bytearray()

        def _read() -> None:
            buf.extend(bytes(conn.readAll()))

        def _finish() -> None:
            _read()
            files = [f for f in buf.decode("utf-8", "ignore").splitlines() if f.strip()]
            on_paths(files)
            conn.deleteLater()

        conn.readyRead.connect(_read)
        conn.disconnected.connect(_finish)
        # caso a mensagem ja tenha chegado inteira antes de conectarmos os sinais
        if conn.bytesAvailable():
            _read()

    server.newConnection.connect(_handle)
    return server
