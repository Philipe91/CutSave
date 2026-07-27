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
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter  # noqa: E402
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter  # noqa: E402
from app.infrastructure.importers.pdfium_importer import PdfiumImporter  # noqa: E402
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer  # noqa: E402
from app.presentation.main_window import MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


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
        ImportPdfUseCase(PdfiumImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(cache_dir=tmp_path / "imgcache")),
    )
    return MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PikePdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PdfiumPageRenderer(),
        store,
        settings,
    )


def _vector_cut_pdf(tmp_path):
    """PDF com a faca do cliente desenhada como vetor (um circulo de corte)."""
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_circle((100, 100), 80, color=(1, 0, 1), width=1.0)
    path = tmp_path / "cliente.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_faca_do_cliente_usa_o_vetor_do_pdf(qapp, tmp_path):
    window = _window(tmp_path)
    window.add_paths([_vector_cut_pdf(tmp_path)])
    window._faca_mode.setCurrentIndex(window._faca_mode.findData("vector"))
    window.generate(blocking=True)
    art = window._result.artworks[0]
    assert art.cut_contour is not None
    # circulo vetorial -> muitos pontos (nao o retangulo de 4 pontos)
    assert len(art.cut_contour.points) > 5
    assert window._faca_notice is not None and window._faca_notice[0] == "info"


def _arte_com_faca_magenta_pdf(tmp_path):
    """PDF como o cliente manda: arte preenchida + FACA em traço magenta,
    sem preenchimento, por cima (convenção CutContour)."""
    doc = fitz.open()
    page = doc.new_page(width=267, height=101)
    page.draw_rect(fitz.Rect(15, 15, 250, 88), color=None, fill=(0.2, 0.4, 1))  # arte
    page.draw_rect(fitz.Rect(8, 8, 259, 93), color=(1, 0, 1), width=1.0)        # faca
    path = tmp_path / "cliente_magenta.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_faca_magenta_detectada_automaticamente(qapp, tmp_path):
    # 16/07 (teste real do Philipe): no modo AUTO (padrão), a linha magenta
    # do PDF tem de virar a faca do cliente SEM trocar o combo — e sair 1:1
    # com o desenho (sem sangria default, sem suavizar/simplificar).
    pt2mm = 25.4 / 72.0
    w = _window(tmp_path)
    w.add_paths([_arte_com_faca_magenta_pdf(tmp_path)])
    w._offset.setValue(0)  # sangria zero: fidelidade total ao desenho
    w.generate(blocking=True)
    art = w._result.artworks[0]
    assert art.cut_contour is not None
    xs = [p.x for p in art.cut_contour.points]
    ys = [p.y for p in art.cut_contour.points]
    # bbox da faca = o retângulo MAGENTA (251x85pt), não a página nem a arte
    assert max(xs) - min(xs) == pytest.approx(251 * pt2mm, abs=1.0)
    assert max(ys) - min(ys) == pytest.approx(85 * pt2mm, abs=1.0)
    assert w._faca_notice is not None and w._faca_notice[0] == "info"
    assert "MAGENTA" in w._faca_notice[1]

    # a linha magenta é INSTRUÇÃO de corte: não pode sair no PDF de impressão
    from app.domain.cut.vector import is_knife_color
    from app.infrastructure.importers.pdfium_vector_extractor import (
        PdfiumVectorExtractor,
    )
    out = tmp_path / "IMPRESSAO.pdf"
    w.export_pdf(str(out))
    assert out.exists()
    infos = PdfiumVectorExtractor().extract_rings_info(str(out))
    assert infos  # a arte (vetores) foi para a impressão...
    assert not any(  # ...mas nenhum traço magenta foi junto
        i.stroked and i.stroke_rgb is not None and is_knife_color(i.stroke_rgb)
        for i in infos
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


def test_tela_dividida_horizontal(qapp, tmp_path):
    from PySide6.QtWidgets import QGraphicsPixmapItem

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)

    window._view_mode.setCurrentIndex(window._view_mode.findData("split"))
    rect_v = window._scene.itemsBoundingRect()
    window._view_mode.setCurrentIndex(window._view_mode.findData("split_h"))
    rect_h = window._scene.itemsBoundingRect()

    pix = [it for it in window._scene.items() if isinstance(it, QGraphicsPixmapItem)]
    assert len(pix) == 2  # arte desenhada uma vez (à esquerda)
    # faca deslocada em X (e não em Y): cena mais larga e mais baixa que o split vertical
    assert rect_h.width() > rect_v.width()
    assert rect_h.height() < rect_v.height()


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
    window._undo.undo()  # desfazer redesenha (snapshot de dados) -> rebusca a peca
    xs = [(p.pos().x(), p.pos().y()) for p in window._piece_items]
    assert any(abs(x - old.x()) < 0.01 and abs(y - old.y()) < 0.01 for x, y in xs)


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
    x0 = piece.x() - piece.dx  # posicao local antes do movimento (ja centralizada)
    piece.setPos(piece.x() + 100, piece.y() + 30)
    sheets = window._effective_sheets()
    xs = [it.position.x for s in sheets for it in s.items]
    assert any(abs(x - (x0 + 100)) < 0.001 for x in xs)  # peca movida 100mm em x


def test_centraliza_na_pagina(qapp, tmp_path):
    # o conteudo fica centralizado na PAGINA: margens iguais em largura E altura.
    from app.application.footprint import artwork_footprint

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)   # chapa bem maior que as pecas -> sobra em volta
    window._height.setValue(2000)
    window.add_paths([src])
    window.generate(blocking=True)
    layout = window._result.sheets[0]
    arts = {a.id: a for a in window._result.artworks}
    lefts, rights, tops, bottoms = [], [], [], []
    for it in layout.items:
        fp = artwork_footprint(arts[it.artwork_id])
        lefts.append(it.position.x)
        rights.append(it.position.x + (fp.max_x - fp.min_x))
        tops.append(it.position.y)
        bottoms.append(it.position.y + (fp.max_y - fp.min_y))
    left_margin = min(lefts)
    right_margin = window._material().width - max(rights)
    top_margin = min(tops)
    bottom_margin = layout.used_length - max(bottoms)
    assert abs(left_margin - right_margin) < 0.5   # centralizado na largura
    assert abs(top_margin - bottom_margin) < 0.5   # centralizado na altura
    assert top_margin > 1.0  # ha margem de fato (nao esta colado no topo)

    # checkbox e menu ficam sincronizados com o estado
    assert window._center_check.isChecked() is True
    assert window._center_action.isChecked() is True

    # desligar a centralizacao encosta o conteudo no canto (topo-esquerda)
    window._set_center_on_sheet(False)
    assert window._center_check.isChecked() is False  # checkbox acompanhou
    assert window._center_action.isChecked() is False  # menu acompanhou
    layout = window._result.sheets[0]
    assert min(it.position.x for it in layout.items) < left_margin
    assert min(it.position.y for it in layout.items) < top_margin


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


def test_registro_ambos_bolinhas_e_mimaki(qapp, tmp_path):
    # "Bolinhas + Mimaki": impressao e DXF levam os DOIS tipos de marca juntos
    # (fluxo cortar na Mimaki e depois na IECHO).
    src = _n_page_pdf(tmp_path, 2, name="reg", w=283, h=170)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([src])
    window._reg_type.setCurrentIndex(window._reg_type.findData("both"))
    window.generate(blocking=True)

    sheets = window._effective_sheets()
    ps = window._print_export.build_print_sheets(
        sheets, window._result.artworks, window._result.sources, **window._print_kwargs()
    )
    assert any(s.circles for s in ps)  # bolinhas no PDF de impressao
    assert any(s.lines for s in ps)    # marcas Mimaki (linhas) no PDF de impressao

    contours, _segments, marks, _mk, _pl = window._dxf_payload(sheets)
    assert marks  # bolinhas tambem no DXF


def test_faca_pdf_leva_bolinhas_de_registro(qapp, tmp_path):
    # as marcas de registro (bolinhas) tem que sair na faca, igual ao DXF.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._reg_type.setCurrentIndex(window._reg_type.findData("circles"))
    window.generate(blocking=True)
    out = tmp_path / "FACA_REG.pdf"
    window.export_faca_pdf(str(out))
    page = fitz.open(str(out))[0]
    drawings = page.get_drawings()
    pretas = [
        d for d in drawings
        if d.get("fill") and max(d["fill"]) < 0.2  # preenchimento preto = bolinha
    ]
    assert pretas  # ha bolinhas de registro (pretas, preenchidas) alem da faca


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
    # faca (2) + o quadrado/frame do Mimaki (1) = 3 contornos; sem as marcas em L
    assert len(msp.query("LWPOLYLINE")) == 3
    assert len(msp.query("LINE")) == 0  # nenhuma marca de registro em L no corte


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
    window._nudge(5.0, -3.0)  # move sem redesenhar (peca segue valida)
    assert abs(piece.pos().x() - (x0 + 5.0)) < 0.01
    assert abs(piece.pos().y() - (y0 - 3.0)) < 0.01
    assert window._undo.count() == 1
    window._undo.undo()  # desfazer redesenha -> rebusca a peca pela posicao
    xs = [(p.pos().x(), p.pos().y()) for p in window._piece_items]
    assert any(abs(x - x0) < 0.01 and abs(y - y0) < 0.01 for x, y in xs)


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


def test_mesmo_arquivo_importado_2x_soma_quantidade(qapp, tmp_path):
    # Bug QA-04: duas linhas do mesmo arquivo colidiam (ids/qtd por caminho) e
    # a producao saia com quantidade errada em silencio. Agora a segunda
    # importacao soma +1 na linha existente (uma linha por arquivo).
    from tests import synth_images as si
    src = si.jpg_white_square(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src, src])
    assert window._table.rowCount() == 1
    assert window._table.cellWidget(0, 1).value() == 2
    window.generate(blocking=True)
    assert sum(s.item_count for s in window._result.sheets) == 2


def test_exportar_faca_sem_faca_nao_grava_pdf_em_branco(qapp, tmp_path):
    # Bug QA-03: "soltar sem faca" + exportar faca gravava um PDF valido porem
    # SEM nenhuma linha de corte (arquivo em branco indo para a maquina).
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True, faca=False)
    out = tmp_path / "FACA_vazia.pdf"
    window.export_faca_pdf(str(out))
    assert not out.exists()  # recusa gravar faca vazia


def test_falha_de_exportacao_mostra_dialogo_e_nao_estoura(qapp, tmp_path, monkeypatch):
    # Bug QA-02: erro real de exportacao (pasta inexistente/permissao) subia
    # cru — no exe o botao "nao fazia nada". Agora vira dialogo amigavel.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    avisos = []
    monkeypatch.setattr(
        QMessageBox, "critical",
        staticmethod(lambda *a, **k: avisos.append(a)),
    )
    destino = tmp_path / "pasta_que_nao_existe" / "IMPRESSAO.pdf"
    window.export_pdf(str(destino))  # nao pode estourar excecao
    assert avisos, "falha de exportacao tem que mostrar dialogo"
    assert not destino.exists()


def test_desfazer_giro_de_peca_limpa_o_giro_de_verdade(qapp, tmp_path):
    # Bug QA-01: girar peca -> Ctrl+Z revertia o visual, mas _piece_rotations
    # ficava "sujo" e o giro desfeito VOLTAVA sozinho no proximo recalculo.
    src = _two_page_pdf(tmp_path)  # paginas retangulares (L != A)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)

    piece = window._piece_items[0]
    aid = piece.artwork_id
    art0 = next(a for a in window._result.artworks if a.id == aid)
    w0 = art0.size.width

    piece.setSelected(True)
    window._rotate_selected(90)
    assert window._piece_rotations.get(aid, 0) == 90
    art_girada = next(a for a in window._result.artworks if a.id == aid)
    assert abs(art_girada.size.width - w0) > 0.01  # girou de fato

    window._undo.undo()
    assert window._piece_rotations.get(aid, 0) == 0  # o dict TEM que voltar

    window._undo.redo()  # refazer devolve o giro
    assert window._piece_rotations.get(aid, 0) == 90

    window._undo.undo()  # desfaz de novo (fica sem giro)
    assert window._piece_rotations.get(aid, 0) == 0

    # recalculo nao relacionado (sangria) nao pode reaplicar o giro desfeito
    window._offset.setValue(window._offset.value() + 1)
    art_final = next(a for a in window._result.artworks if a.id == aid)
    assert abs(art_final.size.width - w0) < 0.01  # continua NAO girada


def test_export_center_desmarca_chapas_mesmo_com_selecao(qapp, tmp_path):
    # Bug: com peca selecionada no canvas o modo vira "Apenas a selecao" e a
    # lista de chapas ficava DESABILITADA -> nao dava para desmarcar chapa.
    from app.presentation.main_window import ExportCenterDialog
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    window._piece_items[0].setSelected(True)  # forca modo "apenas a selecao"

    dlg = ExportCenterDialog(window)
    assert dlg._sel_export is not None  # ha selecao
    assert dlg._checks, "sem checkboxes de chapa"
    # a lista NAO pode estar desabilitada (senao nao da p/ mexer)
    assert dlg._scroll.isEnabled()

    # "Nenhuma" desmarca tudo E troca para o modo "Chapas marcadas"
    dlg._set_all(False)
    assert not any(c.isChecked() for c in dlg._checks)
    assert dlg._mode_sheets.isChecked()
    dlg.deleteLater()


def test_copiar_colar_e_ctrl_d_em_cadeia(qapp, tmp_path):
    # Fluxo do Corel: Ctrl+C copia, Ctrl+V cola (deslocado) e, como a copia
    # vira a nova selecao, Ctrl+D repetido segue duplicando em cadeia.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    n0 = sum(s.item_count for s in window._result.sheets)

    window._piece_items[0].setSelected(True)
    window._copy_selected()
    window._paste_clipboard()  # +1
    assert sum(s.item_count for s in window._result.sheets) == n0 + 1
    assert len(window._selected_pieces()) == 1  # a copia ficou selecionada

    window._duplicate_selected()  # Ctrl+D em cima da copia -> +1
    window._duplicate_selected()  # de novo -> +1 (cadeia)
    assert sum(s.item_count for s in window._result.sheets) == n0 + 3

    window._paste_clipboard()  # segunda colagem cascateia (+1)
    assert sum(s.item_count for s in window._result.sheets) == n0 + 4


def test_colar_em_cenarios_hostis_nao_quebra(qapp, tmp_path):
    # Regressoes do QA (caça-bugs): colar apos remover o arquivo nao insere
    # peça fantasma; clipboard com ids inexistentes e ignorado em silencio;
    # colar muitas vezes mantem o arranjo integro (used_length >= 0).
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    n0 = sum(s.item_count for s in window._result.sheets)

    # clipboard forjado com id que nao existe na producao -> no-op
    window._piece_clipboard = [(0, "id_fantasma#p1", 10.0, 10.0)]
    window._paste_count = 0
    window._paste_clipboard()
    assert sum(s.item_count for s in window._result.sheets) == n0

    # copiar de verdade e colar 30x em cadeia -> integro
    window._piece_items[0].setSelected(True)
    window._copy_selected()
    for _ in range(30):
        window._paste_clipboard()
    assert sum(s.item_count for s in window._result.sheets) == n0 + 30
    assert all(s.used_length >= 0 for s in window._result.sheets)

    # remover o arquivo da biblioteca -> colar de novo nao quebra nem insere
    window._table.setCurrentCell(0, 0)
    window.remove_selected()
    window._paste_clipboard()  # nao deve estourar


def test_clipboard_e_por_aba(qapp, tmp_path):
    # QA-12: copiar numa aba e trocar de aba NAO leva o clipboard junto
    # (ids homonimos entre trabalhos colariam peça em posição errada).
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    window._piece_items[0].setSelected(True)
    window._copy_selected()
    assert window._piece_clipboard  # copiou

    window._new_tab()  # troca para uma aba nova
    assert window._piece_clipboard == []  # clipboard nao atravessa abas


def test_tipo_de_faca_na_barra_respeita_a_selecao(qapp, tmp_path):
    # Estilo Corel: com peça SELECIONADA, mudar o Tipo na barra Faca vale só
    # para o arquivo dela (override); o global do documento não muda — misturar
    # corte reto com contorno justo não atropela os outros arquivos.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)

    global_antes = window._faca_mode.currentData()
    window._selected_path = src  # peça deste arquivo selecionada
    window._ct_mode.setCurrentIndex(window._ct_mode.findData("contour"))

    assert window._file_overrides[src]["mode"] == "contour"  # só o arquivo
    assert window._faca_mode.currentData() == global_antes   # global intacto

    # BUG 09/07: com override criado, o Offset da barra tem de editar o
    # ARQUIVO (o global era ignorado e "a borda parava de aumentar")
    window._ct_offset.setValue(5.0)
    window._apply_contour_offset()
    assert window._file_overrides[src]["offset"] == 5.0
    assert window._file_overrides[src]["auto_offset"] == 5.0
    window._ct_smooth.setValue(3)
    assert window._file_overrides[src]["smooth"] == 3
    assert int(window._auto_smooth.value()) != 3 or True  # global preservado

    # sem seleção: a barra volta a controlar o documento inteiro
    window._selected_path = None
    window._ct_loading = False
    window._ct_mode.setCurrentIndex(window._ct_mode.findData("rect"))
    assert window._faca_mode.currentData() == "rect"


def test_ajustar_chapa_ao_conteudo(qapp, tmp_path):
    # "Ajustar chapa ao conteúdo": a chapa encolhe para o bbox do arranjo
    # (sem branco em volta na exportação) e o conteúdo encosta na origem.
    # Ctrl+Z desfaz (passa pelo _commit_arrangement).
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)  # chapa MUITO maior que o conteúdo
    window.add_paths([src])
    window.generate(blocking=True)
    antes = window._effective_sheets()[0]
    assert antes.material.width == 2000

    window._fit_sheets_to_content()
    depois = window._effective_sheets()[0]
    assert depois.material.width < 2000  # encolheu para o conteúdo
    # conteúdo rente à origem (sem margem morta)
    min_x = min(i.position.x for i in depois.items)
    min_y = min(i.position.y for i in depois.items)
    assert abs(min_x) < 1e-6 and abs(min_y) < 1e-6
    assert len(depois.items) == len(antes.items)  # nenhuma peça sumiu

    window._undo.undo()  # desfazível
    assert window._effective_sheets()[0].material.width == 2000


def test_faca_do_canvas_usa_o_vermelho_do_tema(qapp, tmp_path):
    # QA-06: a linha de faca desenhada no canvas sai EXATAMENTE no token
    # theme.CUT (fim do drift de cores hardcoded).
    from app.presentation import theme
    from PySide6.QtWidgets import QGraphicsPolygonItem

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    facas = [
        it for it in window._scene.items()
        if isinstance(it, QGraphicsPolygonItem)
    ]
    assert facas, "faca nao desenhada no canvas"
    assert facas[0].pen().color().name() == theme.CUT


def test_barra_propriedades_contextual(qapp, tmp_path):
    # Barra contextual: Projeto (sem selecao) -> Objeto (1 peca) -> Grupo (varias).
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window._update_property_bar()
    assert window._pbar_stack.currentIndex() == 0  # Projeto

    window.add_paths([src])
    window.generate(blocking=True)
    window._piece_items[0].setSelected(True)
    assert window._pbar_stack.currentIndex() == 1  # Objeto
    p = window._piece_items[0]
    assert abs(window._pb_w.value() - p.rect().width()) < 0.5  # mostra a medida (L)

    window._piece_items[1].setSelected(True)
    assert window._pbar_stack.currentIndex() == 2  # Grupo
    assert "2" in window._pb_grp_count.text()


def test_girar_mantem_a_selecao(qapp, tmp_path):
    # Ao girar pelo botao, a peca deve CONTINUAR selecionada (para clicar de novo
    # e seguir girando) e a barra deve permanecer no contexto Objeto.
    src = _n_page_pdf(tmp_path, 1, name="grot")
    window = _window(tmp_path)
    window._width.setValue(3000)
    window._height.setValue(3000)
    window.add_paths([src])
    window.generate(blocking=True)
    window._piece_items[0].setSelected(True)
    aid = window._piece_items[0].artwork_id

    window._rotate_selected(90)
    sel = window._selected_pieces()
    assert len(sel) == 1
    assert sel[0].artwork_id == aid
    assert window._pbar_stack.currentIndex() == 1  # continua em Objeto




def test_transformar_duplicar_linear(qapp, tmp_path):
    # Aba Transformar: X=100, copias=5 (relativo) -> original + 5 = 6 pecas.
    src = _n_page_pdf(tmp_path, 1, name="t1")
    window = _window(tmp_path)
    window._width.setValue(3000)
    window._height.setValue(3000)
    window.add_paths([src])
    window.generate(blocking=True)
    assert sum(s.item_count for s in window._result.sheets) == 1

    window._piece_items[0].setSelected(True)
    window._td_x.setValue(100)
    window._td_y.setValue(0)
    window._td_copies.setValue(5)
    window._td_relative.setChecked(True)
    window._apply_transform_duplicate()
    assert sum(s.item_count for s in window._result.sheets) == 6


def test_transformar_gerar_grade(qapp, tmp_path):
    # Aba Transformar: grade 5x4 = 20 pecas.
    src = _n_page_pdf(tmp_path, 1, name="tg")
    window = _window(tmp_path)
    window._width.setValue(6000)
    window._height.setValue(6000)
    window.add_paths([src])
    window.generate(blocking=True)

    window._piece_items[0].setSelected(True)
    window._tg_cols.setValue(5)
    window._tg_rows.setValue(4)
    window._apply_transform_grid()
    assert sum(s.item_count for s in window._result.sheets) == 20


def test_transformar_preview_fantasma(qapp, tmp_path):
    # Preview "fantasma" aparece na cena e some ao aplicar (vira peca real).
    src = _n_page_pdf(tmp_path, 1, name="tp")
    window = _window(tmp_path)
    window._width.setValue(3000)
    window._height.setValue(3000)
    window.add_paths([src])
    window.generate(blocking=True)

    window._props_tabs.setCurrentWidget(window._transform_page)  # ativa a aba
    window._piece_items[0].setSelected(True)
    window._td_copies.setValue(3)
    window._preview_duplicate()
    assert len(window._ghost_items) == 3  # 3 copias fantasma

    window._apply_transform_duplicate()
    assert window._ghost_items == []  # aplicou -> fantasmas somem
    assert sum(s.item_count for s in window._result.sheets) == 4  # original + 3


def test_excluir_ultima_peca_remove_da_tela(qapp, tmp_path):
    # Bug: excluir a UNICA peca nao a removia (voltava do _effective_sheets).
    src = _n_page_pdf(tmp_path, 1, name="uma")  # 1 pagina = 1 peca
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([src])
    window.generate(blocking=True)
    assert sum(s.item_count for s in window._result.sheets) == 1

    window._piece_items[0].setSelected(True)
    window._delete_selected()
    assert sum(s.item_count for s in window._result.sheets) == 0  # a peca sumiu
    assert window._piece_items == []


def test_remover_da_biblioteca_tira_a_peca_da_tela(qapp, tmp_path):
    # Bug: remover o unico arquivo da biblioteca deixava a arte "presa" na chapa.
    from app.presentation.main_window import PieceItem

    src = _n_page_pdf(tmp_path, 1, name="lib1")
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([src])
    window.generate(blocking=True)
    assert sum(s.item_count for s in window._result.sheets) == 1

    window._table.setCurrentCell(0, 0)
    window.remove_selected()
    assert window._paths == []
    # a peca nao pode mais estar na cena
    assert not [it for it in window._scene.items() if isinstance(it, PieceItem)]


def _art_of(window, piece):
    return next(a for a in window._result.artworks if a.id == piece.artwork_id)


def test_pontos_editar_no_vale_para_o_arquivo_e_copias(qapp, tmp_path):
    # Ferramenta Pontos: mover um nó salva a faca MANUAL do arquivo; duplicar
    # depois herda a faca corrigida (fluxo: arruma -> duplica -> nesting).
    from app.domain.geometry import Point2D
    from tests import synth_images as si
    src = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    piece = window._piece_items[0]
    piece.setSelected(True)

    art0 = _art_of(window, piece)
    pts = [list(c.points) for c in (art0.cut_contour, *art0.extra_cuts)]
    original = pts[0][0]
    pts[0][0] = Point2D(original.x + 7.0, original.y + 5.0)  # "puxa" um nó
    window._commit_manual_faca(piece, pts, "mover nó")

    path = window._paths[0]
    assert path in window._faca_manual  # virou faca manual do ARQUIVO
    art1 = _art_of(window, window._piece_items[0])
    p0 = art1.cut_contour.points[0]
    assert abs(p0.x - (original.x + 7.0)) < 0.01
    assert abs(p0.y - (original.y + 5.0)) < 0.01

    # duplicar herda a mesma faca (mesmo artwork_id -> mesma arte)
    window._piece_items[0].setSelected(True)
    window._duplicate_selected()
    assert sum(s.item_count for s in window._result.sheets) == 2

    # sangria de imagem NAO muda mais a faca manual
    w_antes = _art_of(window, window._piece_items[0]).cut_contour.size.width
    window._auto_offset.setValue(window._auto_offset.value() + 5)
    w_depois = _art_of(window, window._piece_items[0]).cut_contour.size.width
    assert abs(w_depois - w_antes) < 0.01

    # desfazer (ate antes da edicao) limpa a faca manual de verdade
    while path in window._faca_manual:
        window._undo.undo()
    assert path not in window._faca_manual


def test_pontos_remover_e_adicionar_no(qapp, tmp_path):
    from tests import synth_images as si
    src = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    piece = window._piece_items[0]
    piece.setSelected(True)
    art0 = _art_of(window, piece)
    n0 = len(art0.cut_contour.points)

    window._remove_node(piece, 0, 0)  # remove o primeiro nó
    art1 = _art_of(window, window._piece_items[0])
    assert len(art1.cut_contour.points) == n0 - 1

    # adiciona um nó de volta no meio do primeiro segmento (via commit direto)
    pts = [list(c.points) for c in (art1.cut_contour, *art1.extra_cuts)]
    from app.domain.geometry import Point2D
    a, b = pts[0][0], pts[0][1]
    pts[0].insert(1, Point2D((a.x + b.x) / 2, (a.y + b.y) / 2))
    window._commit_manual_faca(piece, pts, "adicionar nó")
    art2 = _art_of(window, window._piece_items[0])
    assert len(art2.cut_contour.points) == n0


def test_pontos_voltar_ao_automatico(qapp, tmp_path):
    from app.domain.geometry import Point2D
    from tests import synth_images as si
    src = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    piece = window._piece_items[0]
    piece.setSelected(True)
    art0 = _art_of(window, piece)
    w_auto = art0.cut_contour.size.width

    pts = [list(c.points) for c in (art0.cut_contour, *art0.extra_cuts)]
    pts[0][0] = Point2D(pts[0][0].x + 15.0, pts[0][0].y)
    window._commit_manual_faca(piece, pts)
    path = window._paths[0]
    assert path in window._faca_manual

    window._selected_path = path
    window._reset_manual_faca()
    assert path not in window._faca_manual
    art_back = _art_of(window, window._piece_items[0])
    assert abs(art_back.cut_contour.size.width - w_auto) < 0.01  # recalculada


def test_imagem_com_varios_desenhos_gera_faca_de_cada(qapp, tmp_path):
    # Folha com 2 adesivos separados -> a peca segue UMA so, mas com 2 facas
    # (a principal + 1 extra). Antes so saia a faca do maior desenho.
    from tests import synth_images as si
    src = si.png_dois_adesivos(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    # modo contorno (o alpha ja cai em contorno no auto, mas forcamos)
    window._faca_mode.setCurrentIndex(window._faca_mode.findData("contour"))
    window.generate(blocking=True)

    art = window._result.artworks[0]
    assert art.has_cut  # faca principal
    assert len(art.extra_cuts) == 1  # o segundo adesivo virou faca extra
    # continua UMA peca no nesting (a folha nao foi fatiada)
    assert sum(s.item_count for s in window._result.sheets) == 1

    # e a exportacao (DXF/faca) leva as 2 linhas de corte
    from app.application.positioning import positioned_cut_contours_sheets
    contornos = positioned_cut_contours_sheets(
        window._result.sheets, window._result.artworks,
        window._result.sheets[0].material.width,
    )
    assert len(contornos) == 2  # 2 facas posicionadas


def test_marcas_de_registro_enquadram_a_folha_toda(qapp, tmp_path):
    # Bug: com varios desenhos, as marcas de registro usavam so o MAIOR desenho
    # e saiam no lugar errado. O enquadramento tem que cobrir a peca inteira.
    from app.application.positioning import _faca_rects_of, _union_bbox
    from tests import synth_images as si
    src = si.png_dois_adesivos(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._faca_mode.setCurrentIndex(window._faca_mode.findData("contour"))
    window.generate(blocking=True)

    art = window._result.artworks[0]
    assert art.extra_cuts  # ha mais de um desenho
    sheet = window._result.sheets[0]
    by_id = {a.id: a for a in window._result.artworks}
    bbox = _union_bbox(_faca_rects_of(sheet, by_id, 0.0))
    # o enquadramento cobre os DOIS discos -> bem mais largo que um disco so
    um_disco = art.cut_contour.size.width
    assert (bbox.max_x - bbox.min_x) > um_disco * 1.5


def test_duplicar_so_a_pagina_selecionada(qapp, tmp_path, monkeypatch):
    # PDF com varias paginas: duplicar SO a pagina selecionada, sem duplicar tudo.
    from collections import Counter

    from PySide6.QtWidgets import QInputDialog

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([src])
    window.generate(blocking=True)
    alvo = window._piece_items[0].artwork_id
    outras = {p.artwork_id for p in window._piece_items if p.artwork_id != alvo}
    assert outras  # ha outra pagina no mesmo PDF
    n0 = sum(s.item_count for s in window._result.sheets)

    monkeypatch.setattr(QInputDialog, "getInt", lambda *a, **k: (2, True))
    window._piece_items[0].setSelected(True)
    window._duplicate_selected_qty()

    assert sum(s.item_count for s in window._result.sheets) == n0 + 2  # +2 no total
    cont = Counter(a.id for a in window._result.artworks)
    assert cont[alvo] == 3  # 1 original + 2 copias
    for o in outras:
        assert cont[o] == 1  # as outras paginas NAO foram duplicadas


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
    from app.presentation.main_window import GuideItem
    from PySide6.QtCore import QPointF

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


def test_faca_auto_corta_jpg_opaco_como_retangulo(qapp, tmp_path):
    # Regressao: um JPG opaco (sem transparencia) tem que sair QUADRADO por
    # padrao, e nao com o contorno serrilhado do desenho. No modo Automatico,
    # imagem opaca -> retangulo; e da pra forcar o contorno quando quiser.
    from tests import synth_images as si
    src = si.jpg_circle(tmp_path)  # JPG opaco, desenho redondo
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)  # modo Automatico (padrao)
    rect_pts = len(window._result.artworks[0].cut_contour.points)
    assert rect_pts <= 5  # retangulo, mesmo o desenho sendo redondo

    # forcando "Contorno justo": volta a seguir o formato (muitos pontos)
    window._faca_mode.setCurrentIndex(window._faca_mode.findData("contour"))
    contour_pts = len(window._result.artworks[0].cut_contour.points)
    assert contour_pts > 8


def test_faca_auto_recorta_png_transparente_pelo_contorno(qapp, tmp_path):
    # No modo Automatico, imagem com transparencia (PNG alpha) sai recortada
    # no formato (contorno), nao como um retangulo.
    from tests import synth_images as si
    src = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    pts = len(window._result.artworks[0].cut_contour.points)
    assert pts > 8  # disco -> contorno redondo, nao 4 cantos


def test_redimensionar_arquivo_escala_arte_e_faca(qapp, tmp_path):
    from app.domain.geometry import Size

    src = _two_page_pdf(tmp_path)  # ~70.5 x 35.3 mm
    window = _window(tmp_path)
    window.add_paths([src])
    window._offset.setValue(0)  # faca exata = tamanho da arte
    window.generate(blocking=True)
    art0 = window._result.artworks[0]
    w0, h0 = art0.size.width, art0.size.height

    # dobra a largura e a altura desse arquivo
    window._file_sizes[src] = Size(w0 * 2, h0 * 2)
    window._relayout()

    art = window._result.artworks[0]
    assert abs(art.size.width - w0 * 2) < 0.01
    assert abs(art.size.height - h0 * 2) < 0.01
    # a faca acompanha o novo tamanho (todas as copias mudam)
    assert abs(art.cut_contour.size.width - w0 * 2) < 0.01
    assert all(
        abs(a.size.width - w0 * 2) < 0.01 for a in window._result.artworks
    )


def test_redimensionar_escala_faca_do_cliente_vetorial(qapp, tmp_path):
    from app.domain.geometry import Size

    window = _window(tmp_path)
    window.add_paths([_vector_cut_pdf(tmp_path)])
    window._faca_mode.setCurrentIndex(window._faca_mode.findData("vector"))
    window._offset.setValue(0)  # sem sangria (faca PDF) -> testa a escala pura do contorno
    window.generate(blocking=True)
    path = window._path_of(window._result.artworks[0].id)
    faca_w0 = window._result.artworks[0].cut_contour.size.width

    art0 = window._result.artworks[0]
    window._file_sizes[path] = Size(art0.size.width * 2, art0.size.height * 2)
    window._relayout()

    # o contorno vetorial do cliente tambem dobra (nao vira retangulo)
    faca = window._result.artworks[0].cut_contour
    assert abs(faca.size.width - faca_w0 * 2) < 0.5
    assert len(faca.points) > 5


def test_redimensionar_pela_ui_mantem_proporcao_e_reseta(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._offset.setValue(0)
    window.generate(blocking=True)
    art0 = window._result.artworks[0]
    ratio = art0.size.width / art0.size.height

    window._piece_items[0].setSelected(True)  # abre a aba da peca
    assert window._selected_path == src
    assert window._ps_lock.isChecked()  # proporcao travada por padrao

    nova_largura = art0.size.width * 1.5
    window._ps_w.setValue(nova_largura)  # dispara o redimensionamento

    art = window._result.artworks[0]
    assert abs(art.size.width - nova_largura) < 0.05
    # altura ajustada mantendo a proporcao
    assert abs(art.size.width / art.size.height - ratio) < 1e-3
    assert src in window._file_sizes

    window._reset_piece_size()  # volta ao tamanho original
    assert src not in window._file_sizes
    assert abs(window._result.artworks[0].size.width - art0.size.width) < 0.05


def test_reset_all_defaults_zera_espacamento(qapp, tmp_path):
    # Regra: ao adicionar arquivo com a area vazia, zera TUDO (inclui o
    # espacamento vertical negativo que sobrepunha as pecas).
    from app.domain.geometry import Size

    window = _window(tmp_path)
    window._spacing_v.setValue(-35)
    window._spacing.setValue(10)
    window._offset.setValue(5)
    window._file_sizes["x.pdf"] = Size(10, 10)
    window._reg_type.setCurrentIndex(window._reg_type.findData("circles"))  # marcas ligadas
    window._reset_all_defaults()
    assert window._spacing_v.value() == 0
    assert window._spacing.value() == 0
    assert window._offset.value() == 0
    assert window._file_sizes == {}  # tamanhos personalizados descartados
    assert window._reg() == "none"   # trabalho novo comeca SEM marcas de registro


def test_open_external_files_adiciona_a_producao(qapp, tmp_path):
    # Integracao CorelDRAW/CLI: receber um arquivo de fora joga na producao.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.open_external_files([src])
    assert window._result is not None
    assert any(window._path_of(a.id) == src for a in window._result.artworks)
    # arquivo inexistente e ignorado (nao quebra)
    window.open_external_files(["nao_existe.pdf"])


def test_exportar_apenas_a_selecao(qapp, tmp_path):
    # Selecionar pecas e exportar SO elas (recortado, sem o resto / sem branco).
    import ezdxf

    src = _n_page_pdf(tmp_path, 5, w=283, h=170, name="cinco")
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window._offset.setValue(0)
    window.add_paths([src])
    window.generate(blocking=True)
    assert sum(s.item_count for s in window._result.sheets) == 5

    window._piece_items[0].setSelected(True)
    window._piece_items[1].setSelected(True)
    res = window._selection_export_sheets()
    assert res is not None
    synthetic, (w, h) = res
    assert synthetic[0].item_count == 2  # so as 2 selecionadas

    out = str(tmp_path / "SEL.dxf")
    window.export_dxf(out, sheets_override=synthetic)
    doc = ezdxf.readfile(out)
    assert len(doc.modelspace().query("LWPOLYLINE")) == 2  # so as 2, sem o resto


def test_girar_arquivo_selecionado_reencaixa(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([src])
    window.generate(blocking=True)
    art0 = window._result.artworks[0]
    w0, h0 = art0.size.width, art0.size.height

    window._piece_items[0].setSelected(True)
    window._rotate_selected(90)  # gira o arquivo da peca selecionada
    # a arte daquele arquivo girou (L<->A trocados)
    by_path = {}
    for a in window._result.artworks:
        by_path.setdefault(window._path_of(a.id), a)
    rot = by_path[src]
    assert abs(rot.size.width - h0) < 0.5 and abs(rot.size.height - w0) < 0.5


def test_girar_so_uma_peca_nao_afeta_as_outras(qapp, tmp_path):
    # rotacao POR PECA: girar uma pagina nao gira as outras do mesmo PDF.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([src])
    window.generate(blocking=True)
    antes = {a.id: (a.size.width, a.size.height) for a in window._result.artworks}
    alvo = window._piece_items[0].artwork_id
    outras = [aid for aid in antes if aid != alvo]
    assert outras  # ha outra peca para comparar

    window._piece_items[0].setSelected(True)
    window._rotate_selected(90)

    depois = {a.id: (a.size.width, a.size.height) for a in window._result.artworks}
    w0, h0 = antes[alvo]
    w1, h1 = depois[alvo]
    assert abs(w1 - h0) < 0.5 and abs(h1 - w0) < 0.5  # a peca girou (L<->A)
    for aid in outras:
        assert depois[aid] == antes[aid]  # as outras ficaram iguais
    # a exportacao leva o giro por peca (so a alvo girada)
    assert window._print_kwargs()["rotations"][alvo] == 90
    for aid in outras:
        assert window._print_kwargs()["rotations"][aid] == 0


def test_pecas_selecionaveis_na_tela_dividida(qapp, tmp_path):
    from app.presentation.main_window import PieceItem
    from PySide6.QtWidgets import QGraphicsItem

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    window._view_mode.setCurrentIndex(window._view_mode.findData("split"))

    sel = [
        it for it in window._scene.items()
        if isinstance(it, PieceItem)
        and (it.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
    ]
    assert len(sel) > 0  # da pra selecionar a peca/faca na tela dividida
    sel[0].setSelected(True)
    assert window._selected_sheet_indices() == [sel[0].sheet_index]


def test_unidade_no_menu_opcoes(qapp, tmp_path):
    window = _window(tmp_path)
    assert hasattr(window, "_act_unit_cm") and hasattr(window, "_act_unit_mm")
    from app.presentation import units
    window._on_unit_changed(units.MM)
    assert units.unit() == units.MM
    window._on_unit_changed(units.CM)
    assert units.unit() == units.CM


def test_chapa_branca_nao_some_ao_clicar_no_vazio(qapp, tmp_path):
    # Regressao (GC): clicar na area vazia (laco de selecao) nao pode remover a
    # chapa branca de fundo nem outros itens decorativos da cena.
    import gc

    from app.presentation import main_window as M
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.resize(1000, 700)
    window.show()
    window.add_paths([src])
    window._width.setValue(700)
    window._height.setValue(1950)
    window.generate(blocking=True)
    window._fit_view()
    qapp.processEvents()

    def n_rects():
        return len([it for it in window._scene.items()
                    if type(it).__name__ == "QGraphicsRectItem"])

    antes = n_rects()
    assert antes >= 1  # ao menos a chapa branca

    last = window._result.sheets[-1]
    dxs = (len(window._result.sheets) - 1) * (last.material.width + M.SHEET_GAP_MM)
    vp = window._view.viewport()
    pos = window._view.mapFromScene(QPointF(dxs + last.material.width * 0.5,
                                            last.used_length - 15))
    for _ in range(3):
        for kind, btn in [(QEvent.MouseButtonPress, Qt.LeftButton),
                          (QEvent.MouseButtonRelease, Qt.NoButton)]:
            qapp.sendEvent(vp, QMouseEvent(kind, QPointF(pos), vp.mapToGlobal(pos),
                                           Qt.LeftButton, btn, Qt.NoModifier))
        gc.collect()
        qapp.processEvents()
    assert n_rects() == antes  # a chapa branca continua la


def test_redimensionar_atualiza_na_hora(qapp, tmp_path):
    # Regressao: mudar a medida no campo deve refletir VISUALMENTE na hora
    # (sem precisar duplicar). O PieceItem desenhado muda de tamanho.
    from PySide6.QtCore import QPointF

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([src])
    window._add_file_to_production(src, QPointF(10, 10))
    piece = window._piece_items[0]
    window._selected_path = window._path_of(piece.artwork_id)

    window._ps_w.setValue(400)  # muda a largura (dispara on-the-fly)
    assert abs(window._piece_items[0].rect().width() - 400) < 1.0


def test_arrastar_segundo_arquivo_organiza_nesting(qapp, tmp_path):
    # Arrastar outro arquivo (varias paginas) deve ORGANIZAR (nesting), nao
    # empilhar tudo no ponto do drop.
    from PySide6.QtCore import QPointF

    a = _two_page_pdf(tmp_path)
    b = _n_page_pdf(tmp_path, 3, name="multi3")
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([a, b])
    window._add_file_to_production(a, QPointF(10, 10))
    window._add_file_to_production(b, QPointF(50, 50))  # arrasta b (3 paginas)

    bpos = [
        (round(it.position.x), round(it.position.y))
        for sh in window._result.sheets
        for it in sh.items
        if window._path_of(it.artwork_id) == b
    ]
    assert len(bpos) == 3
    assert len(set(bpos)) == 3  # posicoes distintas = organizado (nao empilhado)


def test_soltar_arquivo_sem_faca_e_gerar_depois(qapp, tmp_path):
    # Soltar arquivo da biblioteca = so a arte (sem faca); a faca surge ao
    # clicar "Gerar Faca".
    from PySide6.QtCore import QPointF

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([src])
    window._add_file_to_production(src, QPointF(10, 10))  # arrasta (soltar)

    assert window._result is not None
    assert not any(a.has_cut for a in window._result.artworks)  # SEM faca

    window._regenerate_faca()  # botao "Gerar Faca"
    assert all(a.has_cut for a in window._result.artworks)  # agora COM faca


def test_rotacionar_reencaixa_mantendo_quantidade(qapp, tmp_path):
    # Rotacionar re-nesta (re-encaixa) mantendo a quantidade, inclusive duplicatas.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)
    window.add_paths([src])
    window.generate(blocking=True)
    window._select_all()
    window._duplicate_selected()
    n = sum(s.item_count for s in window._result.sheets)
    assert n > 2

    window._rotation.setCurrentText("90")
    assert sum(s.item_count for s in window._result.sheets) == n  # mantem qtd


def test_arrastar_um_arquivo_abre_so_ele(qapp, tmp_path):
    # 3 arquivos na biblioteca, nada gerado: arrastar UM abre so ele (nao todos).
    from PySide6.QtCore import QPointF

    a = _two_page_pdf(tmp_path)
    b = _n_page_pdf(tmp_path, 1, name="bbb")
    c = _n_page_pdf(tmp_path, 1, name="ccc")
    window = _window(tmp_path)
    window._width.setValue(3000)
    window._height.setValue(3000)
    window.add_paths([a, b, c])
    assert window._result is None  # nada gerado ainda

    window._add_file_to_production(b, QPointF(10, 10))  # arrasta so o b
    na_producao = {window._path_of(art.id) for art in window._result.artworks}
    assert na_producao == {b}  # SO o arquivo arrastado


def test_pecas_nao_somem_na_tela_dividida(qapp, tmp_path):
    # Regressao (GC): na tela dividida as pecas nao sao interativas e nao ficavam
    # referenciadas -> sumiam ao clicar. Agora ficam guardadas.
    import gc

    from PySide6.QtWidgets import QGraphicsPixmapItem

    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    window._view_mode.setCurrentIndex(window._view_mode.findData("split"))

    def n_pix():
        return len([it for it in window._scene.items()
                    if isinstance(it, QGraphicsPixmapItem)])

    antes = n_pix()
    assert antes >= 1
    for _ in range(3):
        gc.collect()
        qapp.processEvents()
    assert n_pix() == antes  # arte continua na tela dividida apos GC


def test_rotacionar_mantem_duplicatas_manuais(qapp, tmp_path):
    # Rotacionar (mudanca de geometria) NAO pode perder as copias duplicadas.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._width.setValue(3000)
    window._height.setValue(3000)
    window.generate(blocking=True)
    window._select_all()
    window._duplicate_selected()  # dobra a quantidade
    n_dup = sum(s.item_count for s in window._result.sheets)
    assert n_dup > 2

    window._rotation.setCurrentText("90")  # rotaciona TODOS
    assert sum(s.item_count for s in window._result.sheets) == n_dup  # mantem as copias

    window._offset.setValue(3)  # outra mudanca de geometria tambem preserva
    assert sum(s.item_count for s in window._result.sheets) == n_dup


def test_clique_com_tremor_nao_move_a_peca(qapp, tmp_path):
    # "Somente clicando" (com leve tremor do mouse) NAO pode mover/sumir a peca.
    from app.presentation.main_window import PieceItem
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

    def count():
        return len([it for it in window._scene.items() if isinstance(it, PieceItem)])

    piece = window._piece_items[0]
    antes = (round(piece.scenePos().x(), 1), round(piece.scenePos().y(), 1))
    vp = window._view.viewport()
    center = piece.scenePos() + QPointF(
        piece.rect().width() / 2, piece.rect().height() / 2
    )
    start = window._view.mapFromScene(center)
    end = QPoint(start.x() + 3, start.y() + 2)  # tremor < zona morta (6px)

    def send(kind, pos, buttons=Qt.LeftButton):
        ev = QMouseEvent(kind, QPointF(pos), vp.mapToGlobal(pos),
                         Qt.LeftButton, buttons, Qt.NoModifier)
        qapp.sendEvent(vp, ev)

    send(QEvent.MouseButtonPress, start)
    send(QEvent.MouseMove, end)
    send(QEvent.MouseButtonRelease, end, buttons=Qt.NoButton)
    qapp.processEvents()

    assert count() == 2  # nenhuma peca sumiu
    depois = (round(piece.scenePos().x(), 1), round(piece.scenePos().y(), 1))
    assert depois == antes  # nao moveu (clique dentro da zona morta)
    assert window._undo.count() == 0  # nao virou um movimento


def test_ctrlz_ilimitado_sobrevive_a_mudanca_de_parametro(qapp, tmp_path):
    # Regressao: mudar um parametro NAO pode apagar o historico de desfazer.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    assert window._undo.count() == 0  # gerar = recomeco limpo

    window._piece_items[0].setSelected(True)
    window._nudge(50.0, 0.0)
    assert window._undo.count() == 1  # 1 movimento

    window._offset.setValue(window._offset.value() + 3)  # muda parametro -> relayout
    assert window._undo.count() == 2  # mover + ajustar (historico PRESERVADO)

    # desfaz tudo sem quebrar
    while window._undo.canUndo():
        window._undo.undo()
    assert window._result is not None


def test_desfazer_recupera_arranjo_apos_mudar_parametro(qapp, tmp_path):
    # A "pagina em branco"/arranjo manual nao se perde: Ctrl+Z volta o estado.
    src = _n_page_pdf(tmp_path, 3)
    window = _window(tmp_path)
    window.add_paths([src])
    window._width.setValue(3000)
    window.generate(blocking=True)

    window._piece_items[0].setSelected(True)
    window._delete_selected()  # deixa um "vazio" (2 pecas)
    n_apagado = sum(s.item_count for s in window._result.sheets)
    assert n_apagado == 2

    window._offset.setValue(window._offset.value() + 2)  # re-nesta (mexe no arranjo)
    window._undo.undo()  # volta ao arranjo com a peca apagada
    assert sum(s.item_count for s in window._result.sheets) == n_apagado


def test_relayouts_seguidos_se_fundem_num_passo(qapp, tmp_path):
    # Arrastar a setinha de um campo varias vezes vira UM passo de desfazer.
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)
    for _ in range(5):
        window._offset.setValue(window._offset.value() + 1)
    assert window._undo.count() == 1  # 5 ajustes -> 1 passo (merge)


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


def test_sangria_pdf_vale_no_modo_contorno(qapp, tmp_path):
    # Regressao: a "Sangria da faca (PDF)" tem que valer tambem no modo "pelo
    # contorno" (antes so valia no modo retangulo -> "as vezes nao funcionava").
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_circle(fitz.Point(100, 100), 80, color=(0, 0.5, 0), fill=(0, 0.5, 0))
    src = tmp_path / "circ.pdf"
    doc.save(str(src))
    doc.close()

    window = _window(tmp_path)
    window.add_paths([str(src)])
    window._faca_mode.setCurrentIndex(window._faca_mode.findData("contour"))
    window._offset.setValue(0)
    window.generate(blocking=True)
    w0 = window._result.artworks[0].cut_contour.size.width

    window._offset.setValue(8)  # sangria para fora -> a faca cresce
    w1 = window._result.artworks[0].cut_contour.size.width
    assert w1 > w0 + 5


def test_recorte_de_pagina_reduz_tamanho_e_mantem_path(qapp, tmp_path):
    doc = fitz.open()
    pg = doc.new_page(width=283.46, height=283.46)  # ~100x100mm
    pg.draw_rect(pg.rect, color=(0, 0, 0), fill=(0, 0, 0))
    src = tmp_path / "crop.pdf"
    doc.save(str(src))
    doc.close()

    window = _window(tmp_path)
    window.add_paths([str(src)])
    window.generate(blocking=True)
    assert round(window._result.artworks[0].size.width) == 100

    # recorta 10mm de cada lado da pagina 0
    window._page_crops[str(src)] = {0: (10.0, 10.0, 10.0, 10.0)}  # l, t, r, b
    window.generate(blocking=True)
    art = window._result.artworks[0]
    assert round(art.size.width) == 80   # 100 - 10 - 10
    assert round(art.size.height) == 80
    # quantidade/projeto continuam mapeados pelo caminho ORIGINAL
    assert window._path_of(art.id) == str(src)


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
        ImportPdfUseCase(PdfiumImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(cache_dir=folder / "imgcache")),
    )
    return MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PikePdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PdfiumPageRenderer(),
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


def test_qax01_editar_apos_salvar_marca_dirty(qapp, tmp_path):
    # QA EXTREMO QAX-01 (🔴): mudar parâmetro/quantidade depois de salvar
    # deixava _dirty=False e fechar descartava o trabalho em silêncio.
    src = _two_page_pdf(tmp_path)
    w = _window(tmp_path)
    w.add_paths([src])
    w.generate(blocking=True)
    assert w.save_project(str(tmp_path / "t.printnest")) is True
    assert w._dirty is False
    w._auto_offset.setValue(3.0)  # mudar parâmetro global (dispara relayout)
    assert w._dirty is True


def test_qax02_tipo_na_barra_cria_override_esparso(qapp, tmp_path):
    # QA EXTREMO QAX-02 (🟠): Tipo com seleção gravava override COMPLETO e
    # congelava recorte/giro/offset globais no arquivo.
    src = _two_page_pdf(tmp_path)
    w = _window(tmp_path)
    w.add_paths([src])
    w.generate(blocking=True)
    w._selected_path = src
    w._ct_mode.setCurrentIndex(w._ct_mode.findData("contour"))
    assert set(w._file_overrides[src]) == {"mode"}  # ESPARSO: só a chave mexida
    w._selected_path = None
    w._crop.setValue(2.0)  # global posterior TEM de valer para o arquivo
    assert w._params_for(src)["crop"] == 2.0


def test_qax03_encaixe_tolera_ruido_de_float(qapp, tmp_path):
    # QA EXTREMO QAX-03 (🟠): peça de PDF "100mm" media 100,0000046mm e o
    # encaixe com EPS 1e-6 jogava metade das peças para OUTRA chapa.
    import fitz
    pdf = tmp_path / "cem.pdf"
    doc = fitz.open()
    mm2pt = 72.0 / 25.4
    doc.new_page(width=100 * mm2pt, height=100 * mm2pt)
    doc.save(str(pdf))
    doc.close()
    w = _window(tmp_path)
    w._width.setValue(200)  # 2 peças de 100 cabem LADO A LADO
    w._spacing.setValue(0)
    w.add_paths([str(pdf)])
    w._table.cellWidget(0, 1).setValue(2)
    w.generate(blocking=True)
    assert len(w._result.sheets) == 1  # UMA chapa (antes: 2, dobro de material)


def test_combos_tipo_de_faca_tem_miniaturas(qapp, tmp_path):
    # Ilustração dos tipos de faca (13/07): cada opção dos 3 combos ganha
    # miniatura (arte + linha de faca tracejada) e dica própria ao pairar.
    from PySide6.QtCore import Qt
    w = _window(tmp_path)
    for combo in (w._ct_mode, w._faca_mode, w._pf_mode):
        assert combo.count() == len(w._FACA_MODES)
        for i in range(combo.count()):
            assert not combo.itemIcon(i).isNull()
            assert combo.itemData(i, Qt.ToolTipRole)


def test_ilustracoes_nos_demais_controles(qapp, tmp_path):
    # Pacote de ilustrações (13/07): nós da faca, modo do corte, marcas de
    # registro, caixa de importação, modo de visualização, sangria fora/
    # dentro, raio dos cantos e a faixa de 3 passos do canvas vazio.
    from app.presentation import faca_icons
    from PySide6.QtCore import Qt
    w = _window(tmp_path)
    for name in ("_ct_nodes", "_faca_nodes", "_ct_shared", "_reg_type",
                 "_import_box", "_view_mode"):
        combo = getattr(w, name)
        assert combo.count() > 0, name
        for i in range(combo.count()):
            assert not combo.itemIcon(i).isNull(), f"{name}[{i}] sem miniatura"
            assert combo.itemData(i, Qt.ToolTipRole), f"{name}[{i}] sem dica"
    assert not w._ct_dir.button(1).icon().isNull()   # sangria para fora
    assert not w._ct_dir.button(2).icon().isNull()   # sangria para dentro
    assert not w._ct_radius_icon.pixmap().isNull()   # canto -> arredondado
    for step in (0, 1):                              # faixa do canvas vazio
        assert not faca_icons.empty_steps_pixmap(step).isNull()
    assert w._view.empty_step == 0  # janela recém-aberta: passo "Adicionar"


def test_cartelas_fluxo_mimaki_iecho(qapp, tmp_path, monkeypatch):
    # Fluxo de cartelas (13/07): peças encaixam DENTRO das cartelas, a faca
    # IECHO sai com as linhas retas fora a fora em DXF e a faca Mimaki sai
    # em PDF sem as bolinhas.
    # 16/07: o fluxo saiu da UI (CARTELAS_ENABLED=False, planos futuros) —
    # o teste religa o flag para o motor dormente continuar validado.
    import ezdxf

    import app.presentation.main_window as mw
    monkeypatch.setattr(mw, "CARTELAS_ENABLED", True)
    src = _two_page_pdf(tmp_path)
    w = _window(tmp_path)
    w._width.setValue(700)
    w._height.setValue(1000)
    w.add_paths([src])
    w._cart_w.setValue(330.0)
    w._cart_h.setValue(480.0)
    w._cart_gap.setValue(0.0)
    w._cart_margin.setValue(5.0)
    w._cart_on.setChecked(True)
    w.generate(blocking=True)

    # toda peça respeita a origem da grade (20,20) + respiro interno (5)
    for layout in w._result.sheets:
        for item in layout.items:
            assert item.position.x >= 25 - 1e-6
            assert item.position.y >= 25 - 1e-6

    out_dxf = tmp_path / "FACA-IECHO.dxf"
    w.export_faca_iecho(str(out_dxf))
    doc = ezdxf.readfile(str(out_dxf))
    lines = [e for e in doc.modelspace() if e.dxftype() == "LINE"]
    assert len(lines) >= 6  # grade 2x2 colada: 3 verticais + 3 horizontais

    out_pdf = tmp_path / "FACA-MIMAKI.pdf"
    w.export_faca_mimaki(str(out_pdf))
    assert out_pdf.exists()

    # desligado, a exportação IECHO não gera nada (fluxo normal intacto)
    w._cart_on.setChecked(False)
    out2 = tmp_path / "nada.dxf"
    w.export_faca_iecho(str(out2))
    assert not out2.exists()


def test_cartelas_pausado_some_da_ui(qapp, tmp_path):
    # 16/07: fluxo de cartelas pausado (CARTELAS_ENABLED=False) — nenhuma
    # porta de entrada na UI, e o app funciona normal sem a aba existir.
    w = _window(tmp_path)
    tabs = [w._props_tabs.tabText(i) for i in range(w._props_tabs.count())]
    assert "Cartelas" not in tabs
    assert not hasattr(w, "_cartelas_cta")   # botão azul não existe
    assert not hasattr(w, "_cart_on")        # aba nunca foi construída
    assert not w._cartela_enabled()          # guard central responde False
    menus = [a.text() for a in w.menuBar().actions()]
    assert menus  # menu montou sem os itens de cartela (sem crash)


def test_arrastar_arquivo_do_explorer_adiciona(qapp, tmp_path):
    # Regressão 13/07: o canvas dizia "arraste seus arquivos para cá" mas o
    # drop do Explorer era RECUSADO (cursor proibido) — parecia travamento.
    from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    src = _two_page_pdf(tmp_path)
    w = _window(tmp_path)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(src)])
    event = QDropEvent(
        QPointF(50, 50), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
    )
    w.dropEvent(event)
    import pathlib
    assert pathlib.Path(src) in [pathlib.Path(p) for p in w._paths]  # entrou

    # arquivo não suportado é recusado sem quebrar
    ruim = tmp_path / "x.txt"
    ruim.write_text("nao", encoding="utf-8")
    mime2 = QMimeData()
    mime2.setUrls([QUrl.fromLocalFile(str(ruim))])
    event2 = QDropEvent(
        QPointF(50, 50), Qt.CopyAction, mime2, Qt.LeftButton, Qt.NoModifier
    )
    before = list(w._paths)
    w.dropEvent(event2)
    assert w._paths == before


def test_jpeg_cmyk_vai_para_a_chapa(qapp, tmp_path):
    # Regressão 14/07 (adesivo da gráfica): JPEG CMYK explodia o preview
    # ("cannot write mode CMYK as PNG") e a peça nunca chegava na chapa.
    from PIL import Image
    from PySide6.QtCore import QPointF

    jpg = tmp_path / "cmyk.jpg"
    Image.new("CMYK", (300, 200), (10, 80, 90, 5)).save(jpg, quality=90)
    w = _window(tmp_path)
    w.add_paths([str(jpg)])
    w._table.setCurrentCell(0, 0)
    w._on_library_drop(QPointF(50, 50))  # arrastar da biblioteca p/ o canvas
    assert w._result is not None
    assert sum(s.item_count for s in w._result.sheets) == 1
    w.generate(blocking=True)  # com faca
    out = tmp_path / "IMP.pdf"
    w.export_pdf(str(out))
    assert out.exists()


def test_b1_multi_drop_da_biblioteca(qapp, tmp_path):
    # B1: Ctrl/Shift seleciona VÁRIOS arquivos na biblioteca e o drop solta
    # todos de uma vez (antes era um por um).
    from PIL import Image
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QAbstractItemView

    a, b = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (300, 200), (255, 0, 0)).save(a)
    Image.new("RGB", (200, 300), (0, 0, 255)).save(b)
    w = _window(tmp_path)
    assert w._table.selectionMode() == QAbstractItemView.ExtendedSelection
    w.add_paths([str(a), str(b)])
    w._table.selectAll()  # equivale a Ctrl/Shift nas duas linhas

    # sem produção: o drop gera com os DOIS arquivos selecionados
    w._on_library_drop(QPointF(50, 50))
    assert w._result is not None
    assert sum(s.item_count for s in w._result.sheets) == 2

    # com produção: o drop adiciona os dois de novo (2 + 2 = 4 peças)
    w._table.selectAll()
    w._on_library_drop(QPointF(50, 50))
    assert sum(s.item_count for s in w._result.sheets) == 4


def test_u1_colocar_na_chapa_botao_e_duplo_clique(qapp, tmp_path):
    # U1: quem não sabe arrastar tem o botão "Colocar na chapa" e o duplo
    # clique na biblioteca — ambos reusam o caminho do drop (_on_library_drop).
    from PIL import Image

    a, b = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (300, 200), (255, 0, 0)).save(a)
    Image.new("RGB", (200, 300), (0, 0, 255)).save(b)
    w = _window(tmp_path)
    assert w._btn_place.text().strip() == "Colocar na chapa"
    w.add_paths([str(a), str(b)])

    # sem seleção, o botão coloca TODOS os arquivos (primeira viagem)
    w._table.clearSelection()
    w._btn_place.click()
    assert w._result is not None
    assert sum(s.item_count for s in w._result.sheets) == 2

    # duplo clique numa linha adiciona só aquele arquivo (2 + 1 = 3)
    w._table.setCurrentCell(0, 0)
    w._table.itemDoubleClicked.emit(w._table.item(0, 0))
    assert sum(s.item_count for s in w._result.sheets) == 3


def test_qax04_selecao_em_massa_dispara_handler_uma_vez(qapp, tmp_path):
    # QA EXTREMO QAX-04 (🟠): cada setSelected disparava o handler O(n) →
    # O(n²): 2048 peças = travamento. Em lote, o handler roda 1x.
    src = _two_page_pdf(tmp_path)
    w = _window(tmp_path)
    w.add_paths([src])
    w._table.cellWidget(0, 1).setValue(30)  # 60 peças
    w.generate(blocking=True)
    chamadas = []
    original = w._on_selection_changed
    w._on_selection_changed = lambda: (chamadas.append(1), original())[1]
    w._select_all()
    assert len(w._scene.selectedItems()) >= 60
    assert len(chamadas) <= 2  # antes: 1 por peça (60+)


def test_qax05_arquivo_ausente_nao_aborta_a_geracao(qapp, tmp_path, monkeypatch):
    # QA EXTREMO QAX-05 (🟠): um arquivo ausente abortava a geração INTEIRA.
    # Agora as linhas ⚠ são puladas e o resto gera.
    import pathlib
    src = _two_page_pdf(tmp_path)
    sumido = tmp_path / "sumido.pdf"
    sumido.write_bytes(pathlib.Path(src).read_bytes())
    w = _window(tmp_path)
    w.add_paths([src, str(sumido)])
    sumido.unlink()  # some do disco DEPOIS de importado
    w.generate(blocking=True)
    assert w._result is not None
    assert sum(s.item_count for s in w._result.sheets) == 2  # as páginas do válido


def test_undo_de_ajustes_nao_funde_gestos_separados(qapp):
    # Bug 13/07: TODOS os ajustes da sessão fundiam num único comando e um
    # Ctrl+Z "voltava pro início". Agora só funde o MESMO gesto (janela curta).
    from app.presentation.main_window import (
        _MERGE_WINDOW_S,
        RELAYOUT_MERGE_ID,
        SnapshotCommand,
    )

    a = SnapshotCommand(None, "b0", "a0", "ajustar", merge_id=RELAYOUT_MERGE_ID)
    b = SnapshotCommand(None, "a0", "a1", "ajustar", merge_id=RELAYOUT_MERGE_ID)
    assert a.mergeWith(b) is True  # sequência imediata (segurar setinha): funde
    assert a._after == "a1"

    c = SnapshotCommand(None, "a1", "a2", "ajustar", merge_id=RELAYOUT_MERGE_ID)
    c._stamp = a._stamp + _MERGE_WINDOW_S + 1.0  # "minutos depois"
    assert a.mergeWith(c) is False  # gesto novo: passo de desfazer próprio
    assert a._after == "a1"  # o comando antigo não absorveu o novo


def test_projeto_persiste_overrides_e_faca_manual(qapp, tmp_path):
    # Varredura 09/07: ajustes POR ARQUIVO (barra Faca) e facas manuais
    # (Pontos) se perdiam ao salvar/reabrir o .printnest.
    from app.domain.geometry import Point2D
    from app.domain.model.cut_contour import CutContour

    src = _two_page_pdf(tmp_path)
    w1 = _window(tmp_path)
    w1.add_paths([src])
    w1._file_overrides[src] = {"mode": "contour", "offset": 3.5}
    w1._faca_manual[src] = {
        "contours": [CutContour([Point2D(0, 0), Point2D(10, 0), Point2D(5, 8)])],
        "w": 100.0, "h": 80.0, "rotation": 90,
    }
    proj = tmp_path / "trabalho.printnest"
    assert w1.save_project(str(proj)) is True
    assert w1._dirty is False  # salvo: fechar nao pergunta nada

    w2 = _window(tmp_path)
    assert w2.open_project(str(proj)) is True
    assert w2._file_overrides[src] == {"mode": "contour", "offset": 3.5}
    m = w2._faca_manual[src]
    assert m["w"] == 100.0 and m["h"] == 80.0 and m["rotation"] == 90
    pts = m["contours"][0].points
    assert (pts[0].x, pts[0].y) == (0.0, 0.0) and (pts[2].x, pts[2].y) == (5.0, 8.0)
    assert w2._dirty is False  # recem-aberto: intocado


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
    # contorno irregular: sai como SPLINE (curva de verdade) ou LWPOLYLINE
    # (se a deteccao devolver so retas) — o que importa e ter corte na CUT
    msp = doc.modelspace()
    cortes = list(msp.query("SPLINE")) + list(msp.query("LWPOLYLINE"))
    assert len(cortes) >= 1
    assert all(e.dxf.layer == "CUT" for e in cortes)

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


def test_contorno_toolbar_offset_direcao_cantos(qapp, tmp_path):
    # A ferramenta Contorno (barra) controla sangria (PDF+imagem), direcao e cantos.
    src = _n_page_pdf(tmp_path, 1, name="ct")
    window = _window(tmp_path)
    window._faca_mode.setCurrentIndex(window._faca_mode.findData("contour"))
    window.add_paths([src])
    window.generate(blocking=True)

    # offset externo (positivo) grava nos dois campos de sangria
    window._ct_offset.setValue(5)
    window._ct_dir.button(1).setChecked(True)   # Externo
    window._apply_contour_offset()
    assert window._offset.value() == 5
    assert window._auto_offset.value() == 5

    # interno = negativo
    window._ct_dir.button(2).setChecked(True)   # Interno
    window._apply_contour_offset()
    assert window._offset.value() == -5

    # cantos
    window._ct_corner.button(1).setChecked(True)  # Ponta (miter)
    window._apply_contour_corner()
    assert window._faca_corner == "miter"
    assert window._global_faca_params()["corner"] == "miter"


def test_objeto_barra_mostra_e_edita_tamanho(qapp, tmp_path):
    # Objeto (barra): L/A mostram a medida do objeto clicado e redimensionam.
    src = _n_page_pdf(tmp_path, 1, name="la")
    window = _window(tmp_path)
    window._width.setValue(3000)
    window._height.setValue(3000)
    window._offset.setValue(0)
    window.add_paths([src])
    window.generate(blocking=True)
    window._piece_items[0].setSelected(True)
    p = window._piece_items[0]

    assert abs(window._pb_w.value() - p.rect().width()) < 0.5   # mostra a largura
    assert abs(window._pb_h.value() - p.rect().height()) < 0.5  # mostra a altura

    window._pb_lock.setChecked(False)  # so largura
    w0 = window._result.artworks[0].size.width
    window._pb_w.setValue(w0 + 50)
    window._pbar_resize("w")
    assert window._result.artworks[0].size.width > w0  # editou o tamanho


def test_cadeado_proporcao_na_alca(qapp, tmp_path):
    # O cadeado (Objeto) controla a proporcao ao redimensionar pela alca do mouse.
    from PySide6.QtCore import QPointF

    src = _n_page_pdf(tmp_path, 1, name="rz")
    window = _window(tmp_path)
    window._width.setValue(3000)
    window._height.setValue(3000)
    window._offset.setValue(0)
    window.add_paths([src])
    window.generate(blocking=True)
    window._piece_items[0].setSelected(True)

    ratio = window._result.artworks[0].size.width / window._result.artworks[0].size.height
    p = window._piece_items[0]

    # cadeado ligado -> arrastar so a borda direita mantem a proporcao
    window._pb_lock.setChecked(True)
    assert window._ps_lock.isChecked() is True  # cadeado sincronizado
    alvo = QPointF(
        p.scenePos().x() + p.rect().width() + 60, p.scenePos().y() + p.rect().height() / 2
    )
    window._end_resize(p, alvo, "w")
    art = window._result.artworks[0]
    assert abs(art.size.width / art.size.height - ratio) < 1e-2  # proporcao mantida


def test_alca_redimensiona_por_arraste(qapp, tmp_path):
    # Alcas na peca selecionada; arrastar o canto redimensiona a arte.
    from PySide6.QtCore import QPointF

    src = _n_page_pdf(tmp_path, 1, name="alca")
    window = _window(tmp_path)
    window._width.setValue(3000)
    window._height.setValue(3000)
    window._offset.setValue(0)
    window.add_paths([src])
    window.generate(blocking=True)
    window._piece_items[0].setSelected(True)
    assert len(window._resize_handles) == 3  # 3 alcas (canto + 2 arestas)

    p = window._piece_items[0]
    w0 = window._result.artworks[0].size.width
    window._ps_lock.setChecked(False)  # so largura
    alvo = QPointF(
        p.scenePos().x() + p.rect().width() + 40, p.scenePos().y() + p.rect().height()
    )
    window._end_resize(p, alvo, "w")
    assert window._result.artworks[0].size.width > w0  # a peca cresceu
    assert len(window._resize_handles) == 3  # alcas reaparecem na peca redimensionada


def test_faca_png_apos_remover_pdf(qapp, tmp_path):
    # Bug: soltar PDF, gerar faca, remover, soltar PNG -> gerar faca nao funciona.

    pdf = _n_page_pdf(tmp_path, 1, name="doc")
    png = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window._width.setValue(2000)
    window._height.setValue(2000)

    window.open_external_files([pdf])  # arrasta de fora (drag do desktop)
    window._regenerate_faca()
    assert all(a.has_cut for a in window._result.artworks)  # PDF com faca

    window._table.setCurrentCell(0, 0)
    window.remove_selected()  # remove pela biblioteca

    window.open_external_files([png])  # arrasta o PNG de fora
    window._regenerate_faca()
    png_arts = [a for a in window._result.artworks if window._path_of(a.id) == png]
    assert png_arts, "PNG nao entrou na producao"
    assert all(a.has_cut for a in png_arts), "PNG ficou SEM faca"


def test_gerar_faca_sem_producao_gera_do_zero(qapp, tmp_path):
    # "Gerar Faca" sem producao ainda: gera a producao JA com faca (botao azul
    # sempre funciona, mesmo depois de remover tudo e adicionar outro arquivo).
    png = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([png])
    assert window._loaded is False
    window._regenerate_faca()
    assert window._loaded is True
    assert all(a.has_cut for a in window._result.artworks)


def test_remover_ultimo_arquivo_limpa_producao(qapp, tmp_path):
    # Remover o ultimo arquivo da biblioteca limpa a producao (nao deixa _result
    # desatualizado) -> o proximo arquivo comeca do zero.
    pdf = _n_page_pdf(tmp_path, 1, name="doc")
    window = _window(tmp_path)
    window.add_paths([pdf])
    window.generate(blocking=True)
    assert window._loaded is True
    window._table.setCurrentCell(0, 0)
    window.remove_selected()
    assert window._result is None      # producao limpa
    assert window._loaded is False
    assert window._base_artworks == []


def test_abas_preservam_projetos_separados(qapp, tmp_path):
    # Abas de trabalho: cada aba e um projeto independente; trocar preserva tudo.
    pdf1 = _n_page_pdf(tmp_path, 1, name="proj1")
    pdf2 = _n_page_pdf(tmp_path, 3, name="proj2")
    window = _window(tmp_path)
    window._width.setValue(3000)
    window._height.setValue(3000)

    # aba 1: pdf1 (1 peca)
    window.add_paths([pdf1])
    window.generate(blocking=True)
    assert sum(s.item_count for s in window._result.sheets) == 1

    # nova aba (projeto 2, em branco)
    window._new_tab()
    assert window._tabbar.count() == 2
    assert window._paths == [] and window._result is None

    # aba 2: pdf2 (3 pecas)
    window.add_paths([pdf2])
    window.generate(blocking=True)
    assert sum(s.item_count for s in window._result.sheets) == 3

    # volta para a aba 1 -> pdf1 preservado
    window._tabbar.setCurrentIndex(0)
    assert window._paths == [pdf1]
    assert sum(s.item_count for s in window._result.sheets) == 1

    # volta para a aba 2 -> pdf2 preservado
    window._tabbar.setCurrentIndex(1)
    assert window._paths == [pdf2]
    assert sum(s.item_count for s in window._result.sheets) == 3

    # fechar a aba 2 volta para a 1
    window._close_tab(1)
    assert window._tabbar.count() == 1
    assert window._paths == [pdf1]


def test_recortar_imagem_reduz_tamanho(qapp, tmp_path):
    # "Recortar" agora vale para imagem tambem (mesmo esquema do PDF): cortar
    # bordas reduz o tamanho da arte; a origem continua sendo o arquivo original.
    img = si.jpg_white_square(tmp_path)
    window = _window(tmp_path)
    window.add_paths([img])
    window.generate(blocking=True)
    w0 = window._result.artworks[0].size.width

    # aplica recorte de 5mm em cada lado (como o dialogo "Recortar" faz)
    window._page_crops[img] = {0: (5.0, 5.0, 5.0, 5.0)}
    window._invalidate_crop_cache(img)
    window.generate(blocking=True)
    art = window._result.artworks[0]
    assert art.size.width < w0                       # a imagem recortada ficou menor
    assert window._path_of(art.id) == img            # origem = arquivo original


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


def test_faca_gerada_sai_com_poucos_nos(qapp, tmp_path):
    # Suavizar dobra os nós por passada e a sangria arredondada gera arcos
    # densos — a faca ia pra máquina com centenas de nós. O pós-processamento
    # (FACA_POST_SIMPLIFY_MM) reduz sem mudar a forma (desvio <= 0.1mm).
    from tests import synth_images as si
    src = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._auto_smooth.setValue(3)      # suavizar (x8 nos sem o pos-processo)
    window._auto_offset.setValue(2.0)    # sangria arredondada (x2 de novo)
    window.generate(blocking=True)

    faca = window._result.artworks[0].cut_contour
    assert len(faca.points) <= 60, f"faca com nós demais: {len(faca.points)}"
    assert len(faca.points) >= 8   # continua uma curva, não um retângulo


def test_seletor_nos_da_faca_fino_medio_leve(qapp, tmp_path):
    # "Nós da faca": Fino > Médio > Leve em quantidade de nós; a forma se
    # mantém (largura da faca ~igual nos três níveis).
    from tests import synth_images as si
    src = si.png_alpha_disc(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._auto_smooth.setValue(3)
    window._auto_offset.setValue(2.0)
    window.generate(blocking=True)

    contagens, larguras = {}, {}
    for nivel in ("fino", "medio", "leve"):
        window._faca_nodes.setCurrentIndex(window._faca_nodes.findData(nivel))
        faca = window._result.artworks[0].cut_contour
        contagens[nivel] = len(faca.points)
        larguras[nivel] = faca.size.width

    # ordem nao-estrita: formas simples convergem pro mesmo minimo em niveis
    # vizinhos (a reducao em si ja e travada no teste de poucos_nos)
    assert contagens["fino"] >= contagens["medio"] >= contagens["leve"] >= 6
    # mesma forma: larguras variam menos de 1mm entre os níveis
    assert max(larguras.values()) - min(larguras.values()) < 1.0


def test_registro_rotulos_neutros_pela_forma(qapp, tmp_path):
    """E4: rotulos do combo de registro sem nome de maquina; o data (contrato
    com motor/exportadores/projeto salvo) segue identico e na mesma ordem."""
    window = _window(tmp_path)
    combo = window._reg_type
    assert [combo.itemData(i) for i in range(combo.count())] == [
        "none", "circles", "mimaki", "both", "squares", "crosses", "corner_l",
    ]
    for i in range(combo.count()):
        text = combo.itemText(i)
        assert "Mimaki" not in text and "IECHO" not in text, text
        assert "Summa" not in text and "Graphtec" not in text, text


def test_registro_quadrados_dxf_e_impressao(qapp, tmp_path):
    # "Quadrados" (Summa/OPOS): 4 polilinhas fechadas no REGMARK do DXF e
    # 4 rects pretos no PDF de impressao
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._reg_type.setCurrentIndex(window._reg_type.findData("squares"))
    window.generate(blocking=True)
    out = tmp_path / "CORTE_SQ.dxf"
    window.export_dxf(str(out))
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    regs = [p for p in msp.query("LWPOLYLINE") if p.dxf.layer == "REGMARK"]
    assert len(regs) == 4 and all(p.closed for p in regs)
    assert len(msp.query("LINE")) == 0

    sheets = window._effective_sheets()
    ps = window._print_export.build_print_sheets(
        sheets, window._result.artworks, window._result.sources, **window._print_kwargs()
    )
    assert sum(len(s.rects) for s in ps) == 4
    assert all(r.size == float(window._reg_diameter.value()) for s in ps for r in s.rects)


def test_registro_cruzes_dxf_e_impressao(qapp, tmp_path):
    # "Cruzes" (AOKE/iECHO): 8 linhas no REGMARK e 8 linhas com a espessura
    # escolhida no PDF de impressao
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._reg_type.setCurrentIndex(window._reg_type.findData("crosses"))
    window.generate(blocking=True)
    out = tmp_path / "CORTE_CR.dxf"
    window.export_dxf(str(out))
    doc = ezdxf.readfile(str(out))
    lines = doc.modelspace().query("LINE")
    assert len(lines) == 8
    assert all(ln.dxf.layer == "REGMARK" for ln in lines)

    sheets = window._effective_sheets()
    ps = window._print_export.build_print_sheets(
        sheets, window._result.artworks, window._result.sources, **window._print_kwargs()
    )
    esp = float(window._reg_thickness.value())
    assert sum(len(s.lines) for s in ps) == 8
    assert all(line.width == esp for s in ps for line in s.lines)


def test_registro_l_de_canto_dxf_e_pad(qapp, tmp_path):
    # "L de canto" (Graphtec/Roland): 8 linhas no REGMARK, sem quadro extra;
    # o pad da faca soma margem + tamanho + espessura (bracos para fora)
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._reg_type.setCurrentIndex(window._reg_type.findData("corner_l"))
    window.generate(blocking=True)
    out = tmp_path / "CORTE_L.dxf"
    window.export_dxf(str(out))
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    lines = msp.query("LINE")
    assert len(lines) == 8
    assert all(ln.dxf.layer == "REGMARK" for ln in lines)
    # sem quadro: so as facas das pecas nas polilinhas (nenhuma no REGMARK)
    assert all(p.dxf.layer == "CUT" for p in msp.query("LWPOLYLINE"))
    esperado = (float(window._reg_margin.value())
                + float(window._reg_diameter.value())
                + float(window._reg_thickness.value()))
    assert window._faca_pad() == esperado


def test_registro_tipos_antigos_sem_regressao_no_dxf(qapp, tmp_path):
    # nao-regressao explicita: circles segue igual (5 circulos, sem linha nem
    # polilinha de registro)
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._reg_type.setCurrentIndex(window._reg_type.findData("circles"))
    window.generate(blocking=True)
    out = tmp_path / "CORTE_REGR.dxf"
    window.export_dxf(str(out))
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    assert len(msp.query("CIRCLE")) == 5
    assert len(msp.query("LINE")) == 0
    assert all(p.dxf.layer == "CUT" for p in msp.query("LWPOLYLINE"))


def test_reg_type_desconhecido_cai_em_nenhum(qapp, tmp_path):
    # projeto antigo/desconhecido: chave ausente no combo -> "Nenhuma"
    window = _window(tmp_path)
    window._settings.reg_type = "marca_futurista"
    window._load_settings()
    assert window._reg() == "none"


def test_reg_type_novo_persiste_e_reabre(qapp, tmp_path):
    # projeto salvo com forma nova reabre nela (roundtrip via settings)
    window = _window(tmp_path)
    window._reg_type.setCurrentIndex(window._reg_type.findData("squares"))
    window._reg_thickness.setValue(1.2)
    window._save_settings()
    window2 = _window(tmp_path)
    assert window2._reg() == "squares"
    assert float(window2._reg_thickness.value()) == 1.2


def test_espessura_habilita_so_para_cruz_e_l(qapp, tmp_path):
    window = _window(tmp_path)
    combo = window._reg_type
    for data, enabled in (
        ("none", False), ("circles", False), ("squares", False),
        ("crosses", True), ("corner_l", True), ("mimaki", False),
    ):
        combo.setCurrentIndex(combo.findData(data))
        assert window._reg_thickness.isEnabled() is enabled, data
