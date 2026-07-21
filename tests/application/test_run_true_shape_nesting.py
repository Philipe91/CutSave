import ezdxf
import pytest
from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.application.use_cases.run_true_shape_nesting import (
    RunTrueShapeNestingUseCase,
    placed_cut_contours,
    to_nesting_shapes,
)
from app.domain.geometry import Point2D
from app.domain.geometry.polygon import Polygon
from app.domain.geometry.polygon_with_holes import PolygonWithHoles
from app.domain.model.material import Material
from app.domain.nesting.true_shape import TrueShapePacker
from app.infrastructure.exporters.dxf_exporter import DxfExporter
from app.shared.errors import ValidationError


def _rect(w: float, h: float, x0: float = 0.0, y0: float = 0.0) -> Polygon:
    return Polygon((
        Point2D(x0, y0),
        Point2D(x0 + w, y0),
        Point2D(x0 + w, y0 + h),
        Point2D(x0, y0 + h),
    ))


def _use_case(**packer_kwargs) -> RunTrueShapeNestingUseCase:
    packer_kwargs.setdefault("generations", 2)
    packer_kwargs.setdefault("seed", 0)
    return RunTrueShapeNestingUseCase(
        TrueShapePacker(**packer_kwargs), ExportDxfUseCase(DxfExporter())
    )


def _polyline_boxes(path: str) -> list[tuple[float, float, float, float]]:
    """(min_x, min_y, max_x, max_y) de cada LWPOLYLINE do DXF."""
    doc = ezdxf.readfile(path)
    boxes = []
    for pl in doc.modelspace().query("LWPOLYLINE"):
        xs = [p[0] for p in pl.get_points()]
        ys = [p[1] for p in pl.get_points()]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    return boxes


def test_quadrado_e_retangulo_geram_um_dxf(tmp_path):
    shapes = to_nesting_shapes([PolygonWithHoles(_rect(30, 30)), PolygonWithHoles(_rect(50, 20))])
    out = tmp_path / "nest.dxf"
    result = _use_case().execute(shapes, Material("vinil", 200.0), str(out))
    assert result.dxf_paths == (str(out),)
    assert out.exists()
    assert result.unplaced_ids == ()
    assert len(result.layouts) == 1 and result.layouts[0].item_count == 2
    boxes = _polyline_boxes(str(out))
    assert len(boxes) == 2
    # dimensoes preservadas (rotacao pode trocar largura/altura entre si)
    sizes = {tuple(sorted((round(b[2] - b[0], 3), round(b[3] - b[1], 3)))) for b in boxes}
    assert sizes == {(30.0, 30.0), (20.0, 50.0)}


def test_reconstrucao_respeita_a_convencao_position_igual_bbox_min(tmp_path):
    shapes = to_nesting_shapes([PolygonWithHoles(_rect(30, 30)), PolygonWithHoles(_rect(50, 20))])
    result = _use_case().execute(
        shapes, Material("vinil", 200.0), str(tmp_path / "nest.dxf")
    )
    by_id = {s.artwork_id: s for s in shapes}
    for item in result.layouts[0].items:
        outer = placed_cut_contours(by_id[item.artwork_id], item)[0]
        assert outer.origin.x == pytest.approx(item.position.x, abs=1e-6)
        assert outer.origin.y == pytest.approx(item.position.y, abs=1e-6)


def test_furo_descentrado_gira_junto_com_o_outer(tmp_path):
    # "O" com furo DESCENTRADO + rotations=(90,) forcando rotacao: o offset
    # relativo furo->outer no DXF tem de ser o offset original GIRADO de 90
    # graus. Se o furo fosse normalizado pelo proprio bbox, ele colaria no
    # canto minimo do outer (offset zero) e este teste falharia.
    outer = _rect(40, 40)
    hole = _rect(10, 10, 5, 5)
    shapes = to_nesting_shapes([PolygonWithHoles(outer, (hole,))], rotations=(90.0,))
    out = tmp_path / "o.dxf"
    result = _use_case().execute(shapes, Material("vinil", 100.0), str(out))
    assert result.layouts[0].items[0].rotation == 90

    # esperado, por primeiros principios: gira outer e furo pelo MESMO centro
    # e mede o offset entre os cantos minimos dos bboxes girados
    outer_rot = outer.rotated(90.0, around=Point2D(0, 0)).bounding_box
    hole_rot = hole.rotated(90.0, around=Point2D(0, 0)).bounding_box
    expected_dx = hole_rot.min_x - outer_rot.min_x
    expected_dy = hole_rot.min_y - outer_rot.min_y
    assert (expected_dx, expected_dy) != (5.0, 5.0)  # a rotacao mudou o offset

    boxes = sorted(_polyline_boxes(str(out)), key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    assert len(boxes) == 2
    hole_box, outer_box = boxes
    # DXF sai com Y refletido (y' = H - y): dx preserva; dy do modelo vira
    # diferenca entre os MAX de y no arquivo
    assert hole_box[0] - outer_box[0] == pytest.approx(expected_dx, abs=1e-6)
    assert outer_box[3] - hole_box[3] == pytest.approx(expected_dy, abs=1e-6)


def test_dxf_corta_o_contorno_original_nao_o_simplificado(tmp_path):
    # retangulo com lados subdivididos (40 vertices, quase todos colineares):
    # o packer com approximation grossa simplifica INTERNAMENTE para acelerar
    # o NFP, mas o DXF tem de sair com os 40 vertices originais.
    step = 5
    pts = (
        [Point2D(x, 0.0) for x in range(0, 60, step)]
        + [Point2D(60.0, y) for y in range(0, 40, step)]
        + [Point2D(x, 40.0) for x in range(60, 0, -step)]
        + [Point2D(0.0, y) for y in range(40, 0, -step)]
    )
    contour = Polygon(tuple(pts))
    assert len(contour.vertices) == 40
    shapes = to_nesting_shapes([PolygonWithHoles(contour)], rotations=(0.0,))
    out = tmp_path / "orig.dxf"
    _use_case(approximation=2.0).execute(shapes, Material("vinil", 100.0), str(out))
    doc = ezdxf.readfile(str(out))
    pl = doc.modelspace().query("LWPOLYLINE")[0]
    assert len(pl.get_points()) == 40


def test_peca_maior_que_o_material_aparece_em_unplaced(tmp_path):
    shapes = to_nesting_shapes(
        [PolygonWithHoles(_rect(30, 30)), PolygonWithHoles(_rect(500, 500))]
    )
    out = tmp_path / "nest.dxf"
    result = _use_case().execute(shapes, Material("vinil", 100.0), str(out))
    assert result.unplaced_ids == ("shape-0002",)
    boxes = _polyline_boxes(str(out))
    assert len(boxes) == 1  # so a peca que coube
    assert boxes[0][2] - boxes[0][0] == pytest.approx(30.0, abs=1e-6)


def test_nada_coube_lanca_erro_claro_sem_dxf(tmp_path):
    shapes = to_nesting_shapes([PolygonWithHoles(_rect(500, 500))])
    out = tmp_path / "nest.dxf"
    with pytest.raises(ValidationError, match="coube"):
        _use_case().execute(shapes, Material("vinil", 100.0), str(out))
    assert not out.exists()


def test_execute_sheets_gera_um_dxf_numerado_por_folha(tmp_path):
    # largura 40 e folha de 35mm: cada quadrado de 30 exige uma folha propria
    shapes = to_nesting_shapes([PolygonWithHoles(_rect(30, 30)), PolygonWithHoles(_rect(30, 30))])
    out = tmp_path / "nest.dxf"
    result = _use_case().execute_sheets(
        shapes, Material("vinil", 40.0), str(out), sheet_length=35.0
    )
    expected = (str(tmp_path / "nest_folha1.dxf"), str(tmp_path / "nest_folha2.dxf"))
    assert result.dxf_paths == expected
    assert result.unplaced_ids == ()
    assert len(result.layouts) == 2
    for path in expected:
        boxes = _polyline_boxes(path)
        assert len(boxes) == 1
        assert boxes[0][2] - boxes[0][0] == pytest.approx(30.0, abs=1e-6)
