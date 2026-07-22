"""E1/Etapa 1 — peças de corte manipuláveis na área de trabalho (fundação).

Cobre as duas mudanças que tocam o fluxo de impressão:
1. Hit-test do PieceItem pelo CONTORNO real (furos vazados via OddEvenFill),
   EXCLUSIVO de peça vinda do Modo Corte (art.from_cut_mode). Arte de
   impressão — com OU sem faca — segue o retângulo de sempre, no mesmo
   caminho de código de antes (não-regressão explícita).
2. Rotação do PlacedItem sobrevivendo ao canvas: arrastar, desfazer/refazer
   e redesenhar não apagam mais o giro (antes _effective_sheets remontava o
   PlacedItem com 2 argumentos e o primeiro arraste zerava a rotação). Na
   IMPRESSÃO o giro continua com dono ÚNICO (_piece_rotations, assado na
   geometria): PlacedItem.rotation fica 0 e a exportação sai como antes.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import replace  # noqa: E402

import fitz  # noqa: E402
import pytest  # noqa: E402
from app.application.footprint import artwork_footprint  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase  # noqa: E402
from app.application.use_cases.import_image import ImportImageUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    ProductionResult,
    RunProductionPipelineUseCase,
)
from app.domain.geometry import Point2D, Size  # noqa: E402
from app.domain.model.artwork import ArtKind, Artwork, FileFormat  # noqa: E402
from app.domain.model.cut_contour import CutContour  # noqa: E402
from app.domain.model.layout import Layout  # noqa: E402
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pikepdf_print_exporter import (  # noqa: E402
    PikePdfPrintExporter,
)
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter  # noqa: E402
from app.infrastructure.importers.pdfium_importer import PdfiumImporter  # noqa: E402
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer  # noqa: E402
from app.presentation.main_window import (  # noqa: E402
    MainWindow,
    PieceItem,
    _piece_hit_path,
)
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsScene  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _square(x0, y0, x1, y1):
    return CutContour((
        Point2D(x0, y0), Point2D(x1, y0), Point2D(x1, y1), Point2D(x0, y1),
    ))


def _art(cut=None, extras=(), size=None, from_cut_mode=True):
    """Arte de teste. from_cut_mode=True por padrão porque estes testes
    exercitam o hit-test das peças do MODO CORTE; os de não-regressão da
    impressão passam False explicitamente."""
    return Artwork(
        id="a1", name="peça", file_format=FileFormat.PDF,
        size=size or Size(100.0, 100.0),
        kind=ArtKind.VETORIAL, cut_contour=cut, extra_cuts=tuple(extras),
        from_cut_mode=from_cut_mode,
    )


def _piece_na_cena(art):
    fp = artwork_footprint(art)
    piece = PieceItem(
        fp.max_x - fp.min_x, fp.max_y - fp.min_y,
        artwork_id=art.id, name=art.name, art_size=art.size,
        sheet_index=0, dx=0.0, dy=0.0, hit_path=_piece_hit_path(art, fp),
    )
    scene = QGraphicsScene()
    scene.addItem(piece)
    return scene, piece


def _hits(scene, x, y):
    return [it for it in scene.items(QPointF(x, y)) if isinstance(it, PieceItem)]


# ---- hit-test pelo contorno real -------------------------------------------


def test_clique_no_furo_nao_seleciona(qapp):
    # anel: contorno externo 100x100 com furo 40x40 no miolo (o "O")
    art = _art(cut=_square(0, 0, 100, 100), extras=[_square(30, 30, 70, 70)])
    scene, piece = _piece_na_cena(art)
    assert not _hits(scene, 50, 50)   # miolo do "O": vazado, NÃO seleciona
    assert _hits(scene, 50, 15)       # material do anel: seleciona
    assert _hits(scene, 15, 50)
    assert not _hits(scene, 150, 50)  # fora da peça
    # o bounding box NÃO muda (snap, alças e overlay seguem pela caixa)
    assert piece.boundingRect().width() == pytest.approx(100.0)
    assert piece.boundingRect().height() == pytest.approx(100.0)


def test_clique_fora_do_contorno_dentro_da_caixa_nao_seleciona(qapp):
    # faca triangular: o canto do bbox fica FORA do contorno
    tri = CutContour((Point2D(0, 0), Point2D(100, 0), Point2D(0, 100)))
    art = _art(cut=tri)
    scene, _piece = _piece_na_cena(art)
    assert _hits(scene, 20, 20)       # dentro do triângulo
    assert not _hits(scene, 90, 90)   # canto do bbox, fora do triângulo


def test_desenhos_separados_clicaveis_um_a_um(qapp):
    # folha com 2 desenhos disjuntos: cada um clicável; o VÃO entre eles não.
    # (DECISÃO E1/Etapa 1: o clique respeita o material de verdade — o vão
    # entre desenhos da mesma peça deixa de selecionar. O laço/rubber band e
    # o clique em qualquer desenho continuam selecionando a peça.)
    art = _art(cut=_square(0, 0, 40, 40), extras=[_square(60, 0, 100, 40)])
    scene, _piece = _piece_na_cena(art)
    assert _hits(scene, 20, 20)
    assert _hits(scene, 80, 20)
    assert not _hits(scene, 50, 20)   # vão entre os desenhos


def test_peca_sem_faca_continua_retangulo(qapp):
    # não-regressão explícita: sem cut_contour o hit path nem existe e o
    # comportamento é IDÊNTICO ao de hoje (clique em qualquer ponto da caixa).
    art = _art(cut=None)
    assert _piece_hit_path(art, artwork_footprint(art)) is None
    scene, piece = _piece_na_cena(art)
    assert _hits(scene, 50, 50)
    assert _hits(scene, 1, 99)
    assert piece.shape().boundingRect() == piece.rect()


def test_impressao_com_faca_segue_o_caminho_de_hoje(qapp):
    # NÃO-REGRESSÃO EXIGIDA (revisão 22/07): peça de IMPRESSÃO com faca — até
    # com faca furada, caso da faca do cliente em anel — NÃO ganha hit preciso.
    # O hit path nem é construído (from_cut_mode=False => None) e o PieceItem
    # cai no MESMO caminho de código de antes do E1: shape()/contains() do
    # QGraphicsRectItem, clique em qualquer ponto da caixa seleciona,
    # inclusive no miolo do furo.
    art = _art(cut=_square(0, 0, 100, 100), extras=[_square(30, 30, 70, 70)],
               from_cut_mode=False)
    assert _piece_hit_path(art, artwork_footprint(art)) is None
    scene, piece = _piece_na_cena(art)
    assert _hits(scene, 50, 50)   # miolo do furo: seleciona, como hoje
    assert _hits(scene, 95, 95)   # canto da caixa: seleciona, como hoje
    assert piece.shape().boundingRect() == piece.rect()


# ---- rotação sobrevivendo ao canvas ----------------------------------------


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


def _injeta_rotacao(window, graus):
    """Marca a 1a peça da 1a chapa com rotação livre (como o Modo Corte fará
    na Etapa 2) e redesenha o canvas."""
    first = window._result.sheets[0]
    items = list(first.items)
    items[0] = replace(items[0], rotation=graus)
    sheets = [Layout(first.material, items, first.used_length),
              *window._result.sheets[1:]]
    window._result = ProductionResult(
        sheets=sheets, artworks=window._result.artworks, sources=window._sources
    )
    window._draw_preview()
    return items[0].artwork_id


def test_rotacao_sobrevive_arrastar_desfazer_redesenhar(qapp, tmp_path):
    window = _window(tmp_path)
    window.add_paths([_two_page_pdf(tmp_path)])
    window.generate(blocking=True)
    aid = _injeta_rotacao(window, 45.0)

    # redesenhar a cena não perde o giro (PieceItem transporta placed_rotation)
    piece = next(p for p in window._piece_items if p.artwork_id == aid)
    assert float(piece.placed_rotation) == pytest.approx(45.0)

    # arrastar: o caminho canvas->modelo (_effective_sheets) preserva o giro
    x0 = piece.x()
    window._begin_move()
    piece.setPos(piece.x() + 100, piece.y() + 30)
    window._end_move()
    rots = {it.artwork_id: float(it.rotation)
            for s in window._effective_sheets() for it in s.items}
    assert rots[aid] == pytest.approx(45.0)

    # desfazer volta a posição SEM perder o giro; refazer idem
    window._undo.undo()
    piece = next(p for p in window._piece_items if p.artwork_id == aid)
    assert piece.x() == pytest.approx(x0)
    assert float(piece.placed_rotation) == pytest.approx(45.0)
    window._undo.redo()
    piece = next(p for p in window._piece_items if p.artwork_id == aid)
    assert piece.x() == pytest.approx(x0 + 100)
    assert float(piece.placed_rotation) == pytest.approx(45.0)


def test_duplicar_herda_a_rotacao(qapp, tmp_path):
    window = _window(tmp_path)
    window.add_paths([_two_page_pdf(tmp_path)])
    window.generate(blocking=True)
    aid = _injeta_rotacao(window, 90.0)

    piece = next(p for p in window._piece_items if p.artwork_id == aid)
    piece.setSelected(True)
    window._duplicate_selected()
    rots = [float(it.rotation)
            for s in window._effective_sheets() for it in s.items
            if it.artwork_id == aid]
    assert len(rots) == 2 and all(r == pytest.approx(90.0) for r in rots)


def _one_page_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)  # ~70.5 x 35.3 mm (deitada)
    page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "uma_pagina.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _bbox_preto(pixmap, limiar=50):
    """Bbox (px) dos pixels escuros de um fitz.Pixmap RGB."""
    xs, ys = [], []
    stride, n = pixmap.stride, pixmap.n
    for y in range(pixmap.height):
        row = pixmap.samples[y * stride:(y + 1) * stride]
        for x in range(pixmap.width):
            if row[x * n] < limiar:
                xs.append(x)
                ys.append(y)
    assert xs, "nenhum pixel escuro no PDF exportado"
    return min(xs), min(ys), max(xs), max(ys)


def test_exportacao_impressao_com_giro_90_sai_como_antes(qapp, tmp_path):
    # RISCO apontado na revisão de 22/07: o E1 passou a preencher
    # PlacedItem.rotation, e a exportação de impressão lê o giro de
    # _piece_rotations (_print_kwargs -> _rotation_of). Se algum ponto do
    # caminho de exportação passar a ler os DOIS, a peça sai girada DUAS
    # vezes. Este teste trava o comportamento anterior ao E1 de ponta a
    # ponta: giro global 90 + arraste (remonta os PlacedItems) + exportação,
    # medindo a GEOMETRIA do PDF final.
    window = _window(tmp_path)
    window._width.setValue(500)
    window._reg_type.setCurrentIndex(0)  # sem marcas: só a arte no render
    window.add_paths([_one_page_pdf(tmp_path)])
    window.generate(blocking=True)
    window._rotation.setCurrentText("90")  # giro global (caminho antigo)

    # arrasta: obriga o canvas a remontar os PlacedItems (_effective_sheets)
    piece = window._piece_items[0]
    window._begin_move()
    piece.setPos(piece.x() + 5, piece.y())
    window._end_move()

    # invariante do dono único do giro: na IMPRESSÃO o PlacedItem.rotation
    # fica 0 (o giro vive em _piece_rotations, assado na geometria) e o
    # kwargs de exportação segue lendo 90 do caminho de sempre.
    assert all(
        float(it.rotation) == 0.0
        for s in window._effective_sheets() for it in s.items
    )
    assert all(v == 90 for v in window._print_kwargs()["rotations"].values())

    out = tmp_path / "IMPRESSAO.pdf"
    window.export_pdf(str(out))
    doc = fitz.open(str(out))
    try:
        x0, y0, x1, y1 = _bbox_preto(doc[0].get_pixmap(dpi=36))
    finally:
        doc.close()
    # a página fonte é DEITADA (~70.5 x 35.3); girada 90 tem de sair EM PÉ
    # (alta > larga), com a proporção ~2:1 preservada. Girada DUAS vezes
    # (180) sairia deitada de novo — é exatamente o que este assert pega.
    w, h = x1 - x0 + 1, y1 - y0 + 1
    assert h > w
    assert h / w == pytest.approx(2.0, rel=0.1)


def test_arr_key_detecta_mudanca_so_de_rotacao(qapp, tmp_path):
    # girar sem sair do lugar TEM que contar como mudança de arranjo (senão o
    # movimento não entra no histórico e o Ctrl+Z pula o giro).
    window = _window(tmp_path)
    art_id = "x"
    from app.domain.model.material import Material
    from app.domain.model.placement import PlacedItem

    mat = Material(name="m", width=300.0)
    a = [Layout(mat, [PlacedItem(art_id, Point2D(10, 10))], 100.0)]
    b = [Layout(mat, [PlacedItem(art_id, Point2D(10, 10), 45.0)], 100.0)]
    assert window._arr_key(a) != window._arr_key(b)
    assert window._arr_key(a) == window._arr_key(
        [Layout(mat, [PlacedItem(art_id, Point2D(10, 10), 0.0)], 100.0)]
    )
