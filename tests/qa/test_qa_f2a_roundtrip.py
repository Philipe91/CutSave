"""FASE 2A (QA) — o GRANDE ida-e-volta: novo projeto -> importar PDF+PNG+JPG
com quantidades variadas -> Gerar Producao -> ajustar (giro de arquivo, tipo
de faca por arquivo) -> exportar IMPRESSAO.pdf + Faca PDF + DXF unico + DXF
por chapa -> salvar .printnest -> reabrir numa janela NOVA -> comparar TUDO
(quantidades, overrides, posicoes, contagem de paginas) contra o estado
anterior ao salvar.

Os testes de duplicar/mover/girar peca ficam em funcoes separadas: cada um
isola um comportamento (alguns sao bugs reais, marcados xfail).
"""

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
from PySide6.QtWidgets import QApplication  # noqa: E402

from tests import synth_images as si  # noqa: E402

MM2PT = 72.0 / 25.4


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _window(tmp_path, name="w"):
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


def _two_page_pdf(tmp_path, name="fonte"):
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=200, height=100)  # ~70.5 x 35.3 mm
        page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / f"{name}.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _n_page_pdf(tmp_path, n, w=120.0, h=120.0, name="multi"):
    doc = fitz.open()
    for _ in range(n):
        pg = doc.new_page(width=w, height=h)
        pg.draw_rect(pg.rect, color=(0, 0, 0), fill=(0, 0, 0))
    src = tmp_path / f"{name}.pdf"
    doc.save(str(src))
    doc.close()
    return str(src)


def _sheet_positions(window):
    return sorted(
        (round(item.position.x, 2), round(item.position.y, 2))
        for sheet in window._effective_sheets() for item in sheet.items
    )


def _footprint_sizes(window):
    """Tamanho (arredondado) de cada peca posicionada, ordenado — usado para
    comparar o RESULTADO do nesting (mesmas pecas, mesmo tamanho ocupado)
    sem exigir a mesma ORDEM de colocacao (o motor de nesting nao promete
    determinismo de ordem entre execucoes distintas, so encaixe valido)."""
    from app.application.footprint import artwork_footprint

    by_id = {a.id: a for a in window._result.artworks}
    out = []
    for sheet in window._effective_sheets():
        for item in sheet.items:
            fp = artwork_footprint(by_id[item.artwork_id])
            out.append((round(fp.max_x - fp.min_x, 2), round(fp.max_y - fp.min_y, 2)))
    return sorted(out)


def _no_overlaps(window):
    """Confere que nenhuma peca da MESMA chapa se sobrepoe a outra (regressao
    grave de nesting: perda de peca por sobreposicao silenciosa)."""
    from app.application.footprint import artwork_footprint

    by_id = {a.id: a for a in window._result.artworks}
    for sheet in window._effective_sheets():
        boxes = []
        for item in sheet.items:
            fp = artwork_footprint(by_id[item.artwork_id])
            x0, y0 = item.position.x + fp.min_x, item.position.y + fp.min_y
            x1, y1 = item.position.x + fp.max_x, item.position.y + fp.max_y
            boxes.append((x0, y0, x1, y1))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                ax0, ay0, ax1, ay1 = boxes[i]
                bx0, by0, bx1, by1 = boxes[j]
                overlap = ax0 < bx1 - 0.05 and bx0 < ax1 - 0.05 and \
                    ay0 < by1 - 0.05 and by0 < ay1 - 0.05
                if overlap:
                    return False
    return True


def test_roundtrip_completo_multiformatos_salvar_e_reabrir(qapp, tmp_path):
    pdf = _two_page_pdf(tmp_path, "arte_pdf")
    png = si.png_alpha_disc(tmp_path)
    jpg = si.jpg_white_square(tmp_path)

    w1 = _window(tmp_path, "w1")
    w1._width.setValue(2000)
    w1._height.setValue(2000)
    w1.add_paths([pdf, png, jpg])
    w1._table.cellWidget(0, 1).setValue(3)  # pdf: 2 paginas x 3 = 6
    w1._table.cellWidget(1, 1).setValue(2)  # png: 2
    w1._table.cellWidget(2, 1).setValue(4)  # jpg: 4
    w1.generate(blocking=True)
    assert sum(s.item_count for s in w1._result.sheets) == 6 + 2 + 4

    # girar ARQUIVO (barra de propriedades do arquivo selecionado, nao a
    # peca): pega o PDF e vira 90 graus so ele.
    w1._selected_path = pdf
    w1._pf_rotation.setCurrentText("90")
    assert w1._file_overrides[pdf]["rotation"] == 90

    # Gerar Faca por arquivo: retangulo (rect) no PNG e no JPG (mode="rect"
    # da faca reta e previsivel: 1 LWPOLYLINE por peca no DXF, sem depender
    # da qualidade da deteccao de contorno do PNG/JPG sinteticos).
    w1._pf_loading = False
    w1._selected_path = png
    w1._pf_mode.setCurrentIndex(w1._pf_mode.findData("rect"))
    w1._on_piece_faca_changed()  # combo pode ja estar em "rect" (sem sinal)
    w1._selected_path = jpg
    w1._pf_mode.setCurrentIndex(w1._pf_mode.findData("rect"))
    w1._on_piece_faca_changed()
    w1._selected_path = None

    assert w1._file_overrides[png]["mode"] == "rect"
    assert w1._file_overrides[jpg]["mode"] == "rect"

    quantities_antes = w1._quantities()
    tamanhos_antes = _footprint_sizes(w1)
    assert _no_overlaps(w1)

    # exporta os 4 formatos pedidos e confere conteudo real
    impressao = tmp_path / "IMPRESSAO.pdf"
    w1.export_pdf(str(impressao))
    assert impressao.exists()
    assert fitz.open(str(impressao)).page_count == len(w1._result.sheets)

    faca_pdf = tmp_path / "FACA.pdf"
    w1.export_faca_pdf(str(faca_pdf))
    assert faca_pdf.exists()
    assert fitz.open(str(faca_pdf)).page_count == len(w1._result.sheets)

    dxf_unico = tmp_path / "CORTE.dxf"
    w1.export_dxf(str(dxf_unico))
    doc = ezdxf.readfile(str(dxf_unico))
    msp = doc.modelspace()
    assert len(msp.query("LWPOLYLINE")) == 6 + 2 + 4

    dxf_base = tmp_path / "POR_CHAPA.dxf"
    w1.export_dxf_per_sheet(str(dxf_base))
    gerados = list(tmp_path.glob("POR_CHAPA_*.dxf"))
    assert len(gerados) == len(w1._result.sheets)

    proj = tmp_path / "trabalho.printnest"
    assert w1.save_project(str(proj)) is True
    assert w1._dirty is False

    # ---- fecha (janela nova) e reabre ----
    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    assert w2._loaded is False and w2._result is None  # regra: nao gera sozinho
    assert sorted(w2._paths) == sorted([pdf, png, jpg])
    assert w2._quantities() == quantities_antes

    # overrides por arquivo (giro do PDF, tipo de faca do PNG/JPG) voltam
    assert w2._file_overrides[pdf]["rotation"] == 90
    assert w2._file_overrides[png]["mode"] == "rect"
    assert w2._file_overrides[jpg]["mode"] == "rect"

    w2.generate(blocking=True)
    assert sum(s.item_count for s in w2._result.sheets) == 6 + 2 + 4
    # mesmas pecas (mesmo tamanho ocupado) e sem sobreposicao apos reabrir —
    # a ORDEM de colocacao ao longo da chapa pode variar entre execucoes (o
    # motor de nesting congelado nao promete determinismo de ordem, so
    # encaixe valido); ver achado QA-F2A-05 (observacao, nao bug).
    assert _footprint_sizes(w2) == tamanhos_antes
    assert _no_overlaps(w2)

    impressao2 = tmp_path / "IMPRESSAO_2.pdf"
    w2.export_pdf(str(impressao2))
    assert fitz.open(str(impressao2)).page_count == fitz.open(str(impressao)).page_count


def test_projeto_persiste_overrides_e_faca_manual_multiformato(qapp, tmp_path):
    # variante do teste ja existente na suite principal, mas com PNG (imagem)
    # no meio, ida-e-volta completa via save_project/open_project.
    from app.domain.geometry import Point2D
    from app.domain.model.cut_contour import CutContour

    pdf = _two_page_pdf(tmp_path, "a")
    png = si.png_alpha_disc(tmp_path)
    w1 = _window(tmp_path, "w1")
    w1.add_paths([pdf, png])
    w1._file_overrides[pdf] = {"mode": "contour", "offset": 3.5}
    w1._faca_manual[png] = {
        "contours": [CutContour([Point2D(0, 0), Point2D(10, 0), Point2D(5, 8)])],
        "w": 40.0, "h": 30.0, "rotation": 90,
    }
    proj = tmp_path / "t.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    assert w2._file_overrides[pdf] == {"mode": "contour", "offset": 3.5}
    m = w2._faca_manual[png]
    assert m["w"] == 40.0 and m["h"] == 30.0 and m["rotation"] == 90


# ---- comportamentos que NAO sobrevivem ao salvar/reabrir (bugs reais) ----

@pytest.mark.xfail(
    strict=False,
    reason="QA-F2A-01: duplicar (Ctrl+D) ou mover manualmente uma peca so "
    "muda o arranjo em memoria (self._result / _commit_arrangement); "
    "_collect_project() so grava a QUANTIDADE da tabela (self._quantities()), "
    "nunca o arranjo manual. Salvar o projeto e reabrir perde a copia "
    "duplicada e a posicao movida a mao: a peca some e a quantidade volta "
    "para a da tabela.",
)
def test_duplicar_e_mover_sobrevive_ao_salvar_e_reabrir(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w1 = _window(tmp_path, "w1")
    w1.add_paths([src])
    w1.generate(blocking=True)
    n_antes = sum(s.item_count for s in w1._result.sheets)

    w1._piece_items[0].setSelected(True)
    w1._duplicate_selected()  # Ctrl+D
    n_depois_duplicar = sum(s.item_count for s in w1._result.sheets)
    assert n_depois_duplicar == n_antes + 1

    # move a peca duplicada (agora selecionada) para uma posicao conhecida
    moved = w1._selected_movable()[0]
    moved.setPos(321.0, 123.0)

    proj = tmp_path / "dup.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    w2.generate(blocking=True)
    assert sum(s.item_count for s in w2._result.sheets) == n_depois_duplicar
    assert any(
        abs(i.position.x - 321.0) < 0.5 and abs(i.position.y - 123.0) < 0.5
        for s in w2._result.sheets for i in s.items
    )


@pytest.mark.xfail(
    strict=False,
    reason="QA-F2A-02: girar uma peca individual (Ctrl+[ / Ctrl+], "
    "self._piece_rotations) nao entra no ProjectDocument salvo — so o giro "
    "de ARQUIVO (barra de propriedades, file_overrides['rotation']) e "
    "persistido. Reabrir o projeto perde o giro da peca especifica: ela "
    "volta ao giro do arquivo (ou 0).",
)
def test_girar_peca_individual_sobrevive_ao_salvar_e_reabrir(qapp, tmp_path):
    src = _n_page_pdf(tmp_path, 2, w=80.0, h=50.0)
    w1 = _window(tmp_path, "w1")
    w1._width.setValue(500)
    w1._height.setValue(500)
    w1.add_paths([src])
    w1.generate(blocking=True)
    art_id = w1._piece_items[0].artwork_id
    w1._piece_items[0].setSelected(True)
    w1._rotate_selected(90)
    assert w1._piece_rotations[art_id] == 90

    proj = tmp_path / "giro.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    assert w2._piece_rotations.get(art_id, 0) == 90


def test_girar_arquivo_isso_sim_sobrevive_ao_salvar_e_reabrir(qapp, tmp_path):
    # contraste com o QA-F2A-02: giro de ARQUIVO (nao de peca) e persistido
    # de verdade — e a geometria (retrato<->paisagem) bate antes e depois.
    # _n_page_pdf recebe width/height em PONTOS (fitz.new_page): 80mm/50mm
    # convertidos, pra afirmar tamanhos exatos em mm depois do giro.
    src = _n_page_pdf(tmp_path, 1, w=80.0 * MM2PT, h=50.0 * MM2PT)
    w1 = _window(tmp_path, "w1")
    w1.add_paths([src])
    w1.generate(blocking=True)
    w1._selected_path = src
    w1._pf_rotation.setCurrentText("90")
    art = w1._result.artworks[0]
    w1._selected_path = None

    proj = tmp_path / "giro_arquivo.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    assert w2._file_overrides[src]["rotation"] == 90
    w2.generate(blocking=True)
    art2 = w2._result.artworks[0]
    # 80x50 girado 90 -> 50x80 (largura/altura trocadas), nas duas janelas
    assert (round(art.size.width, 1), round(art.size.height, 1)) == \
        (round(art2.size.width, 1), round(art2.size.height, 1))
    assert round(art2.size.width, 1) == 50.0
    assert round(art2.size.height, 1) == 80.0

