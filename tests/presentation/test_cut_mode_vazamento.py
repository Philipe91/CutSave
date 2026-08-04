"""Abrir o Modo Corte nao pode deixar dialogo vivo pendurado na janela.

O PORQUE
--------
main_window abria o Modo Corte assim:

    CutModeDialog(self, export_dxf=self._dxf_export).exec()

O dialogo e criado com PAI (a MainWindow) e sem guardar referencia. No Qt,
quem tem pai pertence ao C++: destruir o wrapper Python NAO destroi o objeto.
Entao cada abertura deixava um CutModeDialog inteiro vivo — a cena, as pecas
importadas e toda a geometria — preso a janela principal ate o programa
fechar. Medido em 04/08/2026: 4 aberturas, 4 dialogos vivos.

O custo nao e so memoria: cada dialogo retido aumenta o grafo que o coletor de
lixo do Python precisa percorrer, e o crash.log de 04/08 flagrou exatamente a
thread principal coletando lixo dentro de _open_cut_mode enquanto o encaixe
rodava no pyclipper (que solta o GIL) na outra thread.

ATENCAO AO ESCOPO: isto NAO e prova de que o vazamento causa o crash
0xc0000374 do executavel. Aquele defeito segue sem reprodutor e e rastreado a
parte. Este teste trava o vazamento, que e certo e mensuravel por si so.
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase  # noqa: E402
from app.application.use_cases.import_image import ImportImageUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    RunProductionPipelineUseCase,
)
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter  # noqa: E402
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter  # noqa: E402
from app.infrastructure.importers.pdfium_importer import PdfiumImporter  # noqa: E402
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer  # noqa: E402
from app.presentation.cut_mode_dialog import CutModeDialog  # noqa: E402
from app.presentation.main_window import MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ABERTURAS = 5
ABERTURAS_COM_WORKER = 10
SVG_UI = Path(__file__).parents[1] / "fixtures" / "qa_cut_mode_ui.svg"


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path):
    store = SettingsStore(tmp_path / "config.json")
    settings = store.load_or_create()
    pipeline = RunProductionPipelineUseCase(
        ImportPdfUseCase(PdfiumImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(cache_dir=tmp_path / "imgcache")),
    )
    win = MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PikePdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PdfiumPageRenderer(),
        store,
        settings,
    )
    yield win
    win._dirty = False
    win.close()
    win.deleteLater()


def _dialogos_vivos(win) -> list:
    return [c for c in win.children() if isinstance(c, CutModeDialog)]


def _drenar(qapp) -> None:
    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_abrir_o_modo_corte_varias_vezes_nao_acumula_dialogo(window, qapp, monkeypatch):
    """O teste do defeito: ABERTURAS aberturas seguidas, zero dialogo retido.

    exec() e trocado por um retorno imediato — o laco modal travaria a suite e
    nao e ele que esta sob teste; o que importa e o que sobra depois.
    """
    monkeypatch.setattr(CutModeDialog, "exec", lambda self: 0)

    for _ in range(ABERTURAS):
        window._open_cut_mode()
        _drenar(qapp)

    vivos = _dialogos_vivos(window)
    assert not vivos, (
        f"{len(vivos)} CutModeDialog continuam presos a janela depois de "
        f"{ABERTURAS} aberturas. Cada um carrega cena, pecas e geometria, e "
        f"nunca mais e liberado."
    )


def test_um_dialogo_por_vez_enquanto_o_modo_corte_esta_aberto(window, qapp, monkeypatch):
    """Enquanto o exec() nao retornou, o dialogo TEM que estar vivo — o teste
    acima nao pode ser satisfeito destruindo o dialogo cedo demais."""
    visto = {}

    def _exec_espiao(self):
        visto["vivos"] = len(_dialogos_vivos(window))
        return 0

    monkeypatch.setattr(CutModeDialog, "exec", _exec_espiao)

    window._open_cut_mode()
    _drenar(qapp)

    assert visto["vivos"] == 1, "o dialogo precisa existir enquanto esta aberto"
    assert not _dialogos_vivos(window), "e precisa sumir depois de fechado"


def test_ciclo_modal_real_com_importacao_e_worker_nao_acumula_dialogo(
    window, qapp
):
    """Repete o fluxo real: exec modal, SVG, thread de nesting e fechamento."""
    assert SVG_UI.exists()

    for volta in range(ABERTURAS_COM_WORKER):
        estado = {"timeout": False, "organizou": False}

        def dirigir_dialogo():
            dialogos = _dialogos_vivos(window)
            assert len(dialogos) == 1
            dialog = dialogos[0]
            dialog._seconds.setValue(0.5)

            timeout = QTimer(dialog)
            timeout.setSingleShot(True)
            dialog._qa_timeout_timer = timeout

            def aguardar_worker():
                if dialog._nest_thread is None and dialog._layouts:
                    estado["organizou"] = True
                    timeout.stop()
                    dialog.reject()
                    return
                QTimer.singleShot(20, aguardar_worker)

            def abortar_se_travar():
                estado["timeout"] = True
                dialog._encerrar_thread()
                dialog.reject()

            timeout.timeout.connect(abortar_se_travar)
            timeout.start(8000)
            dialog.open_with_file(str(SVG_UI))
            QTimer.singleShot(20, aguardar_worker)

        QTimer.singleShot(0, dirigir_dialogo)
        window._open_cut_mode()
        _drenar(qapp)

        assert not estado["timeout"], f"worker travou na abertura {volta + 1}"
        assert estado["organizou"], f"nenhum layout na abertura {volta + 1}"
        assert _dialogos_vivos(window) == []
