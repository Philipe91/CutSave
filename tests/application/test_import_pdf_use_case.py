from app.application.ports.pdf_importer import IPdfImporter
from app.application.use_cases.import_pdf import ImportPdfUseCase
from app.domain.geometry import Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat


class _FakeImporter(IPdfImporter):
    def __init__(self, artworks):
        self._artworks = artworks
        self.called_with = None

    def import_artworks(self, path):
        self.called_with = path
        return self._artworks


def _artwork():
    return Artwork(
        id="f#p1",
        name="f (pagina 1)",
        file_format=FileFormat.PDF,
        size=Size(10, 10),
        kind=ArtKind.RETANGULAR,
    )


def test_use_case_delega_para_importer():
    art = _artwork()
    fake = _FakeImporter([art])
    use_case = ImportPdfUseCase(fake)

    result = use_case.execute("arquivo.pdf")

    assert result == [art]
    assert fake.called_with == "arquivo.pdf"
