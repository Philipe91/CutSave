import pytest
from app.application.use_cases.run_production_pipeline import RunProductionPipelineUseCase
from app.domain.geometry import Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.material import Material
from app.shared.errors import ValidationError


def _artwork(art_id, w=100.0, h=50.0):
    return Artwork(id=art_id, name=art_id, file_format=FileFormat.PDF,
                   size=Size(w, h), kind=ArtKind.RETANGULAR)


class _FakeImport:
    def __init__(self, by_path):
        self._by_path = by_path

    def execute(self, path, box="auto"):
        return self._by_path[path]


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
