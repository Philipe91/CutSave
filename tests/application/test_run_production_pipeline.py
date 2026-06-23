import pytest
from app.application.ports.image_importer import ImportedImage
from app.application.use_cases.run_production_pipeline import RunProductionPipelineUseCase
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.image_artwork import ImageArtwork, ImageKind
from app.domain.model.material import Material
from app.shared.errors import ImageImportError, ValidationError


def _artwork(art_id, w=100.0, h=50.0):
    return Artwork(id=art_id, name=art_id, file_format=FileFormat.PDF,
                   size=Size(w, h), kind=ArtKind.RETANGULAR)


class _FakeImport:
    def __init__(self, by_path):
        self._by_path = by_path

    def execute(self, path, box="auto"):
        return self._by_path[path]


class _FakeImageImport:
    def execute(self, path, *, sensitivity=50.0, ignore_white=True):
        art = ImageArtwork(
            id=f"{path}#img", name=path, file_format=FileFormat.PNG,
            size=Size(40, 40), kind=ArtKind.RASTER,
            cut_contour=CutContour([Point2D(0, 0), Point2D(40, 0), Point2D(40, 40)]),
            dpi=150.0, image_kind=ImageKind.IMAGE_ALPHA,
        )
        return ImportedImage(art, render_path=f"cache/{path}.png")


def test_pipeline_importa_imagem_e_usa_contorno_detectado():
    pipeline = RunProductionPipelineUseCase(
        _FakeImport({}), image_uc=_FakeImageImport()
    )
    result = pipeline.execute(["logo.png"], Material("UV", width=1300), 3.0)
    art = result.artworks[0]
    assert isinstance(art, ImageArtwork)
    assert art.has_cut  # contorno detectado (nao a faca retangular)
    # render usa o caminho de cache; origem mantem o caminho do usuario
    assert result.sources["logo.png#img"] == ("cache/logo.png.png", 0)
    assert result.origins["logo.png#img"] == "logo.png"


def test_pipeline_mistura_pdf_e_imagem():
    pipeline = RunProductionPipelineUseCase(
        _FakeImport({"a.pdf": [_artwork("a#p1")]}), image_uc=_FakeImageImport()
    )
    result = pipeline.execute(["a.pdf", "logo.png"], Material("UV", width=1300), 3.0)
    formats = {a.file_format for a in result.artworks}
    assert formats == {FileFormat.PDF, FileFormat.PNG}


def test_pipeline_imagem_sem_importador_configurado_falha():
    pipeline = RunProductionPipelineUseCase(_FakeImport({}))  # sem image_uc
    with pytest.raises(ImageImportError):
        pipeline.execute(["logo.png"], Material("UV", width=1300), 3.0)


def test_pipeline_importa_aplica_faca_e_nesting():
    imp = _FakeImport({
        "a.pdf": [_artwork("a#p1"), _artwork("a#p2")],
        "b.pdf": [_artwork("b#p1")],
    })
    pipeline = RunProductionPipelineUseCase(imp)
    material = Material("UV", width=1300, spacing=5)

    result = pipeline.execute(["a.pdf", "b.pdf"], material, offset_mm=3.0)

    assert len(result.sheets) == 1  # chapa aberta (sem altura)
    assert result.sheets[0].item_count == 3
    assert all(a.has_cut for a in result.artworks)  # faca aplicada
    assert result.sources["a#p2"] == ("a.pdf", 1)
    assert result.sources["b#p1"] == ("b.pdf", 0)


def test_pipeline_divide_em_varias_chapas():
    # 4 pecas 100x50 (faca +0); chapa 1300 de largura -> varias por linha;
    # altura pequena forca multiplas chapas
    imp = _FakeImport({"a.pdf": [_artwork(f"a#p{i}", 100, 50) for i in range(4)]})
    pipeline = RunProductionPipelineUseCase(imp)
    material = Material("UV", width=120, spacing=0)  # 1 peca por linha
    result = pipeline.execute(["a.pdf"], material, offset_mm=0.0, sheet_height=60)
    # cada chapa cabe 1 linha (50mm) -> 4 chapas
    assert len(result.sheets) == 4


def test_pipeline_reporta_progresso():
    imp = _FakeImport({"a.pdf": [_artwork("a#p1")], "b.pdf": [_artwork("b#p1")]})
    pipeline = RunProductionPipelineUseCase(imp)
    chamadas = []
    pipeline.execute(["a.pdf", "b.pdf"], Material("UV", width=1300), 3.0,
                     on_progress=lambda d, t: chamadas.append((d, t)))
    assert chamadas == [(1, 2), (2, 2)]


def test_pipeline_sem_artes_falha():
    pipeline = RunProductionPipelineUseCase(_FakeImport({"a.pdf": []}))
    with pytest.raises(ValidationError):
        pipeline.execute(["a.pdf"], Material("UV", width=1300), 3.0)
