"""Defeitos da auditoria de 13/10/2026 na janela principal.

Cada teste reproduz o cenário real relatado na auditoria (estado vazando entre
abas/projetos, giro por peça ignorado, sangria trocada etc.) antes da correção.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from app.application.project_io import ProjectDocument, ProjectStore  # noqa: E402
from app.domain.geometry import Size  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _t():
    import tests.presentation.test_main_window as t

    return t


def _janela(tmp_path, qapp):
    t = _t()
    w = t._window(tmp_path)
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    return w


# ---- #1 geração em thread x troca de trabalho ----

def test_geracao_trava_abas_e_novo_trabalho(qapp, tmp_path):
    t = _t()
    w = _janela(tmp_path, qapp)
    w.add_paths([t._two_page_pdf(tmp_path)])
    w.generate()
    assert w.generating()
    assert not w._tabbar.isEnabled()
    assert not w._tab_plus.isEnabled()
    w._new_tab()
    assert w._tabbar.count() == 1  # aba nova recusada durante a geração
    assert w.open_project(str(tmp_path / "x.printnest")) is False
    t._esperar_geracao(w)
    assert w._tabbar.isEnabled() and w._tab_plus.isEnabled()
    assert w._result is not None
    w.close()


def test_resultado_de_outro_trabalho_e_descartado(qapp, tmp_path):
    t = _t()
    w = _janela(tmp_path, qapp)
    w.add_paths([t._two_page_pdf(tmp_path)])
    w.generate()
    w._nova_epoca()  # o trabalho ativo mudou enquanto a thread rodava
    t._esperar_geracao(w)
    assert w._result is None
    assert w._tabbar.isEnabled()
    w.close()


# ---- #2 recorte e tamanho por arquivo no .printnest ----

def test_projeto_guarda_recorte_e_tamanho_por_arquivo(qapp, tmp_path):
    t = _t()
    pdf = t._two_page_pdf(tmp_path)
    w = _janela(tmp_path, qapp)
    w.add_paths([pdf])
    w._page_crops[pdf] = {0: (1.0, 2.0, 3.0, 4.0)}
    w._file_sizes[pdf] = Size(50.0, 25.0)
    alvo = str(tmp_path / "proj.printnest")
    assert w.save_project(alvo)
    w.close()

    (tmp_path / "b").mkdir()
    w2 = _janela(tmp_path / "b", qapp)
    assert w2.open_project(alvo)
    assert w2._page_crops == {pdf: {0: (1.0, 2.0, 3.0, 4.0)}}
    assert w2._file_sizes[pdf] == Size(50.0, 25.0)
    w2.close()


def test_assinatura_do_arranjo_inclui_recorte_e_tamanho(qapp, tmp_path):
    t = _t()
    pdf = t._two_page_pdf(tmp_path)
    w = _janela(tmp_path, qapp)
    w.add_paths([pdf])
    sem = w._arranjo_signature()
    assert sem == [[pdf, 1]]  # projeto sem ajuste: formato antigo intacto
    w._file_sizes[pdf] = Size(50.0, 25.0)
    assert w._arranjo_signature() != sem
    w.close()


def test_project_io_recorte_tamanho_roundtrip_e_projeto_antigo(tmp_path):
    doc = ProjectDocument(
        page_crops={"a.pdf": {0: (1.0, 2.0, 3.0, 4.0)}},
        file_sizes={"a.pdf": (50.0, 25.0)},
    )
    store = ProjectStore()
    alvo = tmp_path / "p.printnest"
    store.save(alvo, doc)
    lido = store.load(alvo)
    assert lido.page_crops == {"a.pdf": {0: (1.0, 2.0, 3.0, 4.0)}}
    assert lido.file_sizes == {"a.pdf": (50.0, 25.0)}
    antigo = ProjectDocument.from_dict({"version": 1, "files": []})
    assert antigo.page_crops == {} and antigo.file_sizes == {}
    assert "page_crops" not in ProjectDocument().to_dict()
    lixo = ProjectDocument.from_dict({
        "version": 1,
        "page_crops": {"a": {"x": [1, 2, 3, 4], "0": [1, 2]}, "b": 3},
        "file_sizes": {"a": [0, 5], "b": ["1", 2], "c": [10, 20]},
    })
    assert lixo.page_crops == {}
    assert lixo.file_sizes == {"c": (10.0, 20.0)}


# ---- #3 abrir projeto na mesma aba não herda estado do anterior ----

def test_abrir_projeto_zera_ajustes_do_anterior(qapp, tmp_path):
    t = _t()
    pdf = t._two_page_pdf(tmp_path)
    w = _janela(tmp_path, qapp)
    alvo = str(tmp_path / "vazio.printnest")
    w.add_paths([pdf])
    assert w.save_project(alvo)
    w._page_crops[pdf] = {0: (5.0, 5.0, 5.0, 5.0)}
    w._file_sizes[pdf] = Size(10.0, 10.0)
    w._file_pages[pdf] = [1]
    w._baked_crops[(pdf, "sig")] = "cache.pdf"
    w._crop_cache["cache.pdf"] = pdf
    w._faca_on = True
    assert w.open_project(alvo)
    assert w._page_crops == {}
    assert w._file_sizes == {}
    assert w._file_pages == {}
    assert w._baked_crops == {} and w._crop_cache == {}
    assert w._faca_on is False
    w.close()


# ---- #16 aba nova não herda páginas nem arranjo pendente ----

def test_aba_nova_nao_herda_paginas_nem_arranjo_pendente(qapp, tmp_path):
    t = _t()
    pdf = t._two_page_pdf(tmp_path)
    w = _janela(tmp_path, qapp)
    w.add_paths([pdf])
    w._file_pages[pdf] = [1]
    w._pending_arranjo = {"chapas": [{"itens": []}]}
    w._new_tab()
    assert w._file_pages == {}
    assert w._pending_arranjo is None
    w._tabbar.setCurrentIndex(0)
    assert w._file_pages == {pdf: [1]}
    assert w._pending_arranjo == {"chapas": [{"itens": []}]}
    w.close()


# ---- #4 giro por peça do auto-rotacionar entra no espaço ocupado ----

def _peca_deitada(tmp_path, qapp):
    """Arte 141x106 numa chapa de 125: o encaixe só consegue deitando a peça."""
    import fitz

    doc = fitz.open()
    pg = doc.new_page(width=400, height=300)
    pg.draw_rect(fitz.Rect(0, 0, 400, 300), color=(0, 0, 0), fill=(0, 0, 0))
    src = str(tmp_path / "deitada.pdf")
    doc.save(src)
    doc.close()
    w = _janela(tmp_path, qapp)
    w.add_paths([src])
    w._set_auto_rotate(True)
    w._auto_rotate.setChecked(True)
    w._width.setValue(125)
    w.generate(blocking=True)
    assert [p.giro for p in w._piece_items] == [90]
    return w


def test_ajustar_chapa_ao_conteudo_respeita_peca_deitada(qapp, tmp_path):
    w = _peca_deitada(tmp_path, qapp)
    rect = w._piece_items[0].rect()
    w._fit_sheets_to_content()
    chapa = w._effective_sheets()[0]
    assert chapa.material.width == pytest.approx(rect.width(), abs=0.01)
    assert chapa.used_length == pytest.approx(rect.height(), abs=0.01)
    w.close()


def test_repetir_em_grade_nao_sobrepoe_peca_deitada(qapp, tmp_path):
    w = _peca_deitada(tmp_path, qapp)
    altura = w._piece_items[0].rect().height()
    for p in w._piece_items:
        p.setSelected(True)
    w._step_repeat(1, 2, 0.0)
    ys = sorted(i.position.y for i in w._effective_sheets()[0].items)
    assert ys[1] - ys[0] == pytest.approx(altura, abs=0.01)
    w.close()


# ---- #5/#6/#7 barra Faca e card "Faca deste arquivo" ----

def _janela_com_pdf(tmp_path, qapp):
    t = _t()
    pdf = t._two_page_pdf(tmp_path)
    w = _janela(tmp_path, qapp)
    w.add_paths([pdf])
    w.generate(blocking=True)
    return w, pdf


def test_raio_do_arquivo_nao_vaza_para_o_global(qapp, tmp_path):
    w, pdf = _janela_com_pdf(tmp_path, qapp)
    w._selected_path = pdf
    w._ct_radius.setValue(5.0)
    w._apply_contour_radius()
    assert w._file_overrides[pdf]["corner_radius"] == 5.0
    w._sync_contour_tool()  # barra exibe o raio do arquivo (5)
    w._selected_path = None
    assert w._global_faca_params()["corner_radius"] == 0.0
    w._sync_contour_tool()
    assert w._ct_radius.value() == 0.0  # sem seleção: o global
    w.close()


def test_campo_do_card_grava_so_a_propria_chave(qapp, tmp_path):
    w, pdf = _janela_com_pdf(tmp_path, qapp)
    w._load_piece_faca(w._piece_items[0])
    assert w._selected_path == pdf
    w._pf_offset.setValue(4.0)
    assert w._file_overrides[pdf] == {"offset": 4.0}
    w._crop.setValue(2.0)  # global continua alcançando o arquivo
    assert w._params_for(pdf)["crop"] == 2.0
    w.close()


def test_barra_faca_mostra_sangria_do_pdf_e_canto_do_arquivo(qapp, tmp_path):
    w, pdf = _janela_com_pdf(tmp_path, qapp)
    w._offset.setValue(1.0)
    w._auto_offset.setValue(3.0)  # sangria de IMAGEM: não vale para PDF
    w._file_overrides[pdf] = {"corner": "miter"}
    w._selected_path = pdf
    w._sync_contour_tool()
    assert w._ct_offset.value() == 1.0
    marcado = w._ct_corner_val[w._ct_corner.checkedId()]
    assert marcado == "miter"
    w._ct_offset.setValue(2.0)
    w._apply_contour_offset()
    assert w._file_overrides[pdf] == {"corner": "miter", "offset": 2.0}
    w.close()


# ---- #8/#9/#10 redimensionar pelo espaço ocupado + desfazer ----

def _sel_unica(w):
    piece = w._piece_items[0]
    w._scene.clearSelection()
    piece.setSelected(True)
    QApplication.processEvents()
    return w._selected_pieces()[0]


def test_barra_la_redimensiona_pelo_ocupado_com_sangria(qapp, tmp_path):
    w, pdf = _janela_com_pdf(tmp_path, qapp)
    w._offset.setValue(2.0)  # faca 2 mm fora: ocupado = arte + 4
    piece = _sel_unica(w)
    largura = piece.rect().width()
    w._ps_lock.setChecked(False)
    w._pb_w.setValue(largura + 10)  # dispara _pbar_resize("w")
    w._pbar_resize("w")
    assert _sel_unica(w).rect().width() == pytest.approx(largura + 10, abs=0.05)
    w.close()


def test_barra_la_em_arquivo_girado_nao_troca_os_lados(qapp, tmp_path):
    w, pdf = _janela_com_pdf(tmp_path, qapp)
    w._file_overrides[pdf] = {"rotation": 90}
    w._relayout(renest=False)
    piece = _sel_unica(w)
    altura = piece.rect().height()
    w._ps_lock.setChecked(False)
    w._pbar_loading = True
    w._pb_w.setValue(50.0)
    w._pbar_loading = False
    w._pbar_resize("w")
    nova = _sel_unica(w).rect()
    assert nova.width() == pytest.approx(50.0, abs=0.05)
    assert nova.height() == pytest.approx(altura, abs=0.05)
    w.close()


def test_alca_arrasta_pelo_ocupado_e_clique_nao_redimensiona(qapp, tmp_path):
    import app.presentation.main_window as mw
    from PySide6.QtCore import QPoint, QPointF

    w, pdf = _janela_com_pdf(tmp_path, qapp)
    w._offset.setValue(2.0)
    piece = _sel_unica(w)
    largura = piece.rect().width()
    w._ps_lock.setChecked(False)

    class _Ev:
        def __init__(self, scene, tela):
            self._s, self._t = scene, tela

        def scenePos(self):
            return self._s

        def screenPos(self):
            return self._t

        def buttonDownScreenPos(self, _b):
            return QPoint(100, 100)

        def accept(self):
            pass

    handle = mw._ResizeHandle(w, piece, "w")
    canto = piece.scenePos() + QPointF(largura, piece.rect().height())
    handle.setPos(canto)
    handle.mousePressEvent(_Ev(canto + QPointF(-3, -3), QPoint(100, 100)))
    # só clicou (soltou no mesmo pixel): nada muda
    handle.mouseReleaseEvent(_Ev(canto + QPointF(-3, -3), QPoint(101, 100)))
    assert w._file_sizes == {}
    handle.mousePressEvent(_Ev(canto + QPointF(-3, -3), QPoint(100, 100)))
    handle.mouseReleaseEvent(_Ev(canto + QPointF(7, -3), QPoint(140, 100)))
    assert _sel_unica(w).rect().width() == pytest.approx(largura + 10, abs=0.05)
    w.close()


def test_desfazer_redimensionar_gruda(qapp, tmp_path):
    w, pdf = _janela_com_pdf(tmp_path, qapp)
    piece = _sel_unica(w)
    largura = piece.rect().width()
    w._ps_lock.setChecked(True)
    w._redimensionar_pelo_ocupado(piece, largura * 2, piece.rect().height(), "w")
    assert pdf in w._file_sizes
    w._undo.undo()
    assert pdf not in w._file_sizes
    w._undo.redo()
    assert pdf in w._file_sizes
    w._undo.undo()
    w._relayout(renest=False)  # recálculo seguinte não reaplica o desfeito
    assert w._piece_items[0].rect().width() == pytest.approx(largura, abs=0.05)
    w.close()


def test_desfazer_faca_do_arquivo_gruda(qapp, tmp_path):
    w, pdf = _janela_com_pdf(tmp_path, qapp)
    w._load_piece_faca(w._piece_items[0])
    w._pf_offset.setValue(w._offset.value() + 5.0)
    assert set(w._file_overrides.get(pdf)) == {"offset"}
    w._undo.undo()
    assert pdf not in w._file_overrides
    w.close()


# ---- #11 LengthSpin aceita valor digitado em cm ----

def test_lengthspin_aceita_cm_digitado_em_faixa_de_mm(qapp):
    from app.presentation import units
    from app.presentation.main_window import LengthSpin
    from PySide6.QtGui import QValidator
    from PySide6.QtTest import QTest

    antiga = units.unit()
    units.set_unit("cm")
    try:
        spin = LengthSpin(0.3, 2.0)  # espessura da marca de registro
        assert spin.validate("0.05 cm", 4)[0] == QValidator.State.Acceptable
        assert spin.validate("0.", 2)[0] == QValidator.State.Intermediate
        assert spin.validate("abc", 3)[0] == QValidator.State.Invalid
        spin.show()
        spin.lineEdit().selectAll()
        QTest.keyClicks(spin.lineEdit(), "0.05")
        spin.interpretText()
        assert spin.value() == pytest.approx(0.5)
    finally:
        units.set_unit(antiga)


# ---- #12 zoom com limite / régua com poucas marcas ----

def test_zoom_tem_limite_e_regua_nao_explode(qapp, tmp_path):
    import time

    from app.presentation.main_window import Ruler, ZoomableGraphicsView

    w = _janela(tmp_path, qapp)
    v = w._view
    for _ in range(400):
        w._zoom_step(1 / 1.15)
    assert v.zoom_factor() == pytest.approx(ZoomableGraphicsView.ZOOM_MIN, rel=1e-6)
    t0 = time.perf_counter()
    w._h_ruler.grab()
    w._v_ruler.grab()
    assert time.perf_counter() - t0 < 2.0
    for _ in range(400):
        v.zoom_by(1.15)
    assert v.zoom_factor() == pytest.approx(ZoomableGraphicsView.ZOOM_MAX, rel=1e-6)
    assert Ruler._nice_step(1e-6) == 1e8
    w.close()


# ---- #13 ferramenta mão arrasta a tela ----

def test_ferramenta_mao_mantem_o_modo_de_arrastar_tela(qapp, tmp_path):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QGraphicsView

    w, _pdf = _janela_com_pdf(tmp_path, qapp)
    w._set_hand_tool(True)
    vp = w._view.viewport()
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
    assert w._view.dragMode() == QGraphicsView.ScrollHandDrag
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
    w._set_hand_tool(False)
    assert w._view.dragMode() == QGraphicsView.NoDrag
    w.close()


# ---- #14 encaixe de várias peças mantém o espaçamento ----

def test_encaixe_de_grupo_mantem_espacamento(qapp, tmp_path):
    from PySide6.QtCore import QPointF

    w, _pdf = _janela_com_pdf(tmp_path, qapp)
    a, b = w._piece_items[:2]
    sx, sy, _sw, _sl = a.sheet_rect
    # A a 1 mm da borda da chapa (vai encaixar); B longe de qualquer linha
    a.setPos(QPointF(sx + 1.0, sy + 50.0))
    b.setPos(QPointF(sx + 1.0 + a.rect().width() + 9.3, sy + 50.0))
    for p in (a, b):
        p.setSelected(True)
    afast = b.pos() - a.pos()
    w._begin_move()
    a.grabMouse()
    try:
        # mesmo deslocamento para as duas; a ordem do Qt não é garantida
        d = QPointF(0.2, 0.0)
        b.setPos(b.pos() + d)
        a.setPos(a.pos() + d)
    finally:
        a.ungrabMouse()
        w._snap.dragging = False
    assert a.pos().x() == pytest.approx(sx)  # o líder encaixou na borda
    dif = b.pos() - a.pos()
    assert dif.x() == pytest.approx(afast.x()) and dif.y() == pytest.approx(afast.y())
    w.close()


# ---- #17 recorte na página como é VISTA (/Rotate e EXIF) ----

def test_recorte_de_pdf_deitado_corta_o_lado_visto(qapp, tmp_path):
    import fitz

    doc = fitz.open()
    pg = doc.new_page(width=200, height=100)
    pg.set_rotation(90)  # vista: 100 de largura x 200 de altura
    src = str(tmp_path / "deitado.pdf")
    doc.save(src)
    doc.close()
    w = _janela(tmp_path, qapp)
    out = w._bake_cropped_pdf(src, {0: (0.0, 10.0, 0.0, 0.0)}, ("t",))
    assert out is not None
    with fitz.open(out) as d:
        r = d[0].rect  # já considera o /Rotate
        assert r.width == pytest.approx(100.0, abs=0.01)
        assert r.height == pytest.approx(200.0 - 10 * 72 / 25.4, abs=0.01)
    w.close()


def test_recorte_de_foto_respeita_exif_qualidade_e_perfil(qapp, tmp_path):
    from PIL import Image

    stored = Image.new("RGB", (200, 100), (200, 30, 30))
    exif = Image.Exif()
    exif[0x0112] = 6  # celular em pé: vista 100 x 200
    src = str(tmp_path / "foto.jpg")
    icc = b"perfil-de-teste"
    stored.save(src, exif=exif, dpi=(25.4, 25.4), quality=95, icc_profile=icc)
    w = _janela(tmp_path, qapp)
    out = w._bake_cropped_image(src, {0: (0.0, 10.0, 0.0, 0.0)}, ("f",))
    assert out is not None
    with Image.open(out) as im:
        assert im.size == (100, 190)  # cortou o TOPO visto
        assert im.info.get("icc_profile") == icc
    w.close()


def test_project_io_quantidade_ou_giro_invalidos_nao_quebram_abertura():
    doc = ProjectDocument.from_dict({
        "version": 1,
        "files": [
            {"path": "a.pdf", "quantity": "abc", "rotation": "x"},
            {"path": "b.pdf", "quantity": "3", "rotation": 90.0, "pages": [1, -2]},
        ],
    })
    assert (doc.files[0].quantity, doc.files[0].rotation) == (1, 0)
    assert (doc.files[1].quantity, doc.files[1].rotation) == (3, 90)
    assert doc.files[1].pages == [1]


# ---- #15/#18/#19 ----

def test_sensibilidade_por_teclado_aplica_sem_soltar_alca(qapp, tmp_path, monkeypatch):
    w, _pdf = _janela_com_pdf(tmp_path, qapp)
    chamadas = []
    monkeypatch.setattr(w, "generate", lambda **kw: chamadas.append(kw))
    w._ct_sensitivity.setValue(30)  # trilho/teclado: sem sliderReleased
    assert w._ct_sens_timer.isActive()
    w._ct_sens_timer.timeout.emit()
    assert w._auto_sensitivity.value() == 30
    assert chamadas
    w.close()


def test_adicionar_com_mesa_ocupada_preserva_faca_global(qapp, tmp_path):
    t = _t()
    w, pdf = _janela_com_pdf(tmp_path, qapp)
    w._offset.setValue(4.0)
    outro = tmp_path / "outro"
    outro.mkdir()
    w._adicionar_do_usuario([t._two_page_pdf(outro)])
    assert w._offset.value() == 4.0
    w.close()


def _porta(w, porta, caminho, monkeypatch):
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent
    from PySide6.QtWidgets import QFileDialog

    if porta == "botao":
        monkeypatch.setattr(
            QFileDialog, "getOpenFileNames", lambda *a, **k: ([caminho], "")
        )
        w.add_pdfs()
    elif porta == "janela":
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(caminho)])
        w.dropEvent(QDropEvent(QPointF(5, 5), Qt.CopyAction, mime, Qt.LeftButton,
                               Qt.NoModifier))
    elif porta == "area":
        w._view.files_dropped.emit([caminho])
    else:
        w.open_external_files([caminho])


@pytest.mark.parametrize("porta", ["botao", "janela", "area", "externo"])
def test_mesa_vazia_mesma_regra_nas_quatro_portas(qapp, tmp_path, monkeypatch, porta):
    t = _t()
    w = _janela(tmp_path, qapp)
    w._spacing.setValue(7.0)          # operador acabou de ajustar
    reg_antes = w._reg_type.currentIndex()
    largura = w._width.value()
    w._offset.setValue(4.0)           # faca de outra sessão: volta ao padrão
    w._faca_radius = 3.0
    w._file_overrides["velho.pdf"] = {"offset": 9.0}
    _porta(w, porta, t._two_page_pdf(tmp_path), monkeypatch)
    assert w._paths
    assert w._spacing.value() == 7.0
    assert w._reg_type.currentIndex() == reg_antes
    assert w._width.value() == largura
    assert w._offset.value() == 0
    assert w._faca_radius == 0.0
    assert w._file_overrides == {}
    w.close()


def test_chapa_com_decimais_volta_com_decimais(qapp, tmp_path):
    w = _janela(tmp_path, qapp)
    w._settings.material_width = 1066.8
    w._settings.material_height = 500.5
    w._load_settings()
    assert w._width.value() == pytest.approx(1066.8)
    assert w._height.value() == pytest.approx(500.5)
    w.close()


def test_faca_vetorial_usa_a_caixa_de_importacao(qapp, tmp_path, monkeypatch):
    w, _pdf = _janela_com_pdf(tmp_path, qapp)
    vistos = []

    def falso(path, page, box="media"):
        vistos.append(box)
        return []

    monkeypatch.setattr(w._vector_extractor, "extract_rings_info", falso)
    w._vector_contours = {}
    art = w._base_artworks[0]
    w._pdf_vector_contour_ex(art)
    assert vistos == [w._import_box.currentData()]
    w._pdf_vector_contour_ex(art)  # cache: não extrai de novo
    assert len(vistos) == 1
    w.close()


# ---- #20 substituir arquivo ----

def test_substituir_por_arquivo_ja_na_biblioteca_recusa_e_marca_sujo(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    t = _t()
    a = t._two_page_pdf(tmp_path)
    (tmp_path / "b").mkdir()
    b = t._two_page_pdf(tmp_path / "b")
    (tmp_path / "c").mkdir()
    c = t._two_page_pdf(tmp_path / "c")
    w = _janela(tmp_path, qapp)
    w.add_paths([a, b])
    w._dirty = False
    w._table.setCurrentCell(0, 0)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a_, **k: (b, ""))
    w.replace_selected()
    assert w._paths == [a, b]  # não duplicou
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a_, **k: (c, ""))
    w.replace_selected()
    assert w._paths == [c, b]
    assert w._dirty
    w.close()


# ---- #21 DXF por chapa numerado pela chapa ----

def test_dxf_por_chapa_usa_numero_da_chapa_e_avisa_selecao_vazia(qapp, tmp_path):
    import fitz

    doc = fitz.open()
    for _ in range(8):
        pg = doc.new_page(width=283.46, height=170.08)
        pg.draw_rect(pg.rect, color=(0, 0, 0), fill=(0, 0, 0))
    src = tmp_path / "multi.pdf"
    doc.save(str(src))
    doc.close()
    w = _janela(tmp_path, qapp)
    w.add_paths([str(src)])
    w._width.setValue(120)
    w._height.setValue(150)
    w.generate(blocking=True)
    assert len(w._result.sheets) >= 2
    w.export_dxf_per_sheet(str(tmp_path / "CORTE.dxf"), pages=[1])
    assert [p.name for p in tmp_path.glob("CORTE_*.dxf")] == ["CORTE_02.dxf"]
    avisos = []
    w._toasts.warning = lambda msg: avisos.append(msg)
    w.export_dxf_per_sheet(str(tmp_path / "VAZIO.dxf"), pages=[99])
    assert avisos and not list(tmp_path.glob("VAZIO_*.dxf"))
    w.close()


# ---- revisão: recorte medido a partir da região importada (CropBox/TrimBox) ----

@pytest.mark.parametrize(("caixa", "base"), [("media", (20, 20, 200, 200)),
                                             ("trim", (40, 40, 180, 180))])
def test_recorte_de_pdf_parte_da_regiao_da_caixa(qapp, tmp_path, caixa, base):
    import pikepdf
    from app.infrastructure.importers.pdfium_importer import PdfiumImporter

    pdf = pikepdf.new()
    pg = pdf.add_blank_page(page_size=(220, 220))
    pg.CropBox = [20, 20, 200, 200]
    pg.TrimBox = [40, 40, 180, 180]
    src = str(tmp_path / f"caixas_{caixa}.pdf")
    pdf.save(src)
    w = _janela(tmp_path, qapp)
    mm = 72 / 25.4
    out = w._bake_cropped_pdf(src, {0: (10.0, 0.0, 0.0, 0.0)}, (caixa,), caixa)
    assert out is not None
    with pikepdf.open(out) as d:
        x0, y0, x1, y1 = (float(v) for v in d.pages[0].mediabox)
        assert x0 == pytest.approx(base[0] + 10 * mm)  # corta a borda VISTA
        assert (y0, x1, y1) == pytest.approx(base[1:])
        assert [float(v) for v in d.pages[0].CropBox] == pytest.approx([x0, y0, x1, y1])
        assert "/TrimBox" not in d.pages[0]
    largura_vista = (base[2] - base[0]) / mm
    art = PdfiumImporter().import_artworks(out, caixa)[0]
    assert art.size.width == pytest.approx(largura_vista - 10.0, abs=0.01)
    w.close()


def test_assinatura_do_recorte_inclui_a_caixa(qapp, tmp_path):
    t = _t()
    pdf = t._two_page_pdf(tmp_path)
    w = _janela(tmp_path, qapp)
    w.add_paths([pdf])
    w._page_crops[pdf] = {0: (1.0, 0.0, 0.0, 0.0)}
    a = w._effective_path(pdf)
    w._import_box.setCurrentIndex((w._import_box.currentIndex() + 1) % w._import_box.count())
    b = w._effective_path(pdf)
    assert a != b
    w.close()


def test_barra_la_em_faca_do_cliente_acerta_e_nao_anda(qapp, tmp_path):
    t = _t()
    w = _janela(tmp_path, qapp)
    w.add_paths([t._vector_cut_pdf(tmp_path)])
    w._faca_mode.setCurrentIndex(w._faca_mode.findData("vector"))
    w._offset.setValue(10.0)  # faca do cliente (56 mm) + 2x10 passa da arte (70 mm)
    w.generate(blocking=True)
    w._ps_lock.setChecked(True)
    piece = _sel_unica(w)
    from app.application.footprint import artwork_footprint
    art = w._result.artworks[0]
    assert artwork_footprint(art).width > art.size.width + 0.5  # folga escala
    for _ in range(2):  # 2º Enter com o mesmo valor não pode mexer
        w._pbar_loading = True
        w._pb_w.setValue(300.0)
        w._pbar_loading = False
        w._pbar_resize("w")
        piece = _sel_unica(w)
        assert piece.rect().width() == pytest.approx(300.0, abs=0.1)
    w.close()


def test_aba_libera_assim_que_o_resultado_chega(qapp, tmp_path, monkeypatch):
    t = _t()
    w = _janela(tmp_path, qapp)
    w.add_paths([t._two_page_pdf(tmp_path)])
    w.generate()
    # a thread "ainda encerrando" depois do resultado entregue
    monkeypatch.setattr(type(w._thread), "isRunning", lambda self: True)
    while w._result is None:
        qapp.processEvents()
    assert not w.generating()
    w._new_tab()
    assert w._tabbar.count() == 2  # não voltou com o aviso "Gerando"
    monkeypatch.undo()
    w._thread.wait(5000)
    w.close()


def test_porta_do_extrator_vetorial_repassa_a_caixa():
    from app.application.ports.vector_extractor import IVectorExtractor

    vistos = []

    class _Falso(IVectorExtractor):
        def extract_rings(self, path, page_index=0, box="media"):
            vistos.append(box)
            return [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]]

    assert len(_Falso().extract_rings_info("x.pdf", 0, box="trim")) == 1
    assert vistos == ["trim"]
