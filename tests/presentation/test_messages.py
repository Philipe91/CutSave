from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.image_artwork import ImageArtwork, ImageKind
from app.domain.model.material import Material
from app.presentation.messages import (
    has_traced_image,
    oversized_pieces,
    production_notices,
)


def _rect_art(art_id="a0", w=100.0, h=50.0):
    return Artwork(
        id=art_id, name=art_id, file_format=FileFormat.PDF,
        size=Size(w, h), kind=ArtKind.RETANGULAR,
    )


def _traced_image(art_id="img"):
    pts = [Point2D(0, 0), Point2D(10, 0), Point2D(10, 5), Point2D(6, 9),
           Point2D(3, 8), Point2D(0, 6)]  # 6 pontos -> "desenho"
    contour = CutContour(pts)
    return ImageArtwork(
        id=art_id, name=art_id, file_format=FileFormat.PNG,
        size=Size(10, 10), kind=ArtKind.RASTER, cut_contour=contour,
        image_kind=ImageKind.IMAGE_ALPHA, raw_contour=contour,
    )


def test_has_traced_image_detecta_desenho():
    assert has_traced_image([_traced_image()]) is True


def test_has_traced_image_falso_para_retangular():
    assert has_traced_image([_rect_art()]) is False


def test_aviso_faca_compartilhada_com_imagem():
    notices = production_notices(
        shared_faca=True, artworks=[_traced_image()], material=Material("m", width=500)
    )
    codes = [n.code for n in notices]
    assert "shared_faca_image" in codes
    assert all(n.level == "warning" for n in notices if n.code == "shared_faca_image")


def test_sem_aviso_quando_faca_por_peca():
    notices = production_notices(
        shared_faca=False, artworks=[_traced_image()], material=Material("m", width=500)
    )
    assert "shared_faca_image" not in [n.code for n in notices]


def test_pecas_maiores_que_a_chapa():
    grande = _rect_art("g", w=600, h=50)
    assert oversized_pieces([grande], Material("m", width=500)) == ["g"]
    notices = production_notices(
        shared_faca=False, artworks=[grande], material=Material("m", width=500)
    )
    assert "oversized" in [n.code for n in notices]
