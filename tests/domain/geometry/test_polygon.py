import pytest
from app.domain.geometry import BoundingBox, Point2D, Polygon
from app.shared.errors import ValidationError


def _quadrado():
    # anti-horario, lado 10, canto na origem
    return Polygon([Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)])


def test_lista_convertida_para_tupla():
    assert isinstance(_quadrado().vertices, tuple)


def test_minimo_tres_vertices():
    with pytest.raises(ValidationError):
        Polygon([Point2D(0, 0), Point2D(1, 1)])


def test_area_e_perimetro():
    q = _quadrado()
    assert q.area == 100
    assert q.perimeter == 40


def test_orientacao():
    horario = Polygon([Point2D(0, 0), Point2D(0, 10), Point2D(10, 10), Point2D(10, 0)])
    assert _quadrado().is_clockwise is False
    assert horario.is_clockwise is True


def test_centroid_do_quadrado():
    c = _quadrado().centroid
    assert c.x == pytest.approx(5)
    assert c.y == pytest.approx(5)


def test_bounding_box():
    assert _quadrado().bounding_box == BoundingBox(0, 0, 10, 10)


def test_translated():
    p = _quadrado().translated(5, 5)
    assert p.bounding_box == BoundingBox(5, 5, 15, 15)


def test_rotated_preserva_area():
    p = _quadrado().rotated(45)
    assert p.area == pytest.approx(100)


def test_scaled_dobra_lado_quadruplica_area():
    p = _quadrado().scaled(2)
    assert p.area == pytest.approx(400)


def test_contains():
    q = _quadrado()
    assert q.contains(Point2D(5, 5))
    assert not q.contains(Point2D(50, 50))


def test_imutavel():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        _quadrado().vertices = ()


def test_polygon_sem_curvas_por_padrao():
    from app.domain.geometry import Point2D, Polygon

    poly = Polygon((Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)))
    assert poly.curves == ()


def test_translated_leva_os_controles_junto():
    import pytest

    from app.domain.geometry import Point2D, Polygon
    from app.domain.geometry.bezier import BezierSegment

    seg = BezierSegment(Point2D(0, 0), Point2D(3, 1), Point2D(7, 1), Point2D(10, 0))
    poly = Polygon((Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)), curves=(seg,))
    movido = poly.translated(5.0, -1.0)
    assert movido.curves[0].c1.x == pytest.approx(8.0)
    assert movido.curves[0].c1.y == pytest.approx(0.0)


def test_rotated_leva_os_controles_junto():
    import pytest

    from app.domain.geometry import Point2D, Polygon
    from app.domain.geometry.bezier import BezierSegment

    seg = BezierSegment(Point2D(1, 0), Point2D(2, 0), Point2D(3, 0), Point2D(4, 0))
    poly = Polygon((Point2D(1, 0), Point2D(4, 0), Point2D(4, 4)), curves=(seg,))
    girado = poly.rotated(90.0, around=Point2D(0, 0))
    assert girado.curves[0].p0.x == pytest.approx(0.0, abs=1e-9)
    assert girado.curves[0].p0.y == pytest.approx(1.0, abs=1e-9)


def test_from_points_nao_inventa_curva():
    from app.domain.geometry import Point2D, Polygon

    poly = Polygon.from_points([Point2D(0, 0), Point2D(1, 0), Point2D(1, 1)])
    assert poly.curves == ()
