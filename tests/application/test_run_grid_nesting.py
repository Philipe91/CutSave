import pytest
from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.material import Material
from app.shared.errors import ValidationError


def _artwork(art_id, w, h, faca=None):
    return Artwork(
        id=art_id,
        name=art_id,
        file_format=FileFormat.PDF,
        size=Size(w, h),
        kind=ArtKind.RETANGULAR,
        cut_contour=faca,
    )


def _rect_faca(w, h):
    return CutContour([Point2D(0, 0), Point2D(w, 0), Point2D(w, h), Point2D(0, h)])


def _material():
    return Material("UV", width=1300, spacing=5, margin=0)


def test_posiciona_multiplas_artes():
    arts = [_artwork(f"a{i}", 320, 92) for i in range(4)]
    layout = RunGridNestingUseCase().execute(arts, _material())
    assert layout.item_count == 4
    assert [it.artwork_id for it in layout.items] == ["a0", "a1", "a2", "a3"]


def test_usa_faca_como_footprint_quando_existe():
    # arte 320x92, faca 326x98 -> nesting usa 326 de largura
    arts = [
        _artwork("a0", 320, 92, faca=_rect_faca(326, 98)),
        _artwork("a1", 320, 92, faca=_rect_faca(326, 98)),
    ]
    layout = RunGridNestingUseCase().execute(arts, _material())
    # segunda peca em x = 326 + 5 (espacamento)
    assert round(layout.items[1].position.x, 1) == 331.0


def test_usa_tamanho_da_arte_sem_faca():
    art = _artwork("a0", 100, 50)
    layout = RunGridNestingUseCase().execute([art, _artwork("a1", 100, 50)], _material())
    assert round(layout.items[1].position.x, 1) == 105.0


def test_sem_artes_falha():
    with pytest.raises(ValidationError):
        RunGridNestingUseCase().execute([], _material())
