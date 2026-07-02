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
