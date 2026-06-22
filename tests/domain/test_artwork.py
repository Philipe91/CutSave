from dataclasses import FrozenInstanceError

import pytest
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


def _artwork(**kw):
    base = dict(
        id="a1",
        name="logo",
        file_format=FileFormat.PDF,
        size=Size(40, 20),
        kind=ArtKind.RETANGULAR,
    )
    base.update(kw)
    return Artwork(**base)


def test_artwork_sem_faca():
    a = _artwork()
    assert a.has_cut is False
    assert a.file_format is FileFormat.PDF


def test_artwork_com_faca():
    contour = CutContour([Point2D(0, 0), Point2D(40, 0), Point2D(40, 20)])
    a = _artwork(cut_contour=contour)
    assert a.has_cut is True


def test_artwork_exige_id():
    with pytest.raises(ValidationError):
        _artwork(id="")


def test_artwork_imutavel():
    a = _artwork()
    with pytest.raises(FrozenInstanceError):
        a.name = "outro"
