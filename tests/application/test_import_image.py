from app.application.ports.image_importer import IImageImporter, ImportedImage
from app.application.use_cases.import_image import ImportImageUseCase
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.image_artwork import ImageArtwork, ImageKind


class _FakeImporter(IImageImporter):
    def __init__(self):
        self.calls = []

    def import_image(self, path, *, sensitivity=50.0, ignore_white=True):
        self.calls.append((path, sensitivity, ignore_white))
        art = ImageArtwork(
            id="x#1", name="x", file_format=FileFormat.PNG, size=Size(10, 10),
            kind=ArtKind.RASTER,
            cut_contour=CutContour([Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)]),
            dpi=150.0, image_kind=ImageKind.IMAGE_ALPHA,
        )
        return ImportedImage(art, path)


def test_use_case_repassa_parametros_ao_importador():
    fake = _FakeImporter()
    out = ImportImageUseCase(fake).execute("a.png", sensitivity=80, ignore_white=False)
    assert isinstance(out.artwork, ImageArtwork)
    assert fake.calls == [("a.png", 80, False)]
