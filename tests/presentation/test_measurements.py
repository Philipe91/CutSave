from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.presentation.measurements import group_metrics, piece_metrics, sheet_metrics


def _art(art_id="a0", w=100.0, h=50.0, faca=None):
    return Artwork(
        id=art_id, name=art_id, file_format=FileFormat.PDF,
        size=Size(w, h), kind=ArtKind.RETANGULAR, cut_contour=faca,
    )


def _square(side):
    return CutContour([
        Point2D(0, 0), Point2D(side, 0), Point2D(side, side), Point2D(0, side)
    ])


def test_piece_metrics_retangular_sem_faca():
    m = piece_metrics(_art(w=100, h=50))
    assert (m.width, m.height) == (100, 50)
    assert m.area == 5000
    assert m.perimeter == 300


def test_piece_metrics_usa_contorno_da_faca():
    m = piece_metrics(_art(faca=_square(10)))
    assert m.area == 100
    assert m.perimeter == 40


def test_group_metrics_envolve_as_caixas():
    boxes = [(0, 0, 10, 10), (20, 5, 10, 10)]  # (x, y, w, h)
    g = group_metrics(boxes)
    assert g.count == 2
    assert g.width == 30  # de x=0 ate x=30
    assert g.height == 15  # de y=0 ate y=15


def test_group_metrics_vazio():
    g = group_metrics([])
    assert g.count == 0 and g.width == 0 and g.height == 0


def test_sheet_metrics_percentual_e_area_livre():
    art = _art(w=100, h=50)  # footprint 100x50 = 5000 mm2
    mat = Material("UV", width=200)
    layout = Layout(mat, [PlacedItem("a0", Point2D(0, 0))], used_length=100.0)
    s = sheet_metrics(layout, [art])
    assert s.sheet_area == 200 * 100  # 20000
    assert s.used_area == 5000
    assert s.used_pct == 25.0
    assert s.free_area == 15000
