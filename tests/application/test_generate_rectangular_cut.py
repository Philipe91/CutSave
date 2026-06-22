import pytest
from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
from app.domain.geometry import Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.shared.errors import ValidationError


def _artwork(w=320.0, h=92.0):
    return Artwork(
        id="bike#p1",
        name="bike (pagina 1)",
        file_format=FileFormat.PDF,
        size=Size(w, h),
        kind=ArtKind.RETANGULAR,
    )


def test_gera_faca_e_armazena_na_artwork():
    result = GenerateRectangularCutUseCase().execute(_artwork())
    assert result.has_cut is True
    assert result.cut_contour.size == Size(320, 92)


def test_offset_externo():
    result = GenerateRectangularCutUseCase().execute(_artwork(), offset_mm=3.0)
    assert result.cut_contour.size == Size(326, 98)


def test_offset_interno():
    result = GenerateRectangularCutUseCase().execute(_artwork(70, 50), offset_mm=-1.0)
    assert result.cut_contour.size == Size(68, 48)


def test_nao_muta_artwork_original():
    original = _artwork()
    GenerateRectangularCutUseCase().execute(original, offset_mm=5.0)
    assert original.cut_contour is None  # imutavel: original intacto


def test_offset_interno_excessivo_propaga_erro():
    with pytest.raises(ValidationError):
        GenerateRectangularCutUseCase().execute(_artwork(70, 50), offset_mm=-30.0)
