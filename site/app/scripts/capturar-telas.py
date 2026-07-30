"""Captura telas reais do PrintNest para o site de vendas.

Nao altera nada do app: monta a MainWindow como o __main__ faz, usa um
config.json TEMPORARIO (copia do real) e salva PNGs em ./out, em 2x.

Como rodar (do repo, com o venv do projeto):
    .venv/Scripts/python.exe site/app/scripts/capturar-telas.py

Depois converta o que interessa para WebP e jogue em
site/app/public/assets/app/ (o Landing.tsx aponta para .webp).

Ajuste antes de rodar:
  REPO     -> raiz do repositorio
  DOWNLOADS-> pasta com as artes de amostra
  ARTES    -> arquivos e quantidades do job de demonstracao
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(r"c:\projetos\Cutph")
sys.path.insert(0, str(REPO))

os.environ["PYTEST_CURRENT_TEST"] = "shots"  # pula o tour de boas-vindas
os.environ.setdefault("QT_SCALE_FACTOR", "2")  # captura em 2x (retina)

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

DOWNLOADS = Path(r"C:\Users\Pc Fechamento\Downloads")

# artes neutras (sem marca de terceiros) da pasta do cliente
ARTES = [
    ("download (13).png", 4),
    ("download (12).png", 3),
    ("download (11).png", 3),
    ("download (10).png", 4),
    ("download (8).png", 3),
    ("download (7).png", 4),
    ("download (6).png", 4),
    ("download (5).png", 3),
    ("download (4).png", 3),
    ("download (3).png", 4),
    ("download (2).png", 3),
    ("download (1).png", 3),
    ("download.png", 3),
]
ARTES_ESCALA = [(n, q * 4) for n, q in ARTES]

from PySide6.QtCore import QElapsedTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

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
from app.presentation.main_window import ExportCenterDialog, MainWindow  # noqa: E402
from app.shared.config import AppPaths, SettingsStore  # noqa: E402

LOG = []

BASE_SETTINGS = {
    "material_width": 1250.0, "material_height": 2000.0,
    "spacing": 0.0, "spacing_v": 0.0, "offset": 2.0, "safety_inset": 0.0,
    "crop": 0.0, "rotation": 0, "shared_faca": False,
    "reg_type": "none", "reg_margin": 5.0, "reg_diameter": 5.0,
    "reg_thickness": 0.8, "mimaki_distance": 25.0, "mimaki_size": 15.0,
    "mimaki_thickness": 1.0, "show_rulers": True, "view_mode": "split_h",
    "import_box": "trim", "snap_enabled": True, "export_dpi": 500,
    "auto_sensitivity": 50.0, "auto_ignore_white": True,
    "auto_offset_external": 2.0, "auto_offset_internal": 0.0,
    "auto_smooth": 0, "faca_mode": "auto",
}


def make_project(name: str, artes, extra: dict | None = None) -> str:
    files = [
        {"path": str(DOWNLOADS / n).replace("\\", "/"), "quantity": q, "rotation": 0}
        for n, q in artes
        if (DOWNLOADS / n).exists()
    ]
    settings = dict(BASE_SETTINGS)
    settings.update(extra or {})
    doc = {
        "version": 1,
        "files": files,
        "settings": settings,
        # faca pelo CONTORNO real da arte (padrao de adesivo recortado)
        "file_overrides": {f["path"]: {"mode": "contour"} for f in files},
    }
    path = HERE / f"{name}.printnest"
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return str(path)


def build_window():
    paths = AppPaths.default().ensure()
    tmp = Path(tempfile.mkdtemp(prefix="printnest_shots_"))
    cfg = tmp / "config.json"
    if paths.config_file.exists():
        shutil.copy(paths.config_file, cfg)
    store = SettingsStore(cfg)
    settings = store.load_or_create()

    pipeline = RunProductionPipelineUseCase(
        ImportPdfUseCase(PdfiumImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(paths.cache_dir)),
    )
    win = MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PikePdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PdfiumPageRenderer(),
        store,
        settings,
    )
    win._dirty = False
    return win


APP = None


def pump(ms=600):
    t = QElapsedTimer()
    t.start()
    while t.elapsed() < ms:
        APP.processEvents()


def save(widget, name):
    pix = widget.grab()
    pix.save(str(OUT / name), "PNG")
    LOG.append(f"{name}  {pix.width()}x{pix.height()}")


def step(label, fn):
    try:
        fn()
    except Exception:  # noqa: BLE001
        LOG.append(f"!! {label}: {traceback.format_exc().splitlines()[-1]}")


def load(win, proj):
    win.open_project(proj)
    pump(1500)
    win.generate(blocking=True)
    pump(5000)
    win._organize()
    pump(4500)
    win._fit_view()
    pump(1500)


def set_mode(win, data):
    win._view_mode.setCurrentIndex(win._view_mode.findData(data))
    pump(1200)


def main():
    global APP
    from app.presentation.themes import apply_startup

    APP = QApplication(sys.argv)
    apply_startup(APP)

    win = build_window()
    win.resize(1760, 990)
    win.show()
    pump(800)

    # ---------- A. chapa cheia: tela dividida arte | faca ----------
    proj = make_project("amostra-stickers", ARTES, {"material_height": 0.0})
    load(win, proj)
    save(win, "a-tela-dividida.png")

    # ---------- B. impressao + corte sobrepostos ----------
    step("modo both", lambda: set_mode(win, "both"))
    save(win, "b-impressao-corte.png")

    # ---------- C. zoom no contorno (so a area de trabalho) ----------
    def zoom():
        from PySide6.QtCore import Qt

        rect = None
        for item in win._piece_items[:8]:
            r = item.sceneBoundingRect()
            rect = r if rect is None else rect.united(r)
        rect.adjust(-40, -40, 40, 40)
        win._view.fitInView(rect, Qt.KeepAspectRatio)
        pump(1500)
        save(win._view, "c-zoom-faca.png")

    step("zoom", zoom)

    # ---------- D. marcas de registro (corte otico) ----------
    def registro():
        set_mode(win, "split_h")
        win._reg_type.setCurrentIndex(win._reg_type.findData("circles"))
        pump(600)
        win._relayout(renest=False)
        pump(2500)
        win._fit_view()
        pump(1000)
        save(win, "d-registro.png")
        win._reg_type.setCurrentIndex(win._reg_type.findData("none"))
        pump(600)

    step("registro", registro)

    # ---------- E. Centro de Exportacao ----------
    def exportacao():
        dlg = ExportCenterDialog(win)
        dlg.resize(900, 620)
        dlg.show()
        pump(2500)
        save(dlg, "e-exportacao.png")
        dlg.close()
        pump(500)

    step("exportacao", exportacao)

    # ---------- F. Modo Corte (laser / CNC) ----------
    def modo_corte():
        from app.presentation.cut_mode_dialog import CutModeDialog

        dlg = CutModeDialog(win, export_dxf=win._dxf_export)
        dlg.resize(1180, 760)
        dlg.show()
        pump(800)
        font = r"C:\Windows\Fonts\arialbd.ttf"
        if not Path(font).exists():
            font = r"C:\Windows\Fonts\arial.ttf"
        for txt in ("PRINTNEST", "CORTE", "LASER", "CNC"):
            dlg.add_text(txt, font, 220.0)
            pump(400)
        dlg.nest()
        pump(14000)
        save(dlg, "f-modo-corte.png")
        dlg.close()
        pump(500)

    step("modo corte", modo_corte)

    # ---------- G. escala: muitas pecas, varias chapas ----------
    def escala():
        proj2 = make_project("amostra-escala", ARTES_ESCALA, {"material_height": 2000.0})
        load(win, proj2)
        set_mode(win, "print")
        win._fit_view()
        pump(1500)
        save(win, "g-escala.png")

    step("escala", escala)

    (HERE / "log.txt").write_text("\n".join(LOG), encoding="utf-8")
    APP.processEvents()
    os._exit(0)


if __name__ == "__main__":
    main()
