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


def test_polilinha_fechada_na_layer_cut(tmp_path):
    out = tmp_path / "faca.dxf"
    DxfExporter().export([_rect_contour()], str(out))
    doc = ezdxf.readfile(str(out))
    plines = doc.modelspace().query("LWPOLYLINE")
    assert len(plines) == 1
    assert plines[0].closed is True
    assert plines[0].dxf.layer == "CUT"


def test_coordenadas_preservadas(tmp_path):
    out = tmp_path / "faca.dxf"
    DxfExporter().export([_rect_contour(0, 0, 320, 92)], str(out))
    doc = ezdxf.readfile(str(out))
    pl = doc.modelspace().query("LWPOLYLINE")[0]
    pts = [(round(p[0], 3), round(p[1], 3)) for p in pl.get_points()]
    assert pts == [(0, 0), (320, 0), (320, 92), (0, 92)]


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
