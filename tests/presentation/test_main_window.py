import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
import fitz  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase  # noqa: E402
from app.application.use_cases.import_image import ImportImageUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    RunProductionPipelineUseCase,
)
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pymupdf_print_exporter import PyMuPdfPrintExporter  # noqa: E402
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter  # noqa: E402
from app.infrastructure.importers.pymupdf_importer import PyMuPdfImporter  # noqa: E402
from app.infrastructure.rendering.pymupdf_renderer import PyMuPdfPageRenderer  # noqa: E402
from app.presentation.main_window import MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _two_page_pdf(tmp_path):
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=200, height=100)  # ~70.5 x 35.3 mm
        page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "fonte.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _window(tmp_path):
    store = SettingsStore(tmp_path / "config.json")
    settings = store.load_or_create()
    pipeline = RunProductionPipelineUseCase(
        ImportPdfUseCase(PyMuPdfImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(cache_dir=tmp_path / "imgcache")),
    )
    return MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PyMuPdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PyMuPdfPageRenderer(),
        store,
        settings,
    )


def test_fluxo_completo_da_ui(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])

    window.generate(blocking=True)  # roda o pipeline sincronamente

    assert window._result is not None
    assert sum(s.item_count for s in window._result.sheets) == 2
    # preview: material + 2 imagens (arte) + 2 facas
    assert len(window._scene.items()) >= 5
    # a arte foi rasterizada e cacheada (2 paginas distintas)
    assert len(window._pixmaps) == 2

    pdf_out = tmp_path / "IMPRESSAO.pdf"
    window.export_pdf(str(pdf_out))
    assert pdf_out.exists()
    assert fitz.open(str(pdf_out)).page_count == 1

    dxf_out = tmp_path / "CORTE.dxf"
    window.export_dxf(str(dxf_out))
    assert dxf_out.exists()
    doc = ezdxf.readfile(str(dxf_out))
    assert len(doc.modelspace().query("LWPOLYLINE")) == 2


def test_clique_do_botao_nao_usa_o_argumento_checked(qapp, tmp_path):
    # O sinal clicked envia um bool; export_pdf(False)/export_dxf(False) NAO
    # deve tratar False como caminho. Sem result, deve apenas retornar.
    window = _window(tmp_path)
    window.export_pdf(False)  # nao deve levantar nem tentar salvar em "False"
    window.export_dxf(False)
    assert window._result is None


def test_remover_pdf_da_lista(qapp, tmp_path):
    window = _window(tmp_path)
    window.add_paths(["a.pdf", "b.pdf"])
    assert window._table.rowCount() == 2
    window._table.setCurrentCell(0, 0)
    window.remove_selected()
    assert window._table.rowCount() == 1
    assert window._paths == ["b.pdf"]


def test_quantidade_multiplica_pecas(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)  # 2 paginas
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    base = sum(s.item_count for s in window._result.sheets)
    assert base == 2  # 2 paginas, qtd 1

    window._table.cellWidget(0, 1).setValue(3)  # qtd 3 -> dispara relayout
    total = sum(s.item_count for s in window._result.sheets)
    assert total == 6  # 2 paginas x 3


def test_relayout_em_tempo_real_ao_mudar_offset(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)

    faca_antes = window._result.artworks[0].cut_contour.size.width
    window._offset.setValue(window._offset.value() + 5)  # dispara _relayout
    faca_depois = window._result.artworks[0].cut_contour.size.width
    assert faca_depois == faca_antes + 10  # +5mm em cada lado


def test_recuo_de_seguranca_deixa_faca_menor_que_a_arte(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._offset.setValue(0)
    window.generate(blocking=True)

    art = window._result.artworks[0]
    # campo unico com sinal: valor negativo recolhe a faca para dentro (recuo)
    window._offset.setValue(-5)
    faca = window._result.artworks[0].cut_contour
    assert faca.size.width == art.size.width - 10
    assert faca.size.height == art.size.height - 10


def test_recorte_reduz_tamanho_da_arte(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._crop.setValue(0)
    window.generate(blocking=True)
    largura_cheia = window._result.artworks[0].size.width

    window._crop.setValue(3)  # corta 3mm de cada borda -> -6mm na largura
    assert window._result.artworks[0].size.width == largura_cheia - 6


def test_modos_de_visualizacao(qapp, tmp_path):
    from PySide6.QtWidgets import QGraphicsPixmapItem

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)

    def _pixmaps():
        return [it for it in window._scene.items() if isinstance(it, QGraphicsPixmapItem)]

    window._view_mode.setCurrentIndex(window._view_mode.findData("print"))
    assert len(_pixmaps()) == 2  # so impressao -> 2 artes
    window._view_mode.setCurrentIndex(window._view_mode.findData("cut"))
    assert len(_pixmaps()) == 0  # so corte -> sem imagens
    window._view_mode.setCurrentIndex(window._view_mode.findData("split"))
    assert len(_pixmaps()) == 2  # dividida desenha a impressao uma vez


def test_medida_do_arquivo_selecionado(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    window._table.setCurrentCell(0, 0)
    texto = window._sel_info.text()
    from app.presentation import units
    assert units.unit() in texto and "x" in texto  # mostra a medida do arquivo


def test_undo_de_movimento(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    piece = window._piece_items[0]
    old = piece.pos()
    piece.setSelected(True)
    window._begin_move()
    piece.setPos(piece.x() + 100, piece.y() + 30)
    window._end_move()
    assert window._undo.count() == 1
    window._undo.undo()
    assert abs(piece.pos().x() - old.x()) < 0.01
    assert abs(piece.pos().y() - old.y()) < 0.01


def test_ctrlz_grava_movimento_via_mouse(qapp, tmp_path):
    # Regressao: arrastar com o mouse uma peca NAO pre-selecionada precisa gravar
    # o movimento no historico (Ctrl+Z). O snapshot tem de ocorrer apos a selecao.
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.resize(1000, 700)
    window.show()
    window.add_paths([src])
    window.generate(blocking=True)
    window._fit_view()
    qapp.processEvents()

    piece = window._piece_items[0]
    assert not piece.isSelected()
    assert window._undo.count() == 0
    center = piece.scenePos() + QPointF(
        piece.rect().width() / 2, piece.rect().height() / 2
    )
    vp = window._view.viewport()
    start = window._view.mapFromScene(center)
    end = QPoint(start.x() + 60, start.y() + 20)

    def send(kind, pos, buttons=Qt.LeftButton):
        ev = QMouseEvent(kind, QPointF(pos), vp.mapToGlobal(pos),
                         Qt.LeftButton, buttons, Qt.NoModifier)
        qapp.sendEvent(vp, ev)

    send(QEvent.MouseButtonPress, start)
    qapp.processEvents()
    send(QEvent.MouseMove, end)
    send(QEvent.MouseButtonRelease, end, buttons=Qt.NoButton)
    qapp.processEvents()

    assert window._undo.count() == 1  # movimento gravado -> Ctrl+Z funciona


def test_agrupar_move_em_conjunto(qapp, tmp_path):
    from PySide6.QtWidgets import QGraphicsItemGroup

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    for p in window._piece_items:
        p.setSelected(True)
    window._group_selected()

    groups = [it for it in window._scene.items() if isinstance(it, QGraphicsItemGroup)]
    assert len(groups) == 1
    antes = window._piece_items[0].scenePos().x()
    groups[0].setPos(groups[0].x() + 50, groups[0].y())
    assert abs((window._piece_items[0].scenePos().x() - antes) - 50) < 0.01


def test_mover_peca_reflete_no_export(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)

    piece = window._piece_items[0]
    piece.setPos(piece.x() + 100, piece.y() + 30)
    sheets = window._effective_sheets()
    xs = [it.position.x for s in sheets for it in s.items]
    assert any(abs(x - 100) < 0.001 for x in xs)  # peca movida 100mm em x


def test_zoom_preservado_ao_mudar_parametro(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    # simula zoom do usuario
    window._view.scale(3.0, 3.0)
    antes = window._view.transform().m11()
    window._offset.setValue(window._offset.value() + 2)  # mexe na faca -> relayout
    depois = window._view.transform().m11()
    assert abs(depois - antes) < 1e-6  # zoom mantido


def test_caixa_importacao_passada_ao_pipeline(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._import_box.setCurrentIndex(window._import_box.findData("trim"))
    window.generate(blocking=True)
    # so valida que gerou sem erro com a caixa selecionada
    assert window._result is not None


def test_menu_e_toolbar_existem(qapp, tmp_path):
    from PySide6.QtWidgets import QToolBar

    window = _window(tmp_path)
    titulos = [a.text() for a in window.menuBar().actions()]
    assert "&Arquivo" in titulos and "E&xibir" in titulos
    assert len(window.findChildren(QToolBar)) >= 1


def test_parse_pages():
    from app.presentation.main_window import MainWindow

    assert MainWindow._parse_pages("", 4) == [0, 1, 2, 3]
    assert MainWindow._parse_pages("1,3", 4) == [0, 2]
    assert MainWindow._parse_pages("2-4", 5) == [1, 2, 3]
    assert MainWindow._parse_pages("9", 4) == []  # fora do intervalo


def _multi_sheet_window(qapp, tmp_path):
    import fitz

    doc = fitz.open()
    for _ in range(8):
        pg = doc.new_page(width=283.46, height=170.08)  # 100x60mm
        pg.draw_rect(pg.rect, color=(0, 0, 0), fill=(0, 0, 0))
    src = tmp_path / "multi.pdf"
    doc.save(str(src))
    doc.close()
    window = _window(tmp_path)
    window.add_paths([str(src)])
    window._width.setValue(120)
    window._height.setValue(150)
    window.generate(blocking=True)
    return window


def test_exportar_pdf_chapa_escolhida(qapp, tmp_path):
    import fitz

    window = _multi_sheet_window(qapp, tmp_path)
    assert len(window._result.sheets) >= 2
    out = tmp_path / "IMP.pdf"
    window.export_pdf(str(out), pages="1")  # so a chapa 1
    assert fitz.open(str(out)).page_count == 1


def test_exportar_dxf_chapa_escolhida(qapp, tmp_path):
    window = _multi_sheet_window(qapp, tmp_path)
    out = tmp_path / "COR.dxf"
    window.export_dxf(str(out), pages=[0])  # indice 0-based
    assert out.exists()


def test_exportar_dxf_por_chapa(qapp, tmp_path):
    import fitz

    # PDF com pecas suficientes para 2 chapas (altura pequena)
    doc = fitz.open()
    for _ in range(8):
        pg = doc.new_page(width=283.46, height=170.08)  # 100x60mm
        pg.draw_rect(pg.rect, color=(0, 0, 0), fill=(0, 0, 0))
    src = tmp_path / "multi.pdf"
    doc.save(str(src))
    doc.close()

    window = _window(tmp_path)
    window.add_paths([str(src)])
    window._width.setValue(120)   # 1 peca por linha
    window._height.setValue(150)  # 2 linhas por chapa
    window.generate(blocking=True)
    n_chapas = len(window._result.sheets)
    assert n_chapas >= 2

    base = tmp_path / "CORTE.dxf"
    window.export_dxf_per_sheet(str(base))
    gerados = list(tmp_path.glob("CORTE_*.dxf"))
    assert len(gerados) == n_chapas


def test_exportar_faca_pdf(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    out = tmp_path / "FACA.pdf"
    window.export_faca_pdf(str(out))
    assert out.exists()
    assert fitz.open(str(out)).page_count == 1


def test_dxf_mimaki_nao_leva_marcas_de_registro(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._reg_type.setCurrentIndex(window._reg_type.findData("mimaki"))
    window.generate(blocking=True)
    out = tmp_path / "CORTE_MK.dxf"
    window.export_dxf(str(out))
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    # so as facas (2 LWPOLYLINE), nenhuma linha de marca de registro Mimaki
    assert len(msp.query("LWPOLYLINE")) == 2
    assert len(msp.query("LINE")) == 0


def test_exportar_imagem_png(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    out = tmp_path / "IMG.png"
    window.export_image(str(out), dpi=72)
    assert out.exists()


def test_exportar_imagem_varias_chapas_numera(qapp, tmp_path):
    window = _multi_sheet_window(qapp, tmp_path)
    assert len(window._result.sheets) >= 2
    out = tmp_path / "IMG.png"
    window.export_image(str(out), dpi=50)
    gerados = list(tmp_path.glob("IMG_*.png"))
    assert len(gerados) >= 2


def test_exportar_imagem_persiste_dpi(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    window.export_image(str(tmp_path / "a.png"), dpi=222)
    assert SettingsStore(tmp_path / "config.json").load().export_dpi == 222


def test_excluir_peca_selecionada(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    assert sum(s.item_count for s in window._result.sheets) == 2
    window._piece_items[0].setSelected(True)
    window._delete_selected()
    assert sum(s.item_count for s in window._result.sheets) == 1


def test_resetar_restaura_arranjo(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    window._piece_items[0].setSelected(True)
    window._delete_selected()
    assert sum(s.item_count for s in window._result.sheets) == 1
    window._reset_arrangement()
    assert sum(s.item_count for s in window._result.sheets) == 2


def test_selecionar_tudo(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    window._select_all()
    selecionadas = [p for p in window._piece_items if p.isSelected()]
    assert len(selecionadas) == 2


def test_toggle_reguas(qapp, tmp_path):
    window = _window(tmp_path)
    assert not window._h_ruler.isHidden()  # padrao: reguas ligadas
    window._show_rulers.setChecked(False)
    assert window._h_ruler.isHidden()
    assert window._v_ruler.isHidden()
    window._show_rulers.setChecked(True)
    assert not window._h_ruler.isHidden()


def _n_page_pdf(tmp_path, n, w=120.0, h=120.0, name="multi"):
    doc = fitz.open()
    for _ in range(n):
        pg = doc.new_page(width=w, height=h)
        pg.draw_rect(pg.rect, color=(0, 0, 0), fill=(0, 0, 0))
    src = tmp_path / f"{name}.pdf"
    doc.save(str(src))
    doc.close()
    return str(src)


def test_nudge_move_pecas_com_setas(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    piece = window._piece_items[0]
    piece.setSelected(True)
    x0, y0 = piece.pos().x(), piece.pos().y()
    window._nudge(5.0, -3.0)
    assert abs(piece.pos().x() - (x0 + 5.0)) < 0.01
    assert abs(piece.pos().y() - (y0 - 3.0)) < 0.01
    assert window._undo.count() == 1
    window._undo.undo()
    assert abs(piece.pos().x() - x0) < 0.01


def test_alinhar_a_esquerda(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    a, b = window._piece_items[0], window._piece_items[1]
    b.setPos(b.x() + 80, b.y() + 40)
    a.setSelected(True)
    b.setSelected(True)
    window._align("left")
    assert abs(a.sceneBoundingRect().left() - b.sceneBoundingRect().left()) < 0.1


def test_distribuir_horizontal_iguala_espacos(qapp, tmp_path):
    src = _n_page_pdf(tmp_path, 3)
    window = _window(tmp_path)
    window.add_paths([src])
    window._width.setValue(3000)  # tudo em uma linha
    window.generate(blocking=True)
    ps = window._piece_items[:3]
    ps[0].setPos(0, 0)
    ps[1].setPos(20, 0)
    ps[2].setPos(400, 0)
    for p in ps:
        p.setSelected(True)
    window._distribute("h")
    rects = sorted((p.sceneBoundingRect() for p in ps), key=lambda r: r.left())
    gap1 = rects[1].left() - rects[0].right()
    gap2 = rects[2].left() - rects[1].right()
    assert abs(gap1 - gap2) < 0.5


def test_duplicar_cria_copia(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    n0 = sum(s.item_count for s in window._result.sheets)
    window._piece_items[0].setSelected(True)
    window._duplicate_selected()
    assert sum(s.item_count for s in window._result.sheets) == n0 + 1


def test_step_repeat_grade_2x2(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._width.setValue(3000)
    window._height.setValue(3000)
    window.generate(blocking=True)
    n0 = sum(s.item_count for s in window._result.sheets)
    window._piece_items[0].setSelected(True)
    window._step_repeat(2, 2, 5.0)  # 2x2 = 3 copias novas
    assert sum(s.item_count for s in window._result.sheets) == n0 + 3


def test_guia_arrastada_cria_seleciona_move_e_exclui(qapp, tmp_path):
    from PySide6.QtCore import QPointF
    from app.presentation.main_window import GuideItem

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)

    window._on_guide_dropped(True, 50.0, inside=True)  # guia horizontal em y=50
    guides = [it for it in window._scene.items() if isinstance(it, GuideItem)]
    assert len(guides) == 1
    g = guides[0]
    assert g.flags() & GuideItem.GraphicsItemFlag.ItemIsSelectable
    assert g.flags() & GuideItem.GraphicsItemFlag.ItemIsMovable

    g.setPos(QPointF(0.0, 10.0))  # move 10mm -> valor guardado vira 60
    assert abs(window._guides[0][1] - 60.0) < 1e-6

    g.setSelected(True)
    window._delete_selected()
    assert not [it for it in window._scene.items() if isinstance(it, GuideItem)]
    assert window._guides == []


def test_guia_fora_do_canvas_nao_cria(qapp, tmp_path):
    from app.presentation.main_window import GuideItem

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    window._on_guide_dropped(False, 30.0, inside=False)  # soltou fora -> ignora
    assert not [it for it in window._scene.items() if isinstance(it, GuideItem)]
    assert window._guides == []


def test_aba_objeto_lista_seleciona_e_ordena(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)

    # a lista de objetos reflete as pecas
    assert window._obj_list.count() == 2

    # selecionar pela lista marca a peca no canvas
    window._obj_list.item(0).setSelected(True)
    assert window._obj_rows[0].isSelected()

    # z-order: trazer a peca 0 para frente fica acima da peca 1
    window._scene.clearSelection()
    window._piece_items[0].setSelected(True)
    window._bring_to_front()
    assert window._piece_items[0].zValue() > window._piece_items[1].zValue()

    # enviar para tras inverte
    window._send_to_back()
    assert window._piece_items[0].zValue() < window._piece_items[1].zValue()


def test_faca_por_arquivo_so_afeta_aquele_arquivo(qapp, tmp_path):
    from tests import synth_images as si

    pdf = _two_page_pdf(tmp_path)
    img = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([pdf, img])
    window.generate(blocking=True)

    def first_by_path():
        out = {}
        for art in window._result.artworks:
            out.setdefault(window._path_of(art.id), art)
        return out

    antes = first_by_path()
    img_w0 = antes[img].cut_contour.size.width
    pdf_art0 = antes[pdf]
    pdf_w0 = pdf_art0.cut_contour.size.width

    # override SO na imagem: +5mm de sangria
    ov = dict(window._params_for(img))
    ov["auto_offset"] = 5.0
    window._file_overrides[img] = ov
    window._relayout()

    depois = first_by_path()
    assert depois[img].cut_contour.size.width > img_w0   # a imagem cresceu
    assert abs(depois[pdf].cut_contour.size.width - pdf_w0) < 0.01  # PDF intacto


def test_arrastar_arquivo_da_biblioteca_para_producao(qapp, tmp_path):
    from PySide6.QtCore import QPointF

    a = _two_page_pdf(tmp_path)
    b = _n_page_pdf(tmp_path, 1, name="extra")
    window = _window(tmp_path)
    window.add_paths([a])
    window.generate(blocking=True)
    n0 = sum(s.item_count for s in window._result.sheets)
    assert n0 == 2

    # B foi esquecido: entra na biblioteca depois de gerar, ainda fora da producao
    window.add_paths([b])
    assert not any(window._path_of(art.id) == b for art in window._result.artworks)

    # arrasta B para a area de trabalho (drop na chapa 0)
    window._add_file_to_production(b, QPointF(10.0, 10.0))
    assert any(window._path_of(art.id) == b for art in window._result.artworks)
    assert sum(s.item_count for s in window._result.sheets) == n0 + 1


def test_faca_pdf_pelo_contorno_nao_e_retangulo(qapp, tmp_path):
    # PDF com um circulo preenchido sobre fundo branco
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)  # ~70mm
    page.draw_circle(fitz.Point(100, 100), 90, color=(0, 0.5, 0), fill=(0, 0.5, 0))
    src = tmp_path / "circulo.pdf"
    doc.save(str(src))
    doc.close()

    window = _window(tmp_path)
    window.add_paths([str(src)])
    # modo retangulo (padrao): faca e um retangulo (4 cantos)
    window.generate(blocking=True)
    rect_pts = len(window._result.artworks[0].cut_contour.points)
    assert rect_pts <= 5

    # modo "pelo contorno": rasteriza e corta no formato do circulo
    window._faca_mode.setCurrentIndex(window._faca_mode.findData("contour"))
    contour_pts = len(window._result.artworks[0].cut_contour.points)
    assert contour_pts > 8  # circulo -> muitos pontos, nao um retangulo


def test_snap_axis_encaixa_na_borda():
    from app.presentation.main_window import SNAP_THRESHOLD_MM, PieceItem

    th = SNAP_THRESHOLD_MM
    # borda esquerda 100.5 perto da linha 100 -> encaixa em 100
    assert abs(PieceItem._snap_axis(100.5, 10.0, [100.0], th) - 100.0) < 1e-9
    # borda direita (110.5) perto da linha 110 -> left vira 100.0
    assert abs(PieceItem._snap_axis(100.5, 10.0, [110.0], th) - 100.0) < 1e-9
    # nada dentro do limiar -> nao mexe
    assert PieceItem._snap_axis(100.0, 10.0, [50.0], th) == 100.0


def test_snap_so_age_durante_arraste(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    a, b = window._piece_items[0], window._piece_items[1]
    # alinha 'a' a 1mm da borda esquerda de 'b': fora de arraste nao encaixa
    target = b.sceneBoundingRect().left() + 1.0
    window._snap.dragging = False
    a.setPos(500.0, a.y())
    a.setPos(target, a.y())
    assert abs(a.sceneBoundingRect().left() - target) < 0.01
    # durante o arraste, encaixa na borda de 'b'
    window._snap.dragging = True
    a.setPos(500.0, a.y())  # afasta antes (setPos para a mesma pos nao dispara)
    a.setPos(target, a.y())
    assert abs(a.sceneBoundingRect().left() - b.sceneBoundingRect().left()) < 0.01
    window._snap.dragging = False


def test_snap_persiste(qapp, tmp_path):
    window = _window(tmp_path)
    window._snap_check.setChecked(False)
    window._save_settings()
    assert SettingsStore(tmp_path / "config.json").load().snap_enabled is False


def test_persiste_configuracoes(qapp, tmp_path):
    window = _window(tmp_path)
    window._width.setValue(1500)
    window._height.setValue(1000)
    window._spacing.setValue(8)
    window._offset.setValue(2)
    window._save_settings()

    recarregado = SettingsStore(tmp_path / "config.json").load()
    assert recarregado.material_width == 1500
    assert recarregado.material_height == 1000
    assert recarregado.spacing == 8
    assert recarregado.offset == 2
    assert recarregado.safety_inset == 0  # campo unico zera o antigo recuo


# ---- projeto (.printnest) ----
def _window_cfg(tmp_path, name):
    """Janela com um diretorio de config proprio (config.json isolado por 'name')."""
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    store = SettingsStore(folder / "config.json")
    settings = store.load_or_create()
    pipeline = RunProductionPipelineUseCase(
        ImportPdfUseCase(PyMuPdfImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(cache_dir=folder / "imgcache")),
    )
    return MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PyMuPdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PyMuPdfPageRenderer(),
        store,
        settings,
    )


def test_salvar_e_abrir_projeto_restaura_arquivos_e_parametros(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w1 = _window_cfg(tmp_path, "w1")
    w1.add_paths([src])
    w1._table.cellWidget(0, 1).setValue(4)
    w1._width.setValue(1234)
    w1._offset.setValue(7)
    proj = tmp_path / "trabalho.printnest"
    assert w1.save_project(str(proj)) is True
    assert proj.exists()

    w2 = _window_cfg(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    assert w2._paths == [src]
    assert w2._table.cellWidget(0, 1).value() == 4
    assert w2._width.value() == 1234
    assert w2._offset.value() == 7
    # REGRA 1: abrir o projeto NAO gera producao automaticamente
    assert w2._loaded is False
    assert w2._result is None


def test_abrir_projeto_com_arquivo_ausente_nao_quebra(qapp, tmp_path):
    from app.application.project_io import ProjectDocument, ProjectFile, ProjectStore

    proj = tmp_path / "p.printnest"
    ProjectStore().save(
        proj,
        ProjectDocument(
            files=[ProjectFile(str(tmp_path / "sumiu.pdf"), quantity=2)],
            settings={},
        ),
    )
    w = _window_cfg(tmp_path, "w")
    assert w.open_project(str(proj)) is True  # REGRA 2: nao impede a abertura
    assert w._table.rowCount() == 1
    assert w._paths == [str(tmp_path / "sumiu.pdf")]
    assert "⚠" in w._table.item(0, 0).text()  # linha marcada como ausente


def test_reabrir_ultimo_projeto_ao_iniciar(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w1 = _window_cfg(tmp_path, "shared")
    w1.add_paths([src])
    proj = tmp_path / "ultimo.printnest"
    w1.save_project(str(proj))

    # nova janela com a MESMA config -> reabre o ultimo projeto sozinha
    w2 = _window_cfg(tmp_path, "shared")
    assert w2._paths == [src]
    assert w2._project_path == str(proj)


def test_novo_projeto_limpa_a_lista(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w")
    w.add_paths([src])
    w.generate(blocking=True)
    assert w._loaded is True

    w.new_project()
    assert w._paths == []
    assert w._table.rowCount() == 0
    assert w._result is None
    assert w._loaded is False


# ---- importacao de imagens + faca automatica (V1.4) ----
from tests import synth_images as si  # noqa: E402


def test_fluxo_imagem_png_gera_faca_e_exporta(qapp, tmp_path):
    img = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([img])
    window.generate(blocking=True)

    assert window._result is not None
    art = window._result.artworks[0]
    from app.domain.model.image_artwork import ImageArtwork
    assert isinstance(art, ImageArtwork)
    assert art.has_cut  # faca automatica (contorno detectado)

    pdf_out = tmp_path / "IMG_IMPRESSAO.pdf"
    window.export_pdf(str(pdf_out))
    assert pdf_out.exists()

    dxf_out = tmp_path / "IMG_CORTE.dxf"
    window.export_dxf(str(dxf_out))
    assert dxf_out.exists()
    doc = ezdxf.readfile(str(dxf_out))
    assert len(doc.modelspace().query("LWPOLYLINE")) >= 1  # contorno irregular

    png_out = tmp_path / "IMG_OUT.png"
    window.export_image(str(png_out), dpi=72)
    assert png_out.exists()


def test_fluxo_imagem_webp(qapp, tmp_path):
    img = si.webp_opaque(tmp_path)
    window = _window(tmp_path)
    window.add_paths([img])
    window.generate(blocking=True)
    assert window._result is not None
    # render usa o PNG em cache (webp nao abre no fitz), mas a quantidade
    # continua mapeada pelo caminho original do usuario
    art = window._result.artworks[0]
    assert window._origins[art.id] == img
    pdf_out = tmp_path / "webp.pdf"
    window.export_pdf(str(pdf_out))
    assert pdf_out.exists()


def test_offset_externo_de_imagem_aumenta_a_faca(qapp, tmp_path):
    img = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([img])
    window._auto_offset.setValue(0)
    window.generate(blocking=True)
    antes = window._result.artworks[0].cut_contour.size.width

    window._auto_offset.setValue(5)  # campo unico: +5 = sangria para fora
    depois = window._result.artworks[0].cut_contour.size.width
    assert depois > antes


def test_quantidade_de_imagem_multiplica(qapp, tmp_path):
    img = si.jpg_white_square(tmp_path)
    window = _window(tmp_path)
    window.add_paths([img])
    window.generate(blocking=True)
    assert sum(s.item_count for s in window._result.sheets) == 1
    window._table.cellWidget(0, 1).setValue(5)
    assert sum(s.item_count for s in window._result.sheets) == 5


def test_imagem_com_caixa_apara_nao_quebra(qapp, tmp_path):
    # Regressao: imagem + "Cortar para = Apara" fazia render_png acessar page.xref
    # de um documento nao-PDF -> falha nativa (o programa fechava).
    img = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window._import_box.setCurrentIndex(window._import_box.findData("trim"))
    window.add_paths([img])
    window.generate(blocking=True)
    assert window._result is not None
    assert sum(s.item_count for s in window._result.sheets) == 1


def test_projeto_com_imagem_salva_e_reabre(qapp, tmp_path):
    img = si.jpg_white_square(tmp_path)
    w1 = _window_cfg(tmp_path, "wi1")
    w1.add_paths([img])
    proj = tmp_path / "img.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window_cfg(tmp_path, "wi2")
    assert w2.open_project(str(proj)) is True
    assert w2._paths == [img]
