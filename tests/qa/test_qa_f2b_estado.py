"""FASE 2B (QA) — maquina de estados do dialogo do Modo Corte: clique
duplo em Organizar, fechar durante o calculo, falha externa (Corel/disco)
virando aviso (nunca traceback), e reabertura sem vazamento de estado.
"""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.presentation.cut_mode_dialog import CutModeDialog  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

_XMLNS = 'xmlns="http://www.w3.org/2000/svg"'


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp):
    dlg = CutModeDialog(export_dxf=ExportDxfUseCase(DxfExporter()))
    dlg._seconds.setValue(0.5)
    yield dlg
    dlg.deleteLater()


def _rect_svg(tmp_path, w: float, h: float, name: str = "peca.svg") -> str:
    path = tmp_path / name
    path.write_text(
        f'<svg {_XMLNS} width="100mm" height="100mm" viewBox="0 0 100 100">'
        f'<rect x="0" y="0" width="{w}" height="{h}"/></svg>',
        encoding="utf-8",
    )
    return str(path)


def _wait_thread(dialog, qapp, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while dialog._nest_thread is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)


# -- Organizar 2x seguidas (clique duplo) ---------------------------------------


def test_organizar_duas_vezes_seguidas_nao_dispara_duas_threads(dialog, tmp_path, qapp):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._on_nest()
    primeira = dialog._nest_thread
    assert primeira is not None

    dialog._on_nest()  # clique duplo durante o calculo em curso
    assert dialog._nest_thread is primeira  # segunda chamada foi no-op

    _wait_thread(dialog, qapp)
    assert dialog._nest_thread is None
    assert dialog._layouts  # o resultado da (unica) thread foi aplicado


# -- fechar durante Organizar ----------------------------------------------------


def test_reject_durante_organizar_nao_fecha_e_avisa(dialog, tmp_path, qapp):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog.show()
    qapp.processEvents()
    dialog._on_nest()
    assert dialog._nest_thread is not None

    dialog.reject()
    assert dialog.isVisible()  # nao fechou com a thread viva
    assert "Aguarde" in dialog._status.text()

    _wait_thread(dialog, qapp)

    dialog.reject()  # thread livre: agora fecha de verdade
    assert not dialog.isVisible()


# -- Enviar p/ Corel sem Corel instalado -----------------------------------------


def test_enviar_para_corel_sem_corel_instalado_vira_aviso_sem_traceback(
    dialog, tmp_path, monkeypatch
):
    def _sem_corel(path):
        raise RuntimeError("CorelDRAW nao encontrado nesta maquina")

    monkeypatch.setattr("app.presentation.cut_mode_dialog.send_file_to_corel", _sem_corel)
    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: avisos.append(a)))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()

    dialog._send_to_corel()  # nao pode propagar o RuntimeError

    assert avisos, "falha ao enviar para o Corel devia virar aviso amigavel"
    assert "CorelDRAW" in str(avisos[0])


# -- Exportar para pasta invalida (aproxima "somente-leitura") -------------------


def test_exportar_para_pasta_invalida_avisa_sem_traceback(dialog, tmp_path, monkeypatch):
    # "somente-leitura" aproximado por pasta INEXISTENTE: no Windows, marcar
    # o atributo read-only de uma pasta nao impede escrita dentro dela (a
    # API nao bloqueia como no chmod do Linux) — pasta ausente reproduz o
    # mesmo sintoma real (IO falha ao gravar) sem depender de ACL de SO.
    destino = str(tmp_path / "pasta_sem_permissao_ou_inexistente" / "corte.dxf")
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (destino, ""))
    )
    avisos = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: avisos.append(a)))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()

    dialog._pick_export_path()  # nao pode estourar traceback

    assert avisos, "pasta de destino invalida devia virar aviso amigavel"
    assert not os.path.exists(destino)


# -- dialogo reaberto -------------------------------------------------------------


def test_dialogo_reaberto_pela_janela_principal_nao_vaza_estado_da_sessao_anterior(
    qapp, tmp_path
):
    # main_window.py cria uma instancia NOVA a cada abertura do Modo Corte
    # ("CutModeDialog(self, export_dxf=...).exec()") — nunca reaproveita a
    # mesma janela, entao o estado zerado aqui e a garantia de construcao,
    # nao de limpeza manual.
    dlg1 = CutModeDialog(export_dxf=ExportDxfUseCase(DxfExporter()))
    dlg1._seconds.setValue(0.5)
    dlg1.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dlg1._rotate_mode.setCurrentIndex(0)
    dlg1.nest()
    assert dlg1._layouts
    dlg1.deleteLater()

    dlg2 = CutModeDialog(export_dxf=ExportDxfUseCase(DxfExporter()))
    dlg2._seconds.setValue(0.5)
    assert dlg2._pieces == []
    assert dlg2._layouts == ()
    assert dlg2._list.count() == 0
    assert not dlg2._btn_export.isEnabled()
    dlg2.deleteLater()
