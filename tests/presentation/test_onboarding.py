"""Tour de boas-vindas: passos avançam, conclui e persiste o 'já vi'."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def temp_settings(tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings

    ini = str(tmp_path / "tour.ini")

    def _factory(*_a, **_k):
        return QSettings(ini, QSettings.IniFormat)

    import app.presentation.onboarding as ob
    monkeypatch.setattr(ob, "QSettings", _factory)
    return ob


def test_tour_avanca_conclui_e_persiste(temp_settings):
    from PySide6.QtWidgets import QApplication, QLabel, QWidget

    QApplication.instance() or QApplication([])

    ob = temp_settings
    assert ob.tour_done() is False

    win = QWidget()
    win.resize(800, 600)
    alvo = QLabel("alvo", win)
    alvo.setGeometry(10, 10, 120, 30)
    win.show()

    steps = [
        ob.TourStep(alvo, "Passo 1", "texto"),
        ob.TourStep(None, "Fim", "acabou"),
    ]
    tour = ob.TourOverlay(win, steps)
    assert tour._index == 0
    assert "1 de 2" in tour._dots.text()

    tour.advance()
    assert tour._index == 1
    assert tour._next.text() == "Concluir"

    tour.advance()  # concluiu
    assert ob.tour_done() is True  # nao reaparece na proxima abertura

    win.deleteLater()


def test_janela_principal_nao_abre_tour_sob_pytest(tmp_path):
    # o auto-start é bloqueado em testes (PYTEST_CURRENT_TEST) — sem overlay
    # fantasma atrapalhando os demais testes de UI
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w._start_tour()  # sem force: deve sair silenciosamente
    from app.presentation.onboarding import TourOverlay
    assert not any(isinstance(c, TourOverlay) for c in w.children())
