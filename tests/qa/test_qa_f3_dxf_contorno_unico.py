"""FASE 3 (QA) — DXF: um contorno = UMA entidade (F3).

Bug reproduzido no Corel (24/07): letra exportada do Modo Corte abria em
PEDACOS — render_splines_and_polylines quebrava o caminho a cada canto (um
SPLINE por trecho curvo, polylines nos retos) e nao dava para selecionar a
letra inteira.

Contrato F3 sob teste, com um "R" de verdade (Texto... -> curvas):
- nº de entidades no layer CUT == nº de contornos (externo + furos);
- cada SPLINE e FECHADO;
- ordem de corte preservada (furo ANTES do externo, de dentro pra fora);
- geometria EXATA: os pontos de controle do SPLINE sao exatamente os das
  Beziers de cubic_segments (mesma receita do preview/canvas/Faca PDF) com
  o espelhamento Y do DxfExporter — curva de verdade, nada achatado.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.run_true_shape_nesting import (  # noqa: E402
    placed_cut_contours,
)
from app.domain.cut.curves import cubic_segments  # noqa: E402
from app.domain.geometry import Point2D  # noqa: E402
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.presentation.cut_mode_dialog import CutModeDialog  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_ARIAL = "C:/Windows/Fonts/arial.ttf"

pytestmark = pytest.mark.skipif(
    not os.path.exists(_ARIAL), reason="arial.ttf indisponivel neste ambiente"
)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp):
    dlg = CutModeDialog(export_dxf=ExportDxfUseCase(DxfExporter()))
    dlg._seconds.setValue(0.5)  # tempo minimo: o teste valida o CONTRATO
    yield dlg
    dlg.deleteLater()


def _control_points_esperados(points, flip_h):
    """Receita do exportador: flip Y -> cubic_segments -> pontos de controle
    do B-spline (bezier_to_bspline nao duplica o no compartilhado)."""
    flipped = [Point2D(p.x, flip_h - p.y) for p in points]
    segs = cubic_segments(flipped)
    cps = [(segs[0].p0.x, segs[0].p0.y)]
    for s in segs:
        cps.extend([(s.c1.x, s.c1.y), (s.c2.x, s.c2.y), (s.p1.x, s.p1.y)])
    return cps


def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def test_letra_r_um_spline_fechado_por_contorno_furo_antes_do_externo(
    dialog, tmp_path
):
    dialog.add_text("R", _ARIAL, 30.0)
    dialog._width.setValue(200.0)
    dialog._sheet_len.setValue(0.0)  # bobina: 1 folha so
    dialog.nest()
    assert len(dialog._layouts) == 1 and not dialog._unplaced

    out = str(tmp_path / "letra_r.dxf")
    result = dialog.export(out)
    assert result.dxf_paths == (out,)

    shape = dialog._nested_shapes[0]
    item = dialog._layouts[0].items[0]
    contornos = placed_cut_contours(shape, item)  # [externo, furo, ...]
    assert len(contornos) == 2  # "R" do Arial: externo + 1 furo (miolo)

    msp = ezdxf.readfile(out).modelspace()
    cut = [e for e in msp if e.dxf.layer == "CUT"]
    # F3: nº de entidades no CUT == nº de contornos — a letra NAO explode
    # em pedacos; furo continua objeto proprio (2 objetos e o correto).
    assert len(cut) == len(contornos)
    assert all(e.dxftype() == "SPLINE" for e in cut)
    assert all(e.closed for e in cut)

    # ordem de corte: furo ANTES do externo (de dentro pra fora) — o bbox da
    # 1a entidade cabe dentro do bbox da 2a
    flip_h = max(p.y for c in contornos for p in c.points)
    esperados = {
        "furo": _control_points_esperados(contornos[1].points, flip_h),
        "externo": _control_points_esperados(contornos[0].points, flip_h),
    }
    b_furo, b_ext = _bbox(esperados["furo"]), _bbox(esperados["externo"])
    assert b_ext[0] < b_furo[0] and b_ext[1] < b_furo[1]
    assert b_furo[2] < b_ext[2] and b_furo[3] < b_ext[3]

    # geometria EXATA e igual ao preview: os pontos de controle gravados sao
    # exatamente os das Beziers de cubic_segments (mesmos nos que o preview
    # desenha via placed_cut_contours) — na ordem de corte furo -> externo
    for entidade, chave in zip(cut, ("furo", "externo")):
        gravados = [(p.x, p.y) for p in entidade.construction_tool().control_points]
        assert len(gravados) == len(esperados[chave])
        for g, e in zip(gravados, esperados[chave]):
            assert g == pytest.approx(e, abs=1e-6)


def test_retangulo_continua_lwpolyline_fechada(dialog, tmp_path):
    # nao-regressao do ramo reto do exportador: contorno so de retas segue
    # como 1 LWPOLYLINE FECHADA (nao vira spline nem explode)
    svg = tmp_path / "rect.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
        'viewBox="0 0 100 100"><rect x="0" y="0" width="40" height="20"/></svg>',
        encoding="utf-8",
    )
    dialog.add_vector_file(str(svg))
    dialog._width.setValue(200.0)
    dialog._sheet_len.setValue(0.0)
    dialog.nest()

    out = str(tmp_path / "rect.dxf")
    dialog.export(out)
    msp = ezdxf.readfile(out).modelspace()
    plines = msp.query("LWPOLYLINE")
    assert len(plines) == 1
    assert plines[0].closed and plines[0].dxf.layer == "CUT"
    assert len(msp.query("SPLINE")) == 0
