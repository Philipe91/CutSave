"""Instancia unica + IPC (Qt QLocalServer/QLocalSocket).

Permite que o PrintNest se comporte como o RDWorks: ao abrir um arquivo (ex.:
pelo botao da macro do CorelDRAW) com o programa JA aberto, o arquivo entra na
SESSAO ATUAL em vez de abrir outra janela.

Fluxo:
- No inicio do main(), antes de qualquer coisa pesada, o processo toma um
  mutex nomeado do Windows. Se o mutex ja existia, ha outra instancia (talvez
  ainda montando a janela): tenta entregar os caminhos a ela por alguns
  segundos e, se ela confirmar, encerra.
- A entrega so conta quando a instancia aberta CONFIRMA (byte ACK). Conectar
  no pipe nao basta: uma instancia travada aceita a conexao e nunca le nada.
- A primeira instancia sobe o servidor cedo (antes de montar a janela) e
  guarda os caminhos que chegarem ate a janela existir.

Por que tudo isso (13/10/2026): abrir 3 PDFs pelo Explorer dispara 3 processos
juntos. Antes o servidor so subia depois da janela montada e um segundo
listen() no mesmo nome funciona no Windows -> 2-3 janelas; e com a instancia
travada o cliente dava "entregue" so por conectar -> arquivos perdidos.

Protocolo: caminhos separados por "\\n", terminados por NUL (nao existe em
caminho do Windows); o servidor responde ACK e so depois chama o callback.
Cliente antigo (sem NUL, so desconecta) continua sendo atendido.
"""

from __future__ import annotations

import contextlib
import sys
import time
from collections.abc import Callable

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "PrintNestPro.singleton.v1"
MUTEX_NAME = "PrintNestPro.singleton.v1.mutex"
_TIMEOUT_MS = 800
# a instancia aberta pode estar ocupada alguns segundos (importando um PDF
# pesado na thread da interface) — esperar um pouco antes de declarar travada
_ACK_TIMEOUT_MS = 4000
_FIM = b"\x00"
_ACK = b"\x06"

_mutex_handles: list = []  # vivos enquanto o processo viver


def _kernel32():
    import ctypes
    from ctypes import wintypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.restype = wintypes.HANDLE
    k.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    return k, ctypes


def _criar_mutex(name: str):
    """(handle, primeira). Cria JA como DONO (bInitialOwner=True): assim, se
    este processo morrer, o mutex fica "abandonado" e quem estiver esperando
    percebe na hora. Posse de mutex no Windows e POR THREAD — chamar da thread
    principal, que vive o processo inteiro."""
    k, ctypes = _kernel32()
    handle = k.CreateMutexW(None, True, name)
    erro = ctypes.get_last_error()
    if not handle:
        return None, None
    return handle, erro != 183  # ERROR_ALREADY_EXISTS (posse NAO concedida)


def _assumir(handle) -> bool:
    """Tenta tomar a posse sem esperar: True se a outra instancia saiu
    (WAIT_OBJECT_0) ou morreu segurando (WAIT_ABANDONED). A posse fica com a
    thread que chamou — a principal — ate o processo acabar."""
    if not handle:
        return False
    try:
        k, _ = _kernel32()
        return k.WaitForSingleObject(handle, 0) in (0x0, 0x80)
    except Exception:  # noqa: BLE001
        return False


def adquirir_mutex_de_instancia(name: str = MUTEX_NAME) -> bool | None:
    """True = esta e a primeira instancia; False = ja ha outra aberta (ou
    abrindo); None = nao deu para saber (fora do Windows / falha da API).

    O SO solta o mutex sozinho quando o processo morre — crash nao deixa
    "instancia fantasma"."""
    if sys.platform != "win32":
        return None
    try:
        handle, primeira = _criar_mutex(name)
    except Exception:  # noqa: BLE001 — nunca impedir a abertura
        return None
    if handle:
        _mutex_handles.append(handle)
    return primeira


def assumiu_instancia() -> bool:
    """A instancia que segurava o mutex deste processo saiu? (e agora somos
    nos). False sem mutex (fora do Windows / teste)."""
    return bool(_mutex_handles) and _assumir(_mutex_handles[-1])


def forward_to_running(paths: list[str], name: str = SERVER_NAME,
                       ack_timeout_ms: int = _ACK_TIMEOUT_MS) -> bool:
    """Se houver uma instancia aberta, entrega os caminhos a ela e retorna True
    — so depois que ela CONFIRMA o recebimento. Lista vazia tambem e valida
    (so traz a janela existente para a frente)."""
    sock = QLocalSocket()
    try:
        sock.connectToServer(name)
        if not sock.waitForConnected(_TIMEOUT_MS):
            return False
        sock.write("\n".join(paths).encode("utf-8") + _FIM)
        sock.flush()
        sock.waitForBytesWritten(_TIMEOUT_MS)
        # espera o ACK girando um event loop (e nao waitForReadyRead): assim um
        # servidor no MESMO processo/thread (testes) tambem consegue responder
        resposta = bytearray(bytes(sock.readAll()))
        if _ACK not in resposta:
            loop = QEventLoop()
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)

            def _ler() -> None:
                resposta.extend(bytes(sock.readAll()))
                if _ACK in resposta:
                    loop.quit()

            sock.readyRead.connect(_ler)
            sock.disconnected.connect(loop.quit)
            timer.start(ack_timeout_ms)
            loop.exec()
            timer.stop()
            resposta.extend(bytes(sock.readAll()))
        return _ACK in resposta
    finally:
        with contextlib.suppress(RuntimeError):
            sock.abort()


def entregar_a_instancia_aberta(
    paths: list[str],
    primeira: bool | None,
    *,
    name: str = SERVER_NAME,
    forward: Callable[..., bool] = forward_to_running,
    assumir: Callable[[], bool] = assumiu_instancia,
    ao_esperar: Callable[[], None] | None = None,
    prazo_s: float = 20.0,
    intervalo_s: float = 0.25,
) -> bool:
    """Decide se este processo entrega os caminhos e encerra (True) ou abre
    normalmente (False).

    `primeira` vem do mutex: se OUTRA instancia ja o tomou, ela pode estar
    ainda montando a janela (servidor sem responder) — insiste ate `prazo_s`.
    Passado o prazo, abre normal: janela duplicada e melhor que arquivo
    perdido.

    A cada tentativa falha confere o mutex: se a outra instancia FECHOU no
    meio da espera (relancar logo depois de fechar), assume na hora em vez de
    insistir o prazo inteiro sem janela (revisao 13/10/2026). O ACK de cada
    tentativa e cortado pelo que resta do prazo — contra instancia travada o
    total fica limitado a ~prazo_s. `ao_esperar` e chamado uma vez, antes da
    primeira espera (mostrar a splash)."""
    if primeira is not False:
        # primeira (ou sem mutex): uma tentativa so — cobre instancia de versao
        # antiga, que nao toma o mutex
        return forward(paths, name=name)
    limite = time.monotonic() + prazo_s
    avisou = False
    while True:
        resta_ms = int((limite - time.monotonic()) * 1000)
        if forward(paths, name=name,
                   ack_timeout_ms=max(100, min(_ACK_TIMEOUT_MS, resta_ms))):
            return True
        if assumir():
            return False  # a outra saiu: somos a primeira agora
        if time.monotonic() >= limite:
            return False
        if not avisou and ao_esperar is not None:
            avisou = True
            with contextlib.suppress(Exception):  # splash nunca trava a abertura
                ao_esperar()
        time.sleep(intervalo_s)


class CaixaDeEntrada:
    """Guarda os caminhos que chegam pelo IPC antes de a janela existir.

    O servidor sobe cedo (antes de montar a janela) para a segunda abertura
    nao virar outra janela; o que chegar nesse meio tempo e entregue quando a
    janela ligar o destino."""

    def __init__(self) -> None:
        self._destino: Callable[[list[str]], None] | None = None
        self._pendentes: list[str] = []

    def receber(self, files: list[str]) -> None:
        if self._destino is None:
            self._pendentes.extend(files)
        else:
            self._destino(files)

    def ligar(self, destino: Callable[[list[str]], None]) -> None:
        self._destino = destino
        if self._pendentes:
            pendentes, self._pendentes = self._pendentes, []
            destino(pendentes)


def start_server(on_paths: Callable[[list[str]], None], name: str = SERVER_NAME) -> QLocalServer:
    """Cria o servidor local desta (primeira) instancia. Ao receber uma conexao,
    decodifica os caminhos, confirma (ACK) e chama on_paths(list[str]) (vazia =
    so trazer a frente). Mantenha uma referencia ao retorno (senao o GC o
    fecha)."""
    QLocalServer.removeServer(name)  # limpa socket orfao de um crash anterior
    server = QLocalServer()
    server.listen(name)

    def _handle() -> None:
        conn = server.nextPendingConnection()
        if conn is None:
            return
        buf = bytearray()
        estado = {"entregue": False}

        def _entregar() -> None:
            if estado["entregue"]:
                return
            estado["entregue"] = True
            dados = bytes(buf).split(_FIM, 1)[0]
            files = [f for f in dados.decode("utf-8", "ignore").splitlines() if f.strip()]
            on_paths(files)

        def _read() -> None:
            buf.extend(bytes(conn.readAll()))
            if _FIM in buf and not estado["entregue"]:
                # ACK ANTES do callback: abrir os arquivos pode demorar e o
                # cliente nao pode concluir que a instancia travou
                conn.write(_ACK)
                conn.flush()
                _entregar()

        def _finish() -> None:
            with contextlib.suppress(RuntimeError):
                _read()
            _entregar()  # cliente antigo: mensagem termina no disconnect
            conn.deleteLater()

        conn.readyRead.connect(_read)
        conn.disconnected.connect(_finish)
        # caso a mensagem ja tenha chegado inteira antes de conectarmos os sinais
        if conn.bytesAvailable():
            _read()

    server.newConnection.connect(_handle)
    return server
