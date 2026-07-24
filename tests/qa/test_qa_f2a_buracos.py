"""FASE 2A (QA) — fecha os buracos de cobertura da Fase 1 (itens 1-5, 9-11
do inventario): substituir arquivo, alinhar D/T/B/centros, distribuir na
vertical, girar 4x90=identico, limpar guias, zoom F2/F3, Sobre/Licenca
(fumaca) e ausencia de atalhos ambiguos.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
from app.presentation import main_window as mw  # noqa: E402
from app.presentation.main_window import GuideItem, MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtGui import QAction, QShortcut  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


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
        page = doc.new_page(width=200, height=100)
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


# ---- 1) Substituir arquivo selecionado ----

def test_substituir_arquivo_selecionado_atualiza_producao(qapp, tmp_path, monkeypatch):
    # QA-F2A-04 / A1b, corrigido na F1: replace_selected() regenera a
    # producao (generate blocking) em vez de so relayoutar a geometria antiga.
    original = _two_page_pdf(tmp_path, "original")
    novo = _n_page_pdf(tmp_path, 3, name="novo")
    w = _window(tmp_path)
    w.add_paths([original])
    w.generate(blocking=True)
    assert sum(s.item_count for s in w._result.sheets) == 2

    w._table.setCurrentCell(0, 0)
    monkeypatch.setattr(mw.QFileDialog, "getOpenFileName", lambda *a, **k: (novo, ""))
    w.replace_selected()

    assert w._paths == [novo]
    assert w._table.item(0, 0).text().startswith("novo")
    # replace_selected deveria relayoutar sozinho com o conteudo do NOVO
    # arquivo (ja que a producao estava carregada) — hoje fica com o antigo.
    assert sum(s.item_count for s in w._result.sheets) == 3


def test_substituir_arquivo_so_atualiza_apos_gerar_de_novo(qapp, tmp_path, monkeypatch):
    # Documenta o comportamento ATUAL (nao e bug deste teste, e o
    # contorno do QA-F2A-04 acima): so um "Gerar Producao" completo depois
    # da troca busca o conteudo do arquivo novo.
    original = _two_page_pdf(tmp_path, "original")
    novo = _n_page_pdf(tmp_path, 3, name="novo")
    w = _window(tmp_path)
    w.add_paths([original])
    w.generate(blocking=True)

    w._table.setCurrentCell(0, 0)
    monkeypatch.setattr(mw.QFileDialog, "getOpenFileName", lambda *a, **k: (novo, ""))
    w.replace_selected()
    w.generate(blocking=True)  # contorno: gerar de novo busca o arquivo certo
    assert sum(s.item_count for s in w._result.sheets) == 3


def test_substituir_arquivo_cancelado_nao_muda_nada(qapp, tmp_path, monkeypatch):
    original = _two_page_pdf(tmp_path, "original")
    w = _window(tmp_path)
    w.add_paths([original])
    w.generate(blocking=True)
    w._table.setCurrentCell(0, 0)
    monkeypatch.setattr(mw.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    w.replace_selected()
    assert w._paths == [original]
    assert sum(s.item_count for s in w._result.sheets) == 2


# ---- 3) Alinhar D/T/B/centros (so "esquerda" tinha teste) ----

@pytest.mark.parametrize("mode,axis,edge", [
    ("right", "x", "right"),
    ("top", "y", "top"),
    ("bottom", "y", "bottom"),
    ("hcenter", "x", "center"),
    ("vcenter", "y", "center"),
])
def test_alinhar_direita_topo_base_e_centros(qapp, tmp_path, mode, axis, edge):
    src = _two_page_pdf(tmp_path)
    w = _window(tmp_path)
    w.add_paths([src])
    w.generate(blocking=True)
    a, b = w._piece_items[0], w._piece_items[1]
    b.setPos(b.x() + 37, b.y() + 21)
    a.setSelected(True)
    b.setSelected(True)
    w._align(mode)
    ra, rb = a.sceneBoundingRect(), b.sceneBoundingRect()
    if edge == "right":
        assert abs(ra.right() - rb.right()) < 0.1
    elif edge == "top":
        assert abs(ra.top() - rb.top()) < 0.1
    elif edge == "bottom":
        assert abs(ra.bottom() - rb.bottom()) < 0.1
    elif edge == "center" and axis == "x":
        assert abs(ra.center().x() - rb.center().x()) < 0.1
    elif edge == "center" and axis == "y":
        assert abs(ra.center().y() - rb.center().y()) < 0.1


# ---- 4) Distribuir na vertical (so horizontal tinha teste) ----

def test_distribuir_vertical_iguala_espacos(qapp, tmp_path):
    src = _n_page_pdf(tmp_path, 3)
    w = _window(tmp_path)
    w._width.setValue(400)
    w._height.setValue(3000)  # tudo cabe numa coluna
    w.add_paths([src])
    w.generate(blocking=True)
    ps = w._piece_items[:3]
    ps[0].setPos(0, 0)
    ps[1].setPos(0, 20)
    ps[2].setPos(0, 400)
    for p in ps:
        p.setSelected(True)
    w._distribute("v")
    rects = sorted((p.sceneBoundingRect() for p in ps), key=lambda r: r.top())
    gap1 = rects[1].top() - rects[0].bottom()
    gap2 = rects[2].top() - rects[1].bottom()
    assert abs(gap1 - gap2) < 0.5


# ---- 5) Limpar guias ----

def test_limpar_guias_remove_da_cena_e_do_estado(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w = _window(tmp_path)
    w.add_paths([src])
    w.generate(blocking=True)
    w._on_guide_dropped(True, 30.0, inside=True)
    w._on_guide_dropped(False, 40.0, inside=True)
    assert len(w._guides) == 2
    assert len([it for it in w._scene.items() if isinstance(it, GuideItem)]) == 2

    w._clear_guides()
    assert w._guides == []
    assert [it for it in w._scene.items() if isinstance(it, GuideItem)] == []


# ---- 2) Zoom F2/F3 muda a transformacao do canvas ----

def test_zoom_f2_f3_muda_a_escala_do_canvas(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w = _window(tmp_path)
    w.add_paths([src])
    w.generate(blocking=True)
    antes = w._view.transform().m11()
    w._zoom_step(1.25)  # F2 (zoom +)
    assert w._view.transform().m11() == pytest.approx(antes * 1.25, rel=1e-6)
    depois = w._view.transform().m11()
    w._zoom_step(1 / 1.25)  # F3 (zoom -), volta ao ponto de partida
    assert w._view.transform().m11() == pytest.approx(antes, rel=1e-6)
    assert depois != antes


# ---- 11) Girar 4x90 = arranjo identico ao original ----

def test_girar_peca_quatro_vezes_90_volta_ao_arranjo_original(qapp, tmp_path):
    src = _n_page_pdf(tmp_path, 2, w=80.0, h=50.0)
    w = _window(tmp_path)
    w._width.setValue(500)
    w._height.setValue(500)
    w.add_paths([src])
    w.generate(blocking=True)
    original = sorted(
        (round(i.position.x, 3), round(i.position.y, 3))
        for s in w._effective_sheets() for i in s.items
    )
    art_id = w._piece_items[0].artwork_id
    w._piece_items[0].setSelected(True)
    for _ in range(4):
        w._rotate_selected(90)
        w._reselect_by_artwork({art_id})
    assert w._piece_rotations.get(art_id, 0) % 360 == 0
    depois = sorted(
        (round(i.position.x, 3), round(i.position.y, 3))
        for s in w._effective_sheets() for i in s.items
    )
    assert depois == original


# ---- 9) Sobre / Licenca abrem e fecham (fumaca) ----

def test_sobre_e_licenca_abrem_e_fecham_sem_crash(qapp, tmp_path, monkeypatch):
    from app.presentation.licensing_dialog import ActivationDialog

    # QMessageBox.about() e um metodo de conveniencia que roda exec() dentro
    # do proprio Qt (C++); monkeypatch no exec() de instancia nao intercepta.
    # Troca o proprio "about" por um espiao: confirma que foi chamado (a
    # janela monta o texto/versao) sem abrir modal nenhum no offscreen.
    chamadas = []
    monkeypatch.setattr(
        QMessageBox, "about",
        staticmethod(lambda *a, **k: chamadas.append((a, k))),
    )
    monkeypatch.setattr(ActivationDialog, "exec", lambda self: 0)
    w = _window(tmp_path)
    w._show_about()
    assert chamadas, "Sobre nao chamou QMessageBox.about"
    w._show_license()


# ---- 10) Sem atalhos ambiguos (duas acoes na mesma tecla) ----

def test_sem_atalhos_de_teclado_ambiguos(qapp, tmp_path):
    w = _window(tmp_path)
    by_key: dict[str, list[str]] = {}
    for act in w.findChildren(QAction):
        seq = act.shortcut().toString()
        if seq:
            by_key.setdefault(seq, []).append(f"QAction:{act.text() or act.objectName()}")
    for sc in w.findChildren(QShortcut):
        seq = sc.key().toString()
        if seq:
            by_key.setdefault(seq, []).append(f"QShortcut:{sc.objectName() or id(sc)}")
    ambiguous = {k: v for k, v in by_key.items() if len(v) > 1}
    assert not ambiguous, f"atalhos duplicados: {ambiguous}"
