"""Tour de boas-vindas: passos avançam, conclui e persiste o 'já vi'."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.presentation import icons  # noqa: E402


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


def test_tutorial_nao_marca_o_tour_de_boas_vindas_como_visto(temp_settings):
    # os tutoriais do menu reusam o overlay do tour; se marcassem o "ja vi",
    # quem abrisse um tutorial de recurso perderia o tour da 1a abertura
    from PySide6.QtWidgets import QApplication, QWidget

    QApplication.instance() or QApplication([])
    ob = temp_settings
    assert ob.tour_done() is False

    win = QWidget()
    win.resize(800, 600)
    win.show()
    tut = ob.TourOverlay(win, [ob.TourStep(None, "Passo", "texto")], mark_done=False)
    tut.advance()  # concluiu o tutorial
    assert ob.tour_done() is False  # o tour de boas-vindas continua pendente

    win.deleteLater()


def test_overlay_acompanha_o_resize_da_janela(temp_settings):
    # o overlay e filho da janela e filho NAO segue o resize do pai sozinho:
    # sem o eventFilter o veu ficava do tamanho antigo (faixa clara na borda)
    from PySide6.QtWidgets import QApplication, QWidget

    QApplication.instance() or QApplication([])
    ob = temp_settings

    win = QWidget()
    win.resize(800, 600)
    win.show()
    tour = ob.TourOverlay(win, [ob.TourStep(None, "Passo", "texto")])
    assert tour.size() == win.rect().size()

    win.resize(1000, 700)
    QApplication.instance().processEvents()
    assert tour.size() == win.rect().size()

    win.deleteLater()


def test_menu_tutoriais_abre_cada_guia(tmp_path):
    # o menu Tutoriais tem uma entrada por recurso e cada uma abre o overlay
    # com passos de verdade (alvo ausente vira balao centralizado, nunca quebra)
    from app.presentation import tutorials
    from app.presentation.onboarding import TourOverlay
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    assert len(w._tutorial_actions) == len(tutorials.TUTORIAIS)
    assert len(tutorials.TUTORIAIS) >= 5  # cobre as principais funcoes

    for label, icon_name, builder in tutorials.TUTORIAIS:
        passos = builder(w)
        assert passos, f"tutorial '{label}' sem passos"
        assert all(p.title and p.text for p in passos), label
        # icone inexistente vira QIcon VAZIO sem erro: so um teste pega isso
        assert not icons.icon(icon_name).isNull(), f"icone '{icon_name}' nao existe"

    for act in w._tutorial_actions:
        act.trigger()
        assert isinstance(w._tour_overlay, TourOverlay)
    # abrir varios seguidos nao empilha overlay ativo (os anteriores levam
    # hide() + deleteLater). isHidden, e nao isVisible: a janela do teste nunca
    # e mostrada, entao nenhum filho seria "visivel"
    ativos = [c for c in w.children() if isinstance(c, TourOverlay) and not c.isHidden()]
    assert len(ativos) == 1


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
