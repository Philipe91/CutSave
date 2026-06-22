import math

import pytest
from app.application.ports.vector_extractor import IVectorExtractor
from app.application.use_cases.generate_vector_cut import GenerateVectorCutUseCase
from app.domain.geometry import Polygon as GeoPolygon
from app.domain.geometry import Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat


def _circle(cx, cy, r, n=64):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)]


class _FakeExtractor(IVectorExtractor):
    def __init__(self, rings):
        self._rings = rings
        self.called_with = None

    def extract_rings(self, path, page_index=0):
        self.called_with = (path, page_index)
        return self._rings


def _artwork():
    return Artwork(
        id="mack#p2",
        name="mack (pagina 2)",
        file_format=FileFormat.PDF,
        size=Size(700, 700),
        kind=ArtKind.VETORIAL,
    )


def test_gera_e_armazena_contorno():
    fake = _FakeExtractor([_circle(0, 0, 50)])
    result = GenerateVectorCutUseCase(fake).execute(_artwork(), "x.pdf", page_index=1)
    assert result.has_cut is True
    assert GeoPolygon(result.cut_contour.points).area == pytest.approx(math.pi * 50**2, rel=0.02)
    assert fake.called_with == ("x.pdf", 1)


def test_nao_muta_artwork_original():
    original = _artwork()
    GenerateVectorCutUseCase(_FakeExtractor([_circle(0, 0, 50)])).execute(original, "x.pdf")
    assert original.cut_contour is None
