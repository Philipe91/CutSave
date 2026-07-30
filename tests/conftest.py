import contextlib
import gc
import os

import pytest

# Qt roda sem display (headless) durante os testes.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _qt_cleanup():
    """Destroi objetos Qt orfaos ao fim de CADA teste (QA-11).

    Sem isso, todas as janelas criadas pela suite eram coletadas de uma so vez
    no encerramento do interpretador e o teardown do Qt segfaultava (exit 139)
    DEPOIS de 100% dos testes passarem — confundindo CI que checa exit code.
    Coletar por teste, com o QApplication ainda vivo, destroi na ordem certa.
    """
    yield
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:  # ambiente sem Qt (nao acontece hoje, mas e barato)
        return
    gc.collect()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


def pytest_sessionfinish(session, exitstatus) -> None:
    """Fim da suite com Qt (QA-11): fecha as janelas e agenda o desarme.

    O shutdown implicito do PySide6 no exit do interpretador segfaultava
    (exit 139) quando a suite combinava as janelas da MainWindow com o
    QLocalServer do teste de instancia unica — DEPOIS de 100% verde. Nao
    adianta destruir o QApplication na mao: os caches de QPixmap (icones,
    miniaturas) morrem no gc seguinte sem app vivo e crasham igual. O caminho
    seguro e nem deixar o Qt chegar ao teardown: pytest_unconfigure sai com
    os._exit(exitstatus) quando um QApplication existiu na sessao.
    """
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if app is None:
        return  # sessao sem Qt: teardown normal do pytest, sem desarme
    global _EXIT_STATUS
    _EXIT_STATUS = int(exitstatus)
    for widget in QApplication.topLevelWidgets():
        with contextlib.suppress(RuntimeError):
            # PYTEST_CURRENT_TEST ja foi removida neste ponto; uma janela
            # "suja" (dirty) abriria o modal de descarte e penduraria a
            # suite para sempre no offscreen. Aqui nao ha trabalho a salvar.
            if hasattr(widget, "_dirty"):
                widget._dirty = False
            # o dirty agora e POR ABA (fica no snapshot da sessao): zera as
            # sessoes tambem, senao o closeEvent agregaria e abriria o modal
            for s in getattr(widget, "_sessions", []) or []:
                if isinstance(s, dict):
                    s["dirty"] = False
            widget.close()
    app.processEvents()


_EXIT_STATUS: int | None = None


def pytest_unconfigure(config) -> None:
    """Desarme do QA-11: roda depois de TODOS os hooks (relatorio impresso e
    limpeza do pytest concluida) e encerra o processo antes do teardown das
    DLLs do Qt — preservando o exitstatus real da suite. So e acionado quando
    um QApplication chegou a existir na sessao.

    No Windows, os._exit (ExitProcess) ainda roda o detach das DLLs, onde o
    Qt crasha e o faulthandler imprime um stack assustador (exit ja correto,
    mas suja a saida). TerminateProcess pula o detach: saida limpa."""
    if _EXIT_STATUS is None:
        return
    import faulthandler
    import sys

    sys.stdout.flush()
    sys.stderr.flush()
    faulthandler.disable()
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.TerminateProcess(handle, _EXIT_STATUS)
    os._exit(_EXIT_STATUS)
