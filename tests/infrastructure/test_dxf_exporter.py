import ezdxf
import pytest
from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from app.infrastructure.exporters.dxf_exporter import DxfExporter


def _rect_contour(x0=0.0, y0=0.0, w=320.0, h=92.0):
    return CutContour([
        Point2D(x0, y0),
        Point2D(x0 + w, y0),
        Point2D(x0 + w, y0 + h),
        Point2D(x0, y0 + h),
    ])


def test_gera_arquivo_dxf(tmp_path):
    out = tmp_path / "faca.dxf"
    DxfExporter().export([_rect_contour()], str(out))
    assert out.exists()


def test_unidades_em_milimetros(tmp_path):
    out = tmp_path / "faca.dxf"
    DxfExporter().export([_rect_contour()], str(out))
    doc = ezdxf.readfile(str(out))
    assert doc.header["$INSUNITS"] == 4  # 4 = milimetros


def test_layer_cut_existe(tmp_path):
    out = tmp_path / "faca.dxf"
    DxfExporter().export([_rect_contour()], str(out))
    doc = ezdxf.readfile(str(out))
    assert "CUT" in doc.layers


def _circle_contour(n=24, r=15.0, cx=20.0, cy=20.0):
    import math
    return CutContour([
        Point2D(cx + r * math.cos(2 * math.pi * i / n),
                cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ])


def test_dxf_sai_com_y_para_cima_sem_espelhar(tmp_path):
    # Modelo usa Y-para-baixo (tela/PDF); CAD le Y-para-cima. O exportador
    # reflete a geometria (y' = H - y): o que esta no TOPO do modelo (y=0)
    # precisa sair com o MAIOR y no DXF — senao o Corel abre espelhado
    # (bug real do beta, 09/07).
    tri = CutContour([Point2D(5, 0), Point2D(0, 10), Point2D(10, 10)])  # bico no TOPO
    out = tmp_path / "faca.dxf"
    DxfExporter().export([tri], str(out))
    doc = ezdxf.readfile(str(out))
    pts = {(round(x, 6), round(y, 6)) for x, y, *_ in
           doc.modelspace().query("LWPOLYLINE")[0].get_points()}
    # bico (y=0 no modelo) vira y=10 no DXF; base (y=10) vira y=0
    assert (5.0, 10.0) in pts
    assert (0.0, 0.0) in pts and (10.0, 0.0) in pts


def test_contorno_curvo_sai_como_spline(tmp_path):
    # curva de verdade no DXF (corte liso na maquina); o retangulo continua
    # como polilinha (retas exatas). F3: UM contorno = UM SPLINE fechado —
    # nada de explodir a peca em pedacos (bug do Corel, 24/07).
    out = tmp_path / "faca.dxf"
    DxfExporter().export([_circle_contour(), _rect_contour()], str(out))
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    splines = msp.query("SPLINE")
    plines = msp.query("LWPOLYLINE")
    assert len(splines) == 1 and splines[0].dxf.layer == "CUT"
    assert splines[0].closed
    assert len(plines) == 1  # so o retangulo


def test_polilinha_fechada_na_layer_cut(tmp_path):
    out = tmp_path / "faca.dxf"
    DxfExporter().export([_rect_contour()], str(out))
    doc = ezdxf.readfile(str(out))
    plines = doc.modelspace().query("LWPOLYLINE")
    assert len(plines) == 1
    assert plines[0].closed is True
    assert plines[0].dxf.layer == "CUT"


def test_coordenadas_preservadas(tmp_path):
    # medidas/posicoes preservadas; o eixo Y sai REFLETIDO (y' = H - y) para o
    # CAD ler sem espelhar — num retangulo o conjunto de vertices e o mesmo
    out = tmp_path / "faca.dxf"
    DxfExporter().export([_rect_contour(0, 0, 320, 92)], str(out))
    doc = ezdxf.readfile(str(out))
    pl = doc.modelspace().query("LWPOLYLINE")[0]
    pts = {(round(p[0], 3), round(p[1], 3)) for p in pl.get_points()}
    assert pts == {(0, 0), (320, 0), (320, 92), (0, 92)}


def test_caminho_invalido_levanta_erro(tmp_path):
    from app.shared.errors import DxfExportError

    destino = tmp_path / "subpasta_inexistente" / "faca.dxf"
    with pytest.raises(DxfExportError):
        DxfExporter().export([_rect_contour()], str(destino))


def test_multiplas_facas(tmp_path):
    out = tmp_path / "facas.dxf"
    DxfExporter().export([_rect_contour(), _rect_contour(0, 100)], str(out))
    doc = ezdxf.readfile(str(out))
    assert len(doc.modelspace().query("LWPOLYLINE")) == 2


def test_faca_compartilhada_gera_linhas_na_layer_cut(tmp_path):
    from app.domain.cut.shared import Segment

    out = tmp_path / "grade.dxf"
    segs = [
        Segment(Point2D(0, 0), Point2D(0, 50)),
        Segment(Point2D(0, 0), Point2D(100, 0)),
    ]
    DxfExporter().export([], str(out), segments=segs)
    doc = ezdxf.readfile(str(out))
    lines = doc.modelspace().query("LINE")
    assert len(lines) == 2
    assert all(ln.dxf.layer == "CUT" for ln in lines)


def test_marcas_de_registro_geram_circulos_na_layer_regmark(tmp_path):
    from app.domain.cut.registration import RegistrationMark

    out = tmp_path / "marcas.dxf"
    marks = [RegistrationMark(Point2D(10, 10), 6.0), RegistrationMark(Point2D(90, 10), 6.0)]
    DxfExporter().export([_rect_contour()], str(out), marks=marks)
    doc = ezdxf.readfile(str(out))
    circles = doc.modelspace().query("CIRCLE")
    assert len(circles) == 2
    assert "REGMARK" in doc.layers
    assert all(c.dxf.layer == "REGMARK" for c in circles)
    assert round(circles[0].dxf.radius, 3) == 3.0


def test_quadrado_de_registro_sai_como_polilinha_fechada_na_regmark(tmp_path):
    # quadrado 6mm centrado em (10,10): polilinha FECHADA no layer REGMARK
    out = tmp_path / "quadrados.dxf"
    poly = [Point2D(7, 7), Point2D(13, 7), Point2D(13, 13), Point2D(7, 13)]
    DxfExporter().export([_rect_contour()], str(out), mark_polylines=[poly])
    doc = ezdxf.readfile(str(out))
    regs = [
        p for p in doc.modelspace().query("LWPOLYLINE") if p.dxf.layer == "REGMARK"
    ]
    assert len(regs) == 1
    assert regs[0].closed
    # espelhamento vertical: contorno vai ate y=92 -> (7,7) vira (7,85)
    pts = {(round(x, 6), round(y, 6)) for x, y, *_ in regs[0].get_points()}
    assert (7.0, 85.0) in pts and (13.0, 79.0) in pts


def test_cruz_de_registro_sai_como_linhas_na_regmark(tmp_path):
    from app.domain.cut.shared import Segment

    out = tmp_path / "cruzes.dxf"
    segs = [
        Segment(Point2D(7, 10), Point2D(13, 10)),
        Segment(Point2D(10, 7), Point2D(10, 13)),
    ]
    DxfExporter().export([_rect_contour()], str(out), mark_segments=segs)
    doc = ezdxf.readfile(str(out))
    lines = doc.modelspace().query("LINE")
    assert len(lines) == 2
    assert all(ln.dxf.layer == "REGMARK" for ln in lines)


def test_sem_marcas_novas_saida_identica(tmp_path):
    # nao-regressao: a chamada antiga (sem mark_polylines) nao muda entidades
    out = tmp_path / "regressao.dxf"
    DxfExporter().export([_rect_contour()], str(out))
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    assert len(msp.query("LWPOLYLINE")) == 1
    assert len(msp.query("LINE")) == 0
    assert len(msp.query("CIRCLE")) == 0
    assert "REGMARK" not in doc.layers
