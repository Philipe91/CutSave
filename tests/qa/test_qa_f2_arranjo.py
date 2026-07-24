"""QA F2 — A0: persistência do arranjo manual no .printnest (casos de borda).

Os dois casos principais (duplicar+mover e girar peça sobrevivem ao
salvar/reabrir) estão em test_qa_f2a_roundtrip.py (ex-xfail QA-F2A-01/02).
Aqui ficam as bordas do campo aditivo "arranjo":
- projeto ANTIGO (sem o campo) abre exatamente como hoje;
- assinatura inválida (arquivos/quantidades mudaram) -> regenera e avisa;
- roundtrip sem retoque manual exporta DXF idêntico;
- Resetar arranjo continua funcionando depois do restore.
"""

import json
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


def _capture_toasts(w, monkeypatch):
    """Troca os toasts por listas: (warnings, infos) para afirmar avisos."""
    warnings: list = []
    infos: list = []
    monkeypatch.setattr(w._toasts, "warning", lambda msg: warnings.append(msg))
    monkeypatch.setattr(w._toasts, "info", lambda msg: infos.append(msg))
    return warnings, infos


def _dxf_bboxes(path):
    boxes = []
    for poly in ezdxf.readfile(path).modelspace().query("LWPOLYLINE"):
        pts = poly.get_points()
        xs = [round(p[0], 2) for p in pts]
        ys = [round(p[1], 2) for p in pts]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    return sorted(boxes)


# ---- projeto ANTIGO (sem o campo "arranjo") abre exatamente como hoje ----

def test_projeto_antigo_sem_campo_arranjo_abre_igual(qapp, tmp_path, monkeypatch):
    src = _two_page_pdf(tmp_path)
    w1 = _window(tmp_path, "w1")
    w1.add_paths([src])
    w1.generate(blocking=True)
    proj = tmp_path / "antigo.printnest"
    assert w1.save_project(str(proj)) is True

    # simula um .printnest de versao ANTIGA do app: remove o campo novo
    data = json.loads(proj.read_text(encoding="utf-8"))
    data.pop("arranjo", None)
    proj.write_text(json.dumps(data), encoding="utf-8")

    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    warnings, infos = _capture_toasts(w2, monkeypatch)
    w2.generate(blocking=True)

    # comportamento de hoje: nesting automatico da tabela, SEM aviso nenhum
    assert sum(s.item_count for s in w2._result.sheets) == 2
    assert not any("rranjo" in m for m in warnings + infos)
    assert w2._piece_rotations == {}


# ---- assinatura invalida (biblioteca mudou) -> regenera e avisa 1 toast ----

def test_assinatura_invalida_regenera_e_avisa(qapp, tmp_path, monkeypatch):
    src = _two_page_pdf(tmp_path)
    w1 = _window(tmp_path, "w1")
    w1.add_paths([src])
    w1.generate(blocking=True)
    w1._piece_items[0].setSelected(True)
    w1._duplicate_selected()  # arranjo manual: 3 pecas
    proj = tmp_path / "mudou.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    # o usuario muda a QUANTIDADE depois de abrir: assinatura nao bate mais
    w2._table.cellWidget(0, 1).setValue(3)
    warnings, _ = _capture_toasts(w2, monkeypatch)
    w2.generate(blocking=True)

    # fallback = encaixe automatico da tabela (2 paginas x 3), nunca o salvo
    assert sum(s.item_count for s in w2._result.sheets) == 6
    assert any("Arranjo salvo não pôde ser aplicado" in m for m in warnings)
    # o pendente foi consumido: gerar de novo nao repete o aviso
    warnings.clear()
    w2.generate(blocking=True)
    assert not warnings


# ---- roundtrip SEM retoque manual: exportacao identica antes/depois ----

def test_roundtrip_sem_retoque_exporta_dxf_identico(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w1 = _window(tmp_path, "w1")
    w1.add_paths([src])
    w1.generate(blocking=True)
    dxf1 = tmp_path / "antes.dxf"
    w1.export_dxf(str(dxf1))
    proj = tmp_path / "puro.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    w2.generate(blocking=True)
    dxf2 = tmp_path / "depois.dxf"
    w2.export_dxf(str(dxf2))

    # mesmo arranjo salvo restaurado -> geometria do DXF identica
    assert _dxf_bboxes(str(dxf2)) == _dxf_bboxes(str(dxf1))


# ---- Resetar arranjo continua funcionando depois do restore ----

def test_resetar_arranjo_continua_funcionando_apos_restore(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w1 = _window(tmp_path, "w1")
    w1.add_paths([src])
    w1.generate(blocking=True)
    w1._piece_items[0].setSelected(True)
    w1._duplicate_selected()
    proj = tmp_path / "reset.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    w2.generate(blocking=True)
    assert sum(s.item_count for s in w2._result.sheets) == 3  # restaurado

    w2._reset_arrangement()  # descarta o retoque: volta a tabela (2 paginas)
    assert sum(s.item_count for s in w2._result.sheets) == 2
