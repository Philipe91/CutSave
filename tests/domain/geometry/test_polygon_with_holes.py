import pytest
from app.domain.geometry import Point2D, Polygon, PolygonWithHoles, group_rings
from app.domain.nesting.true_shape import NestingShape


def _rect(x: float, y: float, w: float, h: float, clockwise: bool = False) -> Polygon:
    pts = [Point2D(x, y), Point2D(x + w, y), Point2D(x + w, y + h), Point2D(x, y + h)]
    if clockwise:
        pts.reverse()
    return Polygon(tuple(pts))


def test_orientacao_canonica_normalizada_na_construcao():
    # outer entra horario e furo anti-horario: ambos devem ser normalizados
    shape = PolygonWithHoles(
        outer=_rect(0, 0, 100, 50, clockwise=True),
        holes=(_rect(10, 10, 20, 20, clockwise=False),),
    )
    assert shape.outer.signed_area > 0          # anti-horario
    assert shape.holes[0].signed_area < 0       # horario


def test_bounding_box_e_area_liquida():
    shape = PolygonWithHoles(
        outer=_rect(0, 0, 100, 50),
        holes=(_rect(10, 10, 20, 20), _rect(50, 10, 10, 10)),
    )
    bb = shape.bounding_box
    assert (bb.width, bb.height) == (100, 50)
    assert shape.area_liquida == pytest.approx(100 * 50 - 400 - 100)


def test_group_rings_corpo_simples_sem_furo():
    shapes = group_rings([_rect(0, 0, 100, 50)])
    assert len(shapes) == 1
    assert shapes[0].holes == ()


def test_group_rings_detecta_furo_por_contencao():
    shapes = group_rings([_rect(10, 10, 20, 20), _rect(0, 0, 100, 50)])
    assert len(shapes) == 1
    assert len(shapes[0].holes) == 1
    assert shapes[0].outer.area == pytest.approx(5000)


def test_group_rings_ilha_dentro_de_furo_vira_novo_outer():
    # profundidade 0 = corpo, 1 = furo, 2 = corpo de novo (even-odd)
    rings = [
        _rect(0, 0, 100, 100),   # corpo
        _rect(20, 20, 60, 60),   # furo
        _rect(40, 40, 20, 20),   # ilha dentro do furo
    ]
    shapes = group_rings(rings)
    assert len(shapes) == 2
    areas = sorted(s.outer.area for s in shapes)
    assert areas == [pytest.approx(400), pytest.approx(10000)]
    grande = max(shapes, key=lambda s: s.outer.area)
    assert len(grande.holes) == 1


def test_group_rings_furo_atribuido_ao_pai_direto():
    # dois corpos aninhados... nao: dois corpos LADO A LADO, cada um com furo
    rings = [
        _rect(0, 0, 40, 40),
        _rect(10, 10, 10, 10),
        _rect(100, 0, 40, 40),
        _rect(110, 10, 10, 10),
    ]
    shapes = group_rings(rings)
    assert len(shapes) == 2
    for s in shapes:
        assert len(s.holes) == 1
        # furo dentro do proprio outer
        assert s.outer.contains(s.holes[0].vertices[0])


def test_group_rings_descarta_anel_degenerado():
    fino = Polygon((Point2D(0, 0), Point2D(10, 0), Point2D(10, 1e-9)))
    shapes = group_rings([_rect(0, 0, 100, 50), fino])
    assert len(shapes) == 1
    assert shapes[0].holes == ()


def test_nesting_shape_sem_furos_continua_identico():
    # default vazio: nada da Fase 2 muda de comportamento
    shape = NestingShape("a1", _rect(0, 0, 10, 10))
    assert shape.holes == ()
