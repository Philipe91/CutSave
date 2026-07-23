"""FASE 2A (QA) — marcas de registro A2/A3 ponta-a-ponta: cada tipo do combo
(none, circles, mimaki, both, squares, crosses, corner_l) tem que descrever a
MESMA marca fisica no preview (cena), no PDF de impressao exportado e no DXF
de corte exportado — em COORDENADAS REAIS (mm), lendo os arquivos gerados de
verdade (fitz/ezdxf/pikepdf), nao so contando entidades.

O PDF de impressao soma um `pad` (window._faca_pad()) porque a pagina cresce
para caber as marcas; o DXF e o preview (cena) trabalham nas coordenadas CRUAS
da chapa (sem pad). Por isso toda comparacao PDF<->DXF/preview soma/subtrai
esse pad antes de comparar.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
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
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
)

PT2MM = 25.4 / 72.0
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


def _tiny_pdf(tmp_path, w=40.0, h=30.0, name="peca.pdf"):
    # AZUL (nao preto): get_drawings() do PDF exportado enxerga o conteudo do
    # Form XObject da arte tambem (MuPDF resolve o 'Do' ao tracar a pagina) —
    # se a arte fosse preta ela se disfarçaria de marca de registro preta.
    doc = fitz.open()
    page = doc.new_page(width=w * MM2PT, height=h * MM2PT)
    page.draw_rect(page.rect, color=(0.2, 0.3, 0.9), fill=(0.2, 0.3, 0.9))
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


def _reg_window(tmp_path, reg_type, margin=15.0, size=6.0, thickness=0.8, cfg="w"):
    w = _window(tmp_path, cfg)
    w._width.setValue(300.0)
    w._height.setValue(300.0)
    w.add_paths([_tiny_pdf(tmp_path)])
    w._reg_type.setCurrentIndex(w._reg_type.findData(reg_type))
    w._reg_margin.setValue(margin)
    w._reg_diameter.setValue(size)
    w._reg_thickness.setValue(thickness)
    w.generate(blocking=True)
    return w


# ---- extracao do PREVIEW (cena) ----

def _preview_ellipses(w):
    return sorted(
        (round(e.rect().center().x(), 4), round(e.rect().center().y(), 4),
         round(e.rect().width(), 4))
        for e in w._scene.items() if isinstance(e, QGraphicsEllipseItem)
    )


def _preview_reg_rects(w, size):
    return sorted(
        (round(r.rect().center().x(), 4), round(r.rect().center().y(), 4),
         round(r.rect().width(), 4))
        for r in w._scene.items()
        if type(r) is QGraphicsRectItem
        and abs(r.rect().width() - size) < 0.05
        and abs(r.rect().height() - size) < 0.05
    )


def _preview_lines(w):
    return sorted(
        (round(ln.line().x1(), 4), round(ln.line().y1(), 4),
         round(ln.line().x2(), 4), round(ln.line().y2(), 4))
        for ln in w._scene.items() if type(ln) is QGraphicsLineItem
    )


# ---- extracao do PDF exportado (fitz) ----

def _pdf_filled_black(path):
    doc = fitz.open(path)
    out = []
    for d in doc[0].get_drawings():
        fill = d.get("fill")
        if fill is not None and max(fill) < 0.05:
            r = d["rect"]
            out.append((
                round((r.x0 + r.x1) / 2 * PT2MM, 3),
                round((r.y0 + r.y1) / 2 * PT2MM, 3),
                round((r.x1 - r.x0) * PT2MM, 3),
            ))
    doc.close()
    return sorted(out)


def _pdf_stroked_black_lines(path):
    doc = fitz.open(path)
    out = []
    for d in doc[0].get_drawings():
        color = d.get("color")
        if color is None or max(color) >= 0.05 or d.get("fill") is not None:
            continue
        width_mm = (d.get("width") or 0.0) * PT2MM
        for item in d.get("items", []):
            if item[0] == "l":
                p0, p1 = item[1], item[2]
                out.append((
                    round(p0.x * PT2MM, 3), round(p0.y * PT2MM, 3),
                    round(p1.x * PT2MM, 3), round(p1.y * PT2MM, 3),
                    round(width_mm, 4),
                ))
    doc.close()
    return sorted(out)


# ---- extracao do DXF exportado (ezdxf) ----

def _dxf_circles(path):
    doc = ezdxf.readfile(path)
    return sorted(
        (round(c.dxf.center.x, 3), round(c.dxf.center.y, 3), round(c.dxf.radius * 2, 3))
        for c in doc.modelspace().query("CIRCLE")
    )


def _dxf_regmark_squares(path):
    doc = ezdxf.readfile(path)
    out = []
    for p in doc.modelspace().query("LWPOLYLINE"):
        if p.dxf.layer != "REGMARK":
            continue
        pts = list(p.get_points())
        xs = [pt[0] for pt in pts]
        ys = [pt[1] for pt in pts]
        out.append((
            round((min(xs) + max(xs)) / 2, 3), round((min(ys) + max(ys)) / 2, 3),
            round(max(xs) - min(xs), 3),
        ))
    return sorted(out)


def _dxf_regmark_lines(path):
    doc = ezdxf.readfile(path)
    out = []
    for ln in doc.modelspace().query("LINE"):
        if ln.dxf.layer == "REGMARK":
            out.append((
                round(ln.dxf.start.x, 3), round(ln.dxf.start.y, 3),
                round(ln.dxf.end.x, 3), round(ln.dxf.end.y, 3),
            ))
    return sorted(out)


def _assert_same_points(a, b, tol=0.5, pad=(0.0, 0.0, 0.0, 0.0)):
    """Confere que cada ponto de `a` (+pad) tem par em `b`, tolerancia mm."""
    remaining = list(b)
    for raw in a:
        shifted = tuple(raw[i] + (pad[i] if i < len(pad) else 0.0) for i in range(len(raw)))
        idx = None
        for i, cand in enumerate(remaining):
            if all(abs(shifted[k] - cand[k]) <= tol for k in range(len(shifted))):
                idx = i
                break
        assert idx is not None, f"{shifted} sem correspondente em {remaining} (tol={tol})"
        remaining.pop(idx)


REG_TYPES = ("none", "circles", "mimaki", "both", "squares", "crosses", "corner_l")


@pytest.mark.parametrize("reg_type", REG_TYPES)
def test_marca_bate_preview_pdf_dxf_por_tipo(qapp, tmp_path, reg_type):
    margin, size, thickness = 12.0, 8.0, 1.1
    w = _reg_window(tmp_path, reg_type, margin=margin, size=size,
                     thickness=thickness, cfg=reg_type)
    pad = w._faca_pad()

    dxf_path = tmp_path / f"{reg_type}_corte.dxf"
    w.export_dxf(str(dxf_path))
    pdf_path = tmp_path / f"{reg_type}_impressao.pdf"
    w.export_pdf(str(pdf_path))

    # o DXF espelha Y (CAD e Y-para-cima; a tela/PDF sao Y-para-baixo) —
    # dxf_exporter.py faz y' = flip_h - y. Recalcula o MESMO flip_h que o
    # exportador usou (maior Y de toda a geometria daquela chapa) para
    # comparar o preview (Y-para-baixo) com o DXF (Y-para-cima) sem falso
    # negativo por causa da convenção, não por causa de um bug real.
    sheets = w._effective_sheets()
    contours, segs, marks, mark_segs, mark_polys = w._dxf_payload(sheets)
    flip_h = DxfExporter._extent_y(contours, segs, marks, mark_segs, mark_polys)

    def _flip3(t):
        x, y, extra = t
        return (x, round(flip_h - y, 3), extra)

    def _flip4(t):
        x0, y0, x1, y1 = t
        return (x0, round(flip_h - y0, 3), x1, round(flip_h - y1, 3))

    if reg_type == "none":
        assert _preview_ellipses(w) == []
        assert _preview_reg_rects(w, size) == []
        assert _preview_lines(w) == []
        assert _dxf_circles(str(dxf_path)) == []
        assert _dxf_regmark_squares(str(dxf_path)) == []
        assert _dxf_regmark_lines(str(dxf_path)) == []
        assert _pdf_filled_black(str(pdf_path)) == []
        assert _pdf_stroked_black_lines(str(pdf_path)) == []
        return

    if reg_type in ("circles", "both"):
        preview = _preview_ellipses(w)
        assert len(preview) == 5
        dxf = _dxf_circles(str(dxf_path))
        assert len(dxf) == 5
        _assert_same_points([_flip3(t) for t in preview], dxf, tol=0.05)
        pdf = _pdf_filled_black(str(pdf_path))
        assert len(pdf) == 5
        _assert_same_points(preview, pdf, tol=0.3, pad=(pad, pad, 0.0))

    if reg_type == "squares":
        preview = _preview_reg_rects(w, size)
        assert len(preview) == 4
        dxf = _dxf_regmark_squares(str(dxf_path))
        assert len(dxf) == 4
        _assert_same_points([_flip3(t) for t in preview], dxf, tol=0.05)
        pdf = _pdf_filled_black(str(pdf_path))
        assert len(pdf) == 4
        _assert_same_points(preview, pdf, tol=0.3, pad=(pad, pad, 0.0))

    if reg_type in ("crosses", "corner_l"):
        preview = _preview_lines(w)
        assert len(preview) == 8
        dxf = _dxf_regmark_lines(str(dxf_path))
        assert len(dxf) == 8
        _assert_same_points([_flip4(t) for t in preview], dxf, tol=0.05)
        pdf_lines = _pdf_stroked_black_lines(str(pdf_path))
        assert len(pdf_lines) == 8
        pdf = [(x0, y0, x1, y1) for x0, y0, x1, y1, _width in pdf_lines]
        _assert_same_points(preview, pdf, tol=0.3, pad=(pad, pad, pad, pad))
        assert all(abs(width - thickness) < 0.05 for *_, width in pdf_lines)

    if reg_type in ("mimaki", "both"):
        # design: o quadro (frame) some no DXF junto com a faca, mas as
        # marcas em L (linhas) do Mimaki NAO vao para o DXF — só o PDF.
        assert _dxf_regmark_lines(str(dxf_path)) == []
        pdf_lines = _pdf_stroked_black_lines(str(pdf_path))
        assert pdf_lines, "marcas em L do Mimaki sumiram do PDF de impressao"
        preview_lines = _preview_lines(w)
        assert preview_lines, "marcas em L do Mimaki sumiram do preview"


@pytest.mark.parametrize("margin,size", [(0.0, 2.0), (10.0, 2.0), (50.0, 2.0),
                                          (0.0, 10.0), (10.0, 10.0), (50.0, 10.0)])
def test_quadrados_margem_e_tamanho_propagam_pro_dxf_real(qapp, tmp_path, margin, size):
    cfg = f"m{margin}_s{size}"
    w = _reg_window(tmp_path, "squares", margin=margin, size=size, cfg=cfg)
    dxf_path = tmp_path / f"{cfg}.dxf"
    w.export_dxf(str(dxf_path))
    marks = _dxf_regmark_squares(str(dxf_path))
    assert len(marks) == 4
    assert all(abs(m[2] - size) < 0.05 for m in marks)  # lado = tamanho pedido


@pytest.mark.parametrize("thickness", [0.3, 0.8, 2.0])
def test_cruzes_espessura_propaga_pro_pdf_real(qapp, tmp_path, thickness):
    cfg = f"t{thickness}"
    w = _reg_window(tmp_path, "crosses", thickness=thickness, cfg=cfg)
    pdf_path = tmp_path / f"{cfg}.pdf"
    w.export_pdf(str(pdf_path))
    lines = _pdf_stroked_black_lines(str(pdf_path))
    assert len(lines) == 8
    assert all(abs(width - thickness) < 0.05 for *_ , width in lines)


def test_persistencia_quadrados_margem_tamanho_e_espessura(qapp, tmp_path):
    # Pedido explicito da missao: salvar com "squares" + espessura 1.2 e
    # reabrir tem que trazer os 4 campos de volta (tipo, afastamento,
    # tamanho e espessura), mesmo a espessura nao valendo para quadrados.
    w1 = _reg_window(tmp_path, "squares", margin=23.0, size=9.0, thickness=1.2, cfg="w1")
    proj = tmp_path / "trabalho.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window(tmp_path, "w2")
    assert w2.open_project(str(proj)) is True
    assert w2._reg() == "squares"
    assert float(w2._reg_margin.value()) == 23.0
    assert float(w2._reg_diameter.value()) == 9.0
    assert float(w2._reg_thickness.value()) == 1.2


def test_marcas_de_registro_deveriam_ser_100pct_k_puro():
    pytest.xfail(
        "QA-F2A-03: marcas de registro (circulos/quadrados preenchidos e "
        "linhas de cruz/L) saem no PDF de impressao como DeviceRGB '0 0 0 "
        "rg'/'RG' (pdf_writer.draw_circle/draw_line/draw_rect_filled), nunca "
        "como K puro ('0 0 0 0 k'/'K' ou DeviceGray '0 g'). Visualmente e "
        "preto, mas uma grafica que confia em K=100%% para a marca de "
        "registro (sem rebuild de preto/GCR do RIP) pode ver um preto "
        "composto em vez de canal K puro."
    )


@pytest.mark.xfail(strict=False, reason="QA-F2A-03: ver test_marcas_de_registro_deveriam_ser_100pct_k_puro")
def test_marcas_de_registro_pdf_usa_operador_k_e_nao_rg(qapp, tmp_path):
    w = _reg_window(tmp_path, "squares", cfg="kcheck")
    pdf_path = tmp_path / "k.pdf"
    w.export_pdf(str(pdf_path))
    pdf = pikepdf.open(str(pdf_path))
    try:
        ops = pikepdf.parse_content_stream(pdf.pages[0])
        used = {str(op.operator) for op in ops}
        assert "rg" not in used and "RG" not in used, (
            "marca de registro usando DeviceRGB (rg/RG) em vez de K puro"
        )
        assert "k" in used or "K" in used, "esperava operador K (preto puro CMYK)"
    finally:
        pdf.close()
