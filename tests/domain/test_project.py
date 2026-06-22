import pytest
from app.domain.geometry import Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.material import Material
from app.domain.model.project import Project
from app.shared.errors import ValidationError


def _artwork(art_id="a1"):
    return Artwork(
        id=art_id,
        name="logo",
        file_format=FileFormat.PNG,
        size=Size(40, 20),
        kind=ArtKind.RETANGULAR,
    )


def test_project_gera_id_automatico():
    p = Project(name="Lote 1")
    assert p.id
    assert Project(name="Lote 2").id != p.id


def test_add_e_get_artwork():
    p = Project(name="Lote")
    art = _artwork()
    p.add_artwork(art)
    assert p.get_artwork("a1") is art


def test_add_artwork_duplicada_falha():
    p = Project(name="Lote")
    p.add_artwork(_artwork())
    with pytest.raises(ValidationError):
        p.add_artwork(_artwork())


def test_remove_artwork():
    p = Project(name="Lote")
    p.add_artwork(_artwork())
    p.remove_artwork("a1")
    assert p.get_artwork("a1") is None


def test_remove_inexistente_falha():
    with pytest.raises(ValidationError):
        Project(name="Lote").remove_artwork("x")


def test_set_material():
    p = Project(name="Lote")
    material = Material(name="Adesivo", width=1000.0)
    p.set_material(material)
    assert p.material is material


def test_project_exige_nome():
    with pytest.raises(ValidationError):
        Project(name="  ")
