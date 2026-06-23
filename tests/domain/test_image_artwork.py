import pytest
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.image_artwork import ImageArtwork, ImageKind


def _contour():
    return CutContour([Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)])


def test_image_artwork_e_uma_artwork():
    art = ImageArtwork(
        id="x#1", name="x", file_format=FileFormat.PNG, size=Size(50, 30),
        kind=ArtKind.RASTER, cut_contour=_contour(), dpi=150.0,
        image_kind=ImageKind.IMAGE_ALPHA, raw_contour=_contour(),
    )
    assert isinstance(art, Artwork)
    assert art.has_cut
    assert art.image_kind is ImageKind.IMAGE_ALPHA
    assert art.dpi == 150.0
    assert art.raw_contour is not None


@pytest.mark.parametrize("path,expected", [
    ("a.pdf", FileFormat.PDF),
    ("a.png", FileFormat.PNG),
    ("a.JPG", FileFormat.JPG),
    ("a.jpeg", FileFormat.JPG),
    ("a.webp", FileFormat.WEBP),
])
def test_fileformat_from_path(path, expected):
    assert FileFormat.from_path(path) is expected


def test_fileformat_is_image():
    assert FileFormat.PNG.is_image
    assert FileFormat.WEBP.is_image
    assert not FileFormat.PDF.is_image


def test_fileformat_desconhecido_levanta():
    with pytest.raises(ValueError):
        FileFormat.from_path("a.gif")
