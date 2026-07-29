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


def test_arquivo_de_exemplo_existe_e_serve_ao_tutorial(tmp_path):
    # o tutorial guiado manda clicar em "Colocar na chapa"; sem o arquivo no
    # pacote o 1o passo mandaria fazer algo impossivel
    from app.application.use_cases.import_pdf import ImportPdfUseCase
    from app.infrastructure.importers.pdfium_importer import PdfiumImporter
    from app.presentation import tutorials

    caminho = tutorials.caminho_exemplo()
    assert caminho is not None, "assets/exemplo/exemplo-printnest.pdf nao veio no pacote"

    arts = ImportPdfUseCase(PdfiumImporter()).execute(str(caminho), "auto")
    assert len(arts) == 2  # 2 paginas = 2 pecas, e o que o tutorial promete
    for a in arts:  # adesivo de 9x9 cm
        assert abs(a.size.width - 90.0) < 1.0
        assert abs(a.size.height - 90.0) < 1.0


def test_exemplo_tem_silhueta_ondulada_para_o_contorno_justo():
    # a razao de ser do arquivo: o tutorial manda escolher "Contorno justo" e o
    # aluno tem de VER a faca abracando as ondas. Num selo quadrado o contorno
    # justo sairia igual ao retangular e o passo nao provaria nada.
    from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter
    from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer
    from app.presentation import tutorials

    caminho = str(tutorials.caminho_exemplo())
    det, ren = Cv2ImageImporter(), PdfiumPageRenderer()
    for pagina in range(2):
        png = ren.render_png(caminho, pagina, dpi=96)
        c = det.detect_contour_from_png(png, 96, sensitivity=50.0, ignore_white=True)
        assert c is not None, f"pagina {pagina}: deteccao automatica falhou"
        # retangulo teria pouquissimos nos; a silhueta ondulada tem centenas
        assert len(c.points) > 100, f"pagina {pagina}: contorno reto demais"


def test_exemplo_nao_tem_faca_do_cliente():
    # decisao do Philipe (29/07): o arquivo e SO de demonstracao do fluxo. A
    # linha magenta viraria faca do cliente e mudaria o que o tutorial ensina.
    from app.domain.cut.vector import select_cut_rings
    from app.infrastructure.importers.pdfium_vector_extractor import (
        PdfiumVectorExtractor,
    )
    from app.presentation import tutorials

    caminho = str(tutorials.caminho_exemplo())
    ext = PdfiumVectorExtractor()
    for pagina in range(2):
        _rings, motivo = select_cut_rings(ext.extract_rings_info(caminho, pagina))
        assert motivo != "magenta", f"pagina {pagina} tem faca do cliente"


def test_tutorial_guiado_avanca_quando_o_aluno_faz(tmp_path):
    # o passo MAO NA MASSA nao tem "Proximo": so avanca quando o sinal do
    # controle dispara. Aqui o teste faz o papel do aluno.
    from app.presentation import tutorials
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w._act_tutorial_guiado.trigger()
    tour = w._tour_overlay
    passos = tour._steps

    assert any(p.espera is not None for p in passos), "nenhum passo mao na massa"
    # o exemplo entrou na biblioteca e ficou selecionado (senao "Colocar na
    # chapa" sem selecao jogaria TODOS os arquivos do usuario)
    assert str(tutorials.caminho_exemplo()) in w._paths
    assert w._table.currentRow() == w._paths.index(str(tutorials.caminho_exemplo()))

    # passo 0 e narrado: clicar no veu avanca
    assert passos[0].espera is None
    tour.advance()

    # passo 1 e mao na massa (Colocar na chapa): "Proximo" some e o veu abre
    # buraco clicavel; avanca sozinho quando o botao e clicado
    assert passos[1].espera is not None
    assert not tour._next.isVisibleTo(tour._card)
    assert tour._skip_step.isVisibleTo(tour._card)
    indice = tour._index
    w._btn_place.click()
    assert tour._index == indice + 1, "o passo nao avancou quando o aluno agiu"
    # o clique monta a producao EM THREAD: esperar aqui evita deixar um
    # QThread vivo depois do teste (o Qt aborta o processo se a janela morrer
    # com thread rodando)
    t._esperar_geracao(w)

    # o sinal foi solto: agir de novo nao pode empurrar mais um passo
    indice = tour._index
    w._btn_place.click()
    t._esperar_geracao(w)
    assert tour._index == indice


def test_todo_passo_com_alvo_realmente_aponta_algo(tmp_path):
    # ESTE e o teste que faltava. Um alvo que nao resolve vira balao
    # centralizado: o tutorial FALA mas nao MOSTRA onde clicar. Foi assim que
    # os tutoriais de Modo Corte e de Registro sairam mudos — o alvo era
    # filtrado por "visivel" cedo demais (sub-aba fechada) ou nem existia
    # (Modo Corte e botao da ribbon, nao item de menu).
    from app.presentation import tutorials
    from app.presentation.onboarding import TourOverlay
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w.resize(1500, 950)
    w.show()  # sem mostrar, TUDO seria invisivel e o teste passaria de mentira
    app.processEvents()
    # producao montada: a barra da Faca so existe com peca na chapa
    w.add_paths([t._two_page_pdf(tmp_path)])
    w.generate(blocking=True)
    app.processEvents()

    roteiros = [(rot, b) for rot, _ic, b in tutorials.TUTORIAIS]
    roteiros.append(("Tutorial guiado", tutorials.guiado))

    falhas, mudos = [], []
    for label, builder in roteiros:
        passos = builder(w)
        overlay = TourOverlay(w, passos, mark_done=False)
        apontou = 0
        for i, passo in enumerate(passos):
            overlay._desconectar()
            overlay._index = i
            overlay._apply_step()  # roda o `preparar` (abre aba/sub-aba)
            app.processEvents()
            resolveu = overlay._resolver_alvo() is not None
            apontou += resolveu
            if passo.target is not None and not resolveu:
                falhas.append(f"  {label} / passo {i + 1}: {passo.title}")
        overlay._finish()
        # Um tutorial inteiro sem apontar nada e o defeito de 29/07: so texto,
        # sem mostrar o caminho. A checagem por passo NAO pega isso sozinha,
        # porque um alvo que falhou na montagem ja chega aqui como None e
        # passa por "narrado de proposito".
        if apontou < 2:
            mudos.append(f"  {label}: so {apontou} passo(s) apontando")

    assert not falhas, "passos que prometem apontar e nao apontam:\n" + "\n".join(falhas)
    assert not mudos, "tutoriais que so narram, sem mostrar onde:\n" + "\n".join(mudos)
    w.close()


def test_passo_so_avanca_com_a_escolha_certa(temp_settings):
    # o passo do "Contorno justo" escuta currentIndexChanged, que dispara em
    # QUALQUER opcao. O filtro `quando` faz o tutorial so seguir na opcao pedida.
    from PySide6.QtWidgets import QApplication, QComboBox, QWidget

    QApplication.instance() or QApplication([])
    ob = temp_settings

    win = QWidget()
    win.resize(800, 600)
    combo = QComboBox(win)
    for label, data in (("Errado A", "a"), ("Certo", "contour"), ("Errado B", "b")):
        combo.addItem(label, data)
    win.show()

    passos = [
        ob.TourStep(
            combo, "Escolha", "escolha a opcao certa",
            espera=combo.currentIndexChanged,
            quando=lambda: combo.currentData() == "contour",
        ),
        ob.TourStep(None, "Fim", "acabou"),
    ]
    tour = ob.TourOverlay(win, passos, mark_done=False)
    assert tour._index == 0

    combo.setCurrentIndex(2)  # opcao ERRADA: nao pode avancar
    assert tour._index == 0

    combo.setCurrentIndex(1)  # a pedida
    assert tour._index == 1

    win.deleteLater()


def test_tutorial_guiado_sem_o_arquivo_avisa_em_vez_de_abrir(tmp_path, monkeypatch):
    # build antigo sem o exemplo: melhor um aviso do que um tutorial mandando
    # clicar em algo que nao existe
    from app.presentation import tutorials
    from app.presentation.onboarding import TourOverlay
    from PySide6.QtWidgets import QApplication, QMessageBox

    QApplication.instance() or QApplication([])
    import app.presentation.main_window as mw
    import tests.presentation.test_main_window as t

    monkeypatch.setattr(tutorials, "caminho_exemplo", lambda: None)
    vistos = []
    monkeypatch.setattr(
        mw.QMessageBox, "information",
        lambda *a, **k: vistos.append(a) or QMessageBox.Ok,
    )
    w = t._window(tmp_path)
    w._act_tutorial_guiado.trigger()

    assert vistos, "nao avisou que o exemplo faltou"
    assert not any(isinstance(c, TourOverlay) for c in w.children())


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
