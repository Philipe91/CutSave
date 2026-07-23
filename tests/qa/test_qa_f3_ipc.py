"""QA FASE 3 — caso 16: segunda instancia do PrintNest com arquivo.

Espelha tests/presentation/test_single_instance.py (que testa o SERVIDOR, lado
da 1a instancia). Aqui testamos o CLIENTE: forward_to_running(), chamado por
uma 2a instancia ao iniciar quando ja existe uma rodando.

NOTA METODOLOGICA: forward_to_running() cria um QLocalSocket LOCAL a funcao
(sem pai/sem referencia externa). Chamando-o dentro do MESMO processo/thread
que hospeda o servidor de teste, o objeto e destruido (GC do Python) assim que
a funcao retorna — e a entrega ao servidor no MESMO processo as vezes chega
vazia (artefato de teste, confirmado por sondagem manual: reproduz so quando
cliente e servidor share a mesma QApplication/thread). Em USO REAL (2 PROCESSOS
separados, como e sempre o caso: 2a instancia do .exe) a entrega funciona
corretamente (confirmado via subprocesso real abaixo) — por isso os testes
que precisam validar o CONTEUDO entregue usam subprocess.Popen (fiel ao uso
real), e o teste em processo unico so valida os casos que nao dependem de
receber dados (timeout sem servidor)."""

import os
import subprocess
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.presentation.single_instance import forward_to_running, start_server  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_TEST_NAME = "PrintNestPro.test.qaf3.ipc"
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_segunda_instancia_com_arquivo_e_entregue_a_primeira_processo_real(tmp_path):
    """Fiel ao uso real: a 1a instancia (servidor) e a 2a (cliente que chama
    forward_to_running e encerra logo em seguida, como app/presentation/
    __main__.py faz com `if forward_to_running(file_args): return 0`) rodam
    em PROCESSOS SEPARADOS de verdade."""
    out_file = tmp_path / "recebidos.txt"
    server_code = f"""
import os, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from app.presentation.single_instance import start_server
app = QApplication.instance() or QApplication([])
def on_paths(files):
    with open(r"{out_file}", "w", encoding="utf-8") as f:
        f.write(repr(files))
server = start_server(on_paths, name="{_TEST_NAME}.proc")
t0 = time.time()
while time.time() - t0 < 6.0:
    app.processEvents()
    time.sleep(0.02)
"""
    client_code = f"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from app.presentation.single_instance import forward_to_running
app = QApplication.instance() or QApplication([])
ok = forward_to_running([r"C:\\arte\\pedido123.pdf", r"C:\\arte\\faca.pdf"], name="{_TEST_NAME}.proc")
print("forward=", ok)
"""
    server_proc = subprocess.Popen(
        [sys.executable, "-u", "-c", server_code], cwd=_REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        time.sleep(1.0)  # da tempo do servidor subir e comecar a escutar
        client = subprocess.run(
            [sys.executable, "-u", "-c", client_code], cwd=_REPO_ROOT,
            capture_output=True, text=True, timeout=15,
        )
        assert "forward= True" in client.stdout, (
            f"cliente nao detectou a instancia aberta: {client.stdout} {client.stderr}"
        )
        server_proc.wait(timeout=10)
    finally:
        if server_proc.poll() is None:
            server_proc.kill()

    assert out_file.exists(), "o servidor (1a instancia) nunca recebeu a conexao do cliente"
    recebidos = eval(out_file.read_text(encoding="utf-8"))  # noqa: S307 (teste controlado)
    assert recebidos == [r"C:\arte\pedido123.pdf", r"C:\arte\faca.pdf"]


def test_segunda_instancia_sem_servidor_nao_trava(qapp):
    """Sem NENHUMA instancia rodando (nome exclusivo, nunca usado neste
    processo), o cliente tem que desistir rapido (timeout curto) e devolver
    False — nunca travar esperando um servidor que nao existe."""
    t0 = time.monotonic()
    entregue = forward_to_running(["/x/a.pdf"], name="PrintNestPro.test.qaf3.inexistente")
    elapsed = time.monotonic() - t0
    assert entregue is False
    assert elapsed < 5.0, f"forward_to_running sem servidor demorou {elapsed:.1f}s"


def test_segunda_instancia_lista_vazia_so_traz_a_frente_processo_real(tmp_path):
    """Lista vazia e valida (so pede pra trazer a janela existente a frente,
    sem soltar nenhum arquivo novo) — nao pode quebrar nem ser tratada como
    erro. Processo real (mesma logica de fidelidade do teste acima)."""
    out_file = tmp_path / "recebidos_vazio.txt"
    server_code = f"""
import os, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from app.presentation.single_instance import start_server
app = QApplication.instance() or QApplication([])
def on_paths(files):
    with open(r"{out_file}", "w", encoding="utf-8") as f:
        f.write(repr(files))
server = start_server(on_paths, name="{_TEST_NAME}.vazio.proc")
t0 = time.time()
while time.time() - t0 < 6.0:
    app.processEvents()
    time.sleep(0.02)
"""
    client_code = f"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from app.presentation.single_instance import forward_to_running
app = QApplication.instance() or QApplication([])
ok = forward_to_running([], name="{_TEST_NAME}.vazio.proc")
print("forward=", ok)
"""
    server_proc = subprocess.Popen(
        [sys.executable, "-u", "-c", server_code], cwd=_REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        time.sleep(1.0)
        client = subprocess.run(
            [sys.executable, "-u", "-c", client_code], cwd=_REPO_ROOT,
            capture_output=True, text=True, timeout=15,
        )
        assert "forward= True" in client.stdout
        server_proc.wait(timeout=10)
    finally:
        if server_proc.poll() is None:
            server_proc.kill()

    assert out_file.exists()
    recebidos = eval(out_file.read_text(encoding="utf-8"))  # noqa: S307
    assert recebidos == []


def test_segunda_instancia_mesmo_processo_pode_perder_a_entrega(qapp):
    """QA-F3-16 (achado metodologico, nao bug de producao): reproduz, DENTRO
    do mesmo processo/thread do servidor de teste, um efeito colateral do
    QLocalSocket local de forward_to_running() ser destruido (GC do Python)
    logo ao retornar da funcao — a entrega pode chegar VAZIA ao servidor
    quando cliente e servidor compartilham a mesma QApplication/thread.
    Confirmado que em processos SEPARADOS (uso real) isso NAO acontece — ver
    test_segunda_instancia_com_arquivo_e_entregue_a_primeira_processo_real.
    Documentado aqui como suspeita de fragilidade (nao cria referencia forte
    ao socket, nem parent) que só nao vira bug visivel porque o app real
    sempre roda em processos distintos."""
    recebidos = {}
    server = start_server(
        lambda files: recebidos.setdefault("files", files), name=_TEST_NAME + ".samep"
    )
    try:
        entregue = forward_to_running(
            [r"C:\arte\pedido123.pdf", r"C:\arte\faca.pdf"], name=_TEST_NAME + ".samep"
        )
        assert entregue is True
        for _ in range(50):
            qapp.processEvents()
        esperado = [r"C:\arte\pedido123.pdf", r"C:\arte\faca.pdf"]
        if recebidos.get("files") != esperado:
            pytest.xfail(
                "QA-F3-16b: no MESMO processo/thread, forward_to_running() "
                "as vezes entrega lista VAZIA em vez dos caminhos "
                f"(recebido={recebidos.get('files')!r}) — o QLocalSocket "
                "local (single_instance.py forward_to_running) e destruido "
                "(GC) assim que a funcao retorna, sem parent/referencia "
                "externa. So nao afeta o uso real por rodar sempre em "
                "processos separados; ainda assim, um `sock.setParent` ou "
                "manter uma referencia viva ate o disconnect completo "
                "deixaria o código mais robusto/testavel."
            )
    finally:
        server.close()
        server.deleteLater()
        for _ in range(5):
            qapp.processEvents()
