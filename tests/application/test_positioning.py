from app.application.positioning import (
    SHEET_GAP_MM,
    positioned_cut_contours,
    positioned_cut_contours_sheets,
)
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem


def _faca(x0, y0, w, h):
    return CutContour([
        Point2D(x0, y0), Point2D(x0 + w, y0), Point2D(x0 + w, y0 + h), Point2D(x0, y0 + h)
    ])


def _artwork(art_id, faca):
    return Artwork(id=art_id, name=art_id, file_format=FileFormat.PDF,
                   size=Size(faca.size.width, faca.size.height), kind=ArtKind.RETANGULAR,
                   cut_contour=faca)


def test_faca_e_transladada_para_a_posicao_no_layout():
    # faca em (-3,-3)..(323,95); peca posicionada em (0,0) -> faca vira (0,0)..(326,98)
    art = _artwork("a0", _faca(-3, -3, 326, 98))
    layout = Layout(Material("UV", width=1300), [PlacedItem("a0", Point2D(0, 0))], 98.0)
    contours = positioned_cut_contours(layout, [art])
    assert len(contours) == 1
    assert contours[0].origin == Point2D(0, 0)
    assert contours[0].size == Size(326, 98)


def test_ignora_pecas_sem_faca():
    art = Artwork(id="a0", name="a0", file_format=FileFormat.PDF,
                  size=Size(100, 50), kind=ArtKind.RETANGULAR)  # sem faca
    layout = Layout(Material("UV", width=1300), [PlacedItem("a0", Point2D(0, 0))], 50.0)
    assert positioned_cut_contours(layout, [art]) == []


def test_chapas_lado_a_lado_deslocam_em_x():
    art = _artwork("a0", _faca(0, 0, 100, 50))
    mat = Material("UV", width=200)
    s1 = Layout(mat, [PlacedItem("a0", Point2D(0, 0))], 50.0)
    s2 = Layout(mat, [PlacedItem("a0", Point2D(0, 0))], 50.0)

    contours = positioned_cut_contours_sheets([s1, s2], [art], sheet_width=200)
    assert len(contours) == 2
    # chapa 0 em x=0; chapa 1 deslocada por largura + gap
    assert contours[0].origin == Point2D(0, 0)
    assert contours[1].origin == Point2D(200 + SHEET_GAP_MM, 0)
