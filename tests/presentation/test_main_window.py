import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
import fitz  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    RunProductionPipelineUseCase,
)
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pymupdf_print_exporter import PyMuPdfPrintExporter  # noqa: E402
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
    pipeline = RunProductionPipelineUseCase(ImportPdfUseCase(PyMuPdfImporter()))
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
    window._safety.setValue(0)
    window.generate(blocking=True)

    art = window._result.artworks[0]
    # com recuo 5 e offset 0, a faca fica menor que a arte
    window._safety.setValue(5)
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
    assert "mm" in texto and "x" in texto  # mostra a medida do arquivo


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
    window._safety.setValue(1)
    window._save_settings()

    recarregado = SettingsStore(tmp_path / "config.json").load()
    assert recarregado.material_width == 1500
    assert recarregado.material_height == 1000
    assert recarregado.spacing == 8
    assert recarregado.offset == 2
    assert recarregado.safety_inset == 1


# ---- projeto (.printnest) ----
def _window_cfg(tmp_path, name):
    """Janela com um diretorio de config proprio (config.json isolado por 'name')."""
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    store = SettingsStore(folder / "config.json")
    settings = store.load_or_create()
    pipeline = RunProductionPipelineUseCase(ImportPdfUseCase(PyMuPdfImporter()))
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
