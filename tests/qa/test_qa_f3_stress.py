"""QA FASE 3 — comportamentos hostis sob estresse: PDF multipagina grande,
quantidade 999, duplicar em cadeia, undo/redo ao limite, zoom extremo.

Nesting esta CONGELADO (so bug = sobreposicao/perda/corte errado); aqui so
verificamos consistencia de estado, ausencia de excecao e tempo razoavel
(medido e reportado, sem meta rigida imposta pelo teste)."""

import math
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz  # noqa: E402
import pikepdf  # noqa: E402
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


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _window_cfg(tmp_path, name):
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


def _small_pdf(tmp_path, name="peca.pdf", w_mm=10.0, h_mm=10.0):
    pt = 72.0 / 25.4
    doc = fitz.open()
    page = doc.new_page(width=w_mm * pt, height=h_mm * pt)
    page.draw_rect(
        fitz.Rect(0, 0, w_mm * pt, h_mm * pt), color=(0, 0, 0), fill=(0, 0, 0)
    )
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


def _still_usable(w) -> None:
    assert w.isEnabled()
    w._toasts.info("sanity check")


# ---------------------------------------------------------------------------
# Caso 3: PDF multipagina grande (300 paginas) — mede tempo, nao trava
# ---------------------------------------------------------------------------

def test_pdf_multipagina_300_paginas_importa_em_tempo_razoavel(qapp, tmp_path):
    pdf = pikepdf.new()
    for _ in range(300):
        pdf.add_blank_page(page_size=(100, 100))
    path = tmp_path / "multi_300.pdf"
    pdf.save(str(path))

    w = _window_cfg(tmp_path, "w_multi")
    w.add_paths([str(path)])
    t0 = time.monotonic()
    w.generate(blocking=True)
    elapsed = time.monotonic() - t0

    assert w._result is not None
    assert sum(s.item_count for s in w._result.sheets) == 300
    _still_usable(w)
    # MEDICAO (nao meta formal): reportar se ficar bem lento.
    if elapsed > 20.0:
        pytest.xfail(
            f"QA-F3-03 (MEDICAO): 300 paginas levaram {elapsed:.1f}s para "
            "gerar (> 20s) — investigar custo por pagina em generate()."
        )


# ---------------------------------------------------------------------------
# Caso 9: quantidade 999 numa peca pequena em chapa pequena
# ---------------------------------------------------------------------------

def test_quantidade_999_peca_pequena_chapa_pequena(qapp, tmp_path):
    src = _small_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w_qty")
    w.add_paths([src])
    w._width.setValue(200.0)  # chapa pequena: 200mm de largura
    w.generate(blocking=True)
    assert w._result is not None

    spin = w._table.cellWidget(0, 1)
    assert spin is not None
    t0 = time.monotonic()
    spin.setValue(999)  # dispara _relayout(from_table=True) via valueChanged
    elapsed = time.monotonic() - t0

    total = sum(s.item_count for s in w._result.sheets)
    assert total == 999, f"esperava 999 pecas encaixadas, saiu {total}"
    assert len(w._result.sheets) >= 1
    _still_usable(w)
    if elapsed > 20.0:
        pytest.xfail(
            f"QA-F3-09 (MEDICAO): qtd=999 numa chapa pequena levou {elapsed:.1f}s "
            "(> 20s) para reencaixar — investigar custo do nesting em lote."
        )


# ---------------------------------------------------------------------------
# Caso 10: duplicar em cadeia (Ctrl+D x 50) — estado consistente, undo volta tudo
# ---------------------------------------------------------------------------

def test_duplicar_em_cadeia_50x_estado_consistente_e_undo_completo(qapp, tmp_path):
    src = _small_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w_dup")
    w.add_paths([src])
    w.generate(blocking=True)
    assert w._result is not None

    inicial = sum(s.item_count for s in w._result.sheets)
    assert inicial == 1
    estado0 = w._state_snapshot()

    piece = w._piece_items[0]
    piece.setSelected(True)
    for _ in range(50):
        w._duplicate_selected()  # Ctrl+D em cadeia: a copia vira a selecao

    total_depois = sum(s.item_count for s in w._result.sheets)
    assert total_depois == inicial + 50

    # 50 comandos distintos na pilha (cada Ctrl+D e um passo proprio)
    for _ in range(50):
        assert w._undo.canUndo()
        w._undo.undo()
    assert sum(s.item_count for s in w._result.sheets) == inicial
    assert w._state_snapshot() == estado0  # estado final == estado inicial

    for _ in range(50):
        assert w._undo.canRedo()
        w._undo.redo()
    assert sum(s.item_count for s in w._result.sheets) == total_depois
    _still_usable(w)


# ---------------------------------------------------------------------------
# Caso 11: undo/redo ao limite — 100 operacoes mistas, ida e volta sem excecao
# ---------------------------------------------------------------------------

def test_undo_redo_100_operacoes_mistas_ida_e_volta_sem_excecao(qapp, tmp_path, monkeypatch):
    import app.presentation.main_window as mw
    # cada operacao vira um passo PROPRIO (sem fundir por "mesmo gesto rapido")
    monkeypatch.setattr(mw, "_MERGE_WINDOW_S", -1.0)

    src = _small_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w_undo100")
    w.add_paths([src])
    w.generate(blocking=True)
    assert w._result is not None
    estado0 = w._state_snapshot()

    offset_base = float(w._offset.value())
    for i in range(100):
        op = i % 4
        # Reseleciona SEMPRE so a peca[0]: _rotate_selected re-seleciona TODAS
        # as copias que compartilham o mesmo artwork_id (QA-F3-11b, achado a
        # parte) — sem isso a selecao cresce e duplicar vira exponencial.
        w._scene.clearSelection()
        if w._piece_items:
            w._piece_items[0].setSelected(True)
        if op == 0:
            w._nudge(1.0, 0.0)
        elif op == 1:
            w._rotate_selected(90)
        elif op == 2:
            w._duplicate_selected()
        else:
            w._offset.setValue(offset_base + (i % 5) * 0.1)

    estado_final = w._state_snapshot()

    desfeitos = 0
    while w._undo.canUndo():
        w._undo.undo()
        desfeitos += 1
    assert desfeitos > 0
    assert w._state_snapshot() == estado0, "undo ate o fundo tem que voltar ao estado inicial"

    refeitos = 0
    while w._undo.canRedo():
        w._undo.redo()
        refeitos += 1
    assert refeitos == desfeitos
    assert w._state_snapshot() == estado_final, "redo ate o topo tem que restaurar o estado final"
    _still_usable(w)


@pytest.mark.xfail(
    strict=False,
    reason=(
        "QA-F3-11b (achado ao montar o teste de undo/redo misto): girar uma "
        "peca DUPLICADA re-seleciona TODAS as copias com o mesmo artwork_id "
        "(_reselect_by_artwork em main_window.py ~7474, chamado por "
        "_rotate_selected ~7464). Se o usuario, depois de girar, apertar "
        "Ctrl+D de novo (_duplicate_selected duplica TODAS as selecionadas, "
        "~7140), a quantidade de pecas DOBRA a cada ciclo girar+duplicar em "
        "vez de +1 -- 3 ciclos = 8x a peca original, sem aviso. Risco de "
        "quantidade de producao muito maior que o pretendido pelo usuario."
    ),
)
def test_girar_depois_duplicar_nao_deveria_multiplicar_todas_as_copias(qapp, tmp_path):
    src = _small_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w_rot_dup")
    w.add_paths([src])
    w.generate(blocking=True)
    assert len(w._piece_items) == 1

    w._piece_items[0].setSelected(True)
    w._duplicate_selected()
    assert len(w._piece_items) == 2  # 1 copia a mais, como esperado

    w._rotate_selected(90)  # gira a copia recem-criada (unica selecionada)
    selecionadas = len(w._scene.selectedItems())
    # esperado (visao do usuario): girar 1 peca continua com 1 selecionada.
    assert selecionadas == 1, (
        f"girar re-selecionou {selecionadas} peca(s) em vez de 1 "
        "(todas as copias do mesmo artwork_id)"
    )

    w._duplicate_selected()
    total = len(w._piece_items)
    # esperado: +1 copia (o usuario pediu 1 Ctrl+D). Com o bug, dobra (+2).
    assert total == 3, f"esperava 3 pecas (2 + 1 copia), saiu {total}"
    _still_usable(w)


# ---------------------------------------------------------------------------
# Caso 15: zoom extremo em loop — nao trava, transform nao vira NaN/Inf
# ---------------------------------------------------------------------------

def test_zoom_extremo_nao_gera_nan_nem_trava(qapp, tmp_path):
    src = _small_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w_zoom")
    w.add_paths([src])
    w.generate(blocking=True)

    for _ in range(500):
        w._zoom_step(1.15)  # zoom + repetido (F2 seguro)
    zoom_alto = w._view.zoom_factor()
    assert math.isfinite(zoom_alto), "zoom + repetido gerou transform nao finito"

    for _ in range(500):
        w._zoom_step(1 / 1.15)  # zoom - repetido (F3 segurado, volta e passa)
    zoom_baixo = w._view.zoom_factor()
    assert math.isfinite(zoom_baixo), "zoom - repetido gerou transform nao finito"
    assert zoom_baixo > 0, "escala nao pode virar negativa/zero"
    _still_usable(w)


def test_zoom_extremo_nao_ha_clamp_min_max(qapp, tmp_path):
    """Suspeita por codigo confirmada: _zoom_step (main_window.py ~linha 6772)
    e MainWindowView.wheelEvent (main_window.py ~linha 326) chamam
    self._view.scale(factor, factor) SEM nenhum clamp de minimo/maximo. Em
    uso real (segurar F2 ou rodar a roda do mouse por muito tempo) o zoom
    pode crescer sem limite. Aqui provamos com MUITAS repeticoes que o valor
    ultrapassa qualquer proporcao util (nao trava nem vira NaN em poucos
    milhares de passos, mas o software permite uma escala absurda)."""
    src = _small_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w_zoom_clamp")
    w.add_paths([src])
    w.generate(blocking=True)

    for _ in range(2000):
        w._zoom_step(1.15)
    zoom = w._view.zoom_factor()
    assert math.isfinite(zoom)
    if zoom > 1e6:
        pytest.xfail(
            f"QA-F3-15: sem clamp de zoom maximo, 2000 zooms + chegaram a "
            f"{zoom:.3e}x (main_window.py _zoom_step ~6772 e "
            "MainWindowView.wheelEvent ~326 nao limitam a escala)."
        )
