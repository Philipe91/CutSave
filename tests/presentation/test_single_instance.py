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
        # teardown explicito (QA-11): socket/servidor destruidos AGORA, com o
        # QApplication vivo — deixa-los para o GC do fim do processo derrubava
        # o teardown do Qt (segfault 139) quando rodava junto com a suite da
        # MainWindow.
        sock.abort()
        sock.deleteLater()
        server.close()
        server.deleteLater()
        for _ in range(5):
            qapp.processEvents()


# ---- confirmacao (ACK) e corrida na abertura (13/10/2026) ----
# Cenario real: abrir 3 PDFs pelo Explorer dispara 3 processos juntos. Antes:
# (a) o cliente dava "entregue" assim que o pipe conectava, mesmo com a
#     instancia aberta TRAVADA -> os arquivos sumiam;
# (b) o servidor so subia depois da janela montada, e um segundo listen() no
#     mesmo nome funciona no Windows -> 2-3 janelas do PrintNest.
import sys  # noqa: E402
import time  # noqa: E402

from app.presentation import single_instance as si  # noqa: E402
from PySide6.QtNetwork import QLocalServer  # noqa: E402


def _fechar(qapp, *objs):
    for o in objs:
        if isinstance(o, QLocalServer):
            o.close()
        o.deleteLater()
    for _ in range(5):
        qapp.processEvents()


def test_instancia_travada_nao_confirma_e_o_cliente_abre_normal(qapp):
    # servidor que aceita a conexao mas NUNCA responde (event loop travado)
    nome = _TEST_NAME + ".travada"
    QLocalServer.removeServer(nome)
    mudo = QLocalServer()
    assert mudo.listen(nome)
    try:
        t0 = time.monotonic()
        entregue = si.forward_to_running(["C:/a.pdf"], name=nome,
                                         ack_timeout_ms=600)
        assert entregue is False  # antes: True -> arquivo perdido
        assert time.monotonic() - t0 < 3.0
    finally:
        _fechar(qapp, mudo)


def test_entrega_confirmada_no_mesmo_processo(qapp):
    recebidos = {}
    nome = _TEST_NAME + ".ack"
    server = si.start_server(lambda f: recebidos.setdefault("files", f),
                             name=nome)
    try:
        assert si.forward_to_running(["C:/a.pdf", "C:/b.pdf"], name=nome)
        for _ in range(10):
            qapp.processEvents()
        assert recebidos.get("files") == ["C:/a.pdf", "C:/b.pdf"]
    finally:
        _fechar(qapp, server)


def test_servidor_responde_ack_ao_terminador(qapp):
    nome = _TEST_NAME + ".bruto"
    recebidos = {}
    server = si.start_server(lambda f: recebidos.setdefault("files", f),
                             name=nome)
    sock = QLocalSocket()
    try:
        sock.connectToServer(nome)
        assert sock.waitForConnected(800)
        sock.write(b"C:/x.pdf" + si._FIM)
        sock.flush()
        resposta = b""
        fim = time.monotonic() + 2
        while time.monotonic() < fim and not resposta:
            qapp.processEvents()
            sock.waitForReadyRead(20)
            resposta += bytes(sock.readAll())
        assert resposta == si._ACK
        assert recebidos.get("files") == ["C:/x.pdf"]
    finally:
        sock.abort()
        _fechar(qapp, sock, server)


def test_segunda_abertura_espera_a_primeira_subir(qapp):
    # mutex ja existe (outra instancia montando a janela): tenta de novo ate
    # a primeira responder, em vez de abrir uma segunda janela
    tentativas = []

    def _forward(paths, name, **_k):
        tentativas.append(paths)
        return len(tentativas) >= 3

    assert si.entregar_a_instancia_aberta(
        ["C:/a.pdf"], primeira=False, forward=_forward,
        prazo_s=5, intervalo_s=0.01)
    assert len(tentativas) == 3


def test_segunda_abertura_desiste_no_prazo_e_abre_normal(qapp):
    t0 = time.monotonic()
    assert not si.entregar_a_instancia_aberta(
        ["C:/a.pdf"], primeira=False, forward=lambda p, name, **_k: False,
        prazo_s=0.3, intervalo_s=0.05)
    assert time.monotonic() - t0 < 2.0


def test_primeira_abertura_tenta_uma_vez_so(qapp):
    tentativas = []
    assert not si.entregar_a_instancia_aberta(
        [], primeira=True,
        forward=lambda p, name, **_k: tentativas.append(1) or False,
        prazo_s=5, intervalo_s=0.01)
    assert tentativas == [1]


@pytest.mark.skipif(sys.platform != "win32", reason="mutex nomeado do Windows")
def test_mutex_de_instancia_detecta_a_segunda():
    nome = f"PrintNestPro.test.mutex.{time.time_ns()}"
    assert si.adquirir_mutex_de_instancia(nome) is True
    assert si.adquirir_mutex_de_instancia(nome) is False


def test_caixa_de_entrada_guarda_ate_a_janela_existir():
    # servidor sobe ANTES da janela: o que chegar no meio da montagem espera
    caixa = si.CaixaDeEntrada()
    caixa.receber(["C:/a.pdf"])
    caixa.receber([])  # "so trazer a frente" sem janela: nada a fazer
    caixa.receber(["C:/b.pdf"])
    abertos = []
    caixa.ligar(abertos.append)
    assert abertos == [["C:/a.pdf", "C:/b.pdf"]]
    caixa.receber(["C:/c.pdf"])  # depois de ligada: direto para a janela
    assert abertos[-1] == ["C:/c.pdf"]


# ---- a outra instancia fecha no meio da espera (revisao 13/10/2026) ----
# Relancar logo depois de fechar (fechamento lento): o `primeira` decidido na
# partida ficava velho e B insistia os 20 s inteiros sem janela nem splash.
import threading  # noqa: E402


def _instancia_a_em_thread(nome, vive_s):
    """Simula a instancia A: toma o mutex numa thread que morre depois de
    `vive_s` (mutex abandonado = A saiu). Devolve quando A ja tem o mutex."""
    pronto = threading.Event()

    def _a():
        assert si._criar_mutex(nome)[1] is True
        pronto.set()
        time.sleep(vive_s)

    t = threading.Thread(target=_a, daemon=True)
    t.start()
    assert pronto.wait(5)
    return t


@pytest.mark.skipif(sys.platform != "win32", reason="mutex nomeado do Windows")
def test_a_sai_no_meio_da_espera_e_b_assume_na_hora():
    nome = f"PrintNestPro.test.mutex.sai.{time.time_ns()}"
    _instancia_a_em_thread(nome, vive_s=0.4)
    handle, primeira = si._criar_mutex(nome)
    assert primeira is False
    t0 = time.monotonic()
    entregou = si.entregar_a_instancia_aberta(
        ["C:/a.pdf"], primeira=False, forward=lambda p, name, **_k: False,
        assumir=lambda: si._assumir(handle), prazo_s=20, intervalo_s=0.05)
    assert entregou is False  # abre normal, agora como a primeira
    assert time.monotonic() - t0 < 2.0  # antes: os 20 s inteiros


def test_a_travada_b_desiste_em_tempo_limitado():
    # cada tentativa contra A travada esperava 4 s de ACK alem do prazo; agora
    # o ACK de cada tentativa e cortado pelo que resta do prazo
    esperas = []

    def _travada(paths, name, ack_timeout_ms=4000):
        esperas.append(ack_timeout_ms)
        time.sleep(ack_timeout_ms / 1000)
        return False

    t0 = time.monotonic()
    assert not si.entregar_a_instancia_aberta(
        ["C:/a.pdf"], primeira=False, forward=_travada,
        assumir=lambda: False, prazo_s=1.0, intervalo_s=0.05)
    assert time.monotonic() - t0 < 2.0
    assert all(e <= 1000 for e in esperas)


def test_avisa_que_vai_esperar_uma_vez_so():
    # a splash aparece ANTES de esperar (B nao fica mudo por segundos)
    avisos = []
    tentativas = []

    def _fwd(paths, name, **_k):
        tentativas.append(1)
        return len(tentativas) >= 3

    assert si.entregar_a_instancia_aberta(
        [], primeira=False, forward=_fwd, assumir=lambda: False,
        prazo_s=5, intervalo_s=0.01, ao_esperar=lambda: avisos.append(1))
    assert avisos == [1]
