from app.domain.geometry import BoundingBox, Point2D, Polygon, Rectangle, Size


def _rect():
    return Rectangle(Point2D(10, 5), Size(40, 20))


def test_dimensoes_e_extremos():
    r = _rect()
    assert r.width == 40
    assert r.height == 20
    assert r.area == 800
    assert (r.min_x, r.min_y, r.max_x, r.max_y) == (10, 5, 50, 25)
    assert r.center == Point2D(30, 15)


def test_corners():
    r = _rect()
    assert r.corners == (
        Point2D(10, 5),
        Point2D(50, 5),
        Point2D(50, 25),
        Point2D(10, 25),
    )


def test_bounding_box():
    assert _rect().bounding_box == BoundingBox(10, 5, 50, 25)


def test_translated():
    r = _rect().translated(5, -5)
    assert r.origin == Point2D(15, 0)


def test_scaled_mantem_origem():
    r = _rect().scaled(2)
    assert r.origin == Point2D(10, 5)
    assert r.size == Size(80, 40)


def test_contains():
    r = _rect()
    assert r.contains(Point2D(30, 15))
    assert not r.contains(Point2D(0, 0))


def test_intersects():
    a = Rectangle(Point2D(0, 0), Size(10, 10))
    b = Rectangle(Point2D(5, 5), Size(10, 10))
    c = Rectangle(Point2D(100, 100), Size(2, 2))
    assert a.intersects(b)
    assert not a.intersects(c)


def test_to_polygon():
    poly = _rect().to_polygon()
    assert isinstance(poly, Polygon)
    assert poly.area == 800
