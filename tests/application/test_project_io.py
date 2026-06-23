import json

import pytest
from app.application.project_io import (
    PROJECT_VERSION,
    ProjectDocument,
    ProjectFile,
    ProjectStore,
)
from app.shared.errors import ProjectError


def _doc():
    return ProjectDocument(
        files=[
            ProjectFile("a.pdf", quantity=3, rotation=90),
            ProjectFile("b.pdf", quantity=1, rotation=0),
        ],
        settings={"material_width": 1300.0, "offset": 3.0, "shared_faca": True},
    )


def test_round_trip_preserva_arquivos_e_parametros(tmp_path):
    path = tmp_path / "trabalho.printnest"
    store = ProjectStore()
    store.save(path, _doc())

    loaded = store.load(path)
    assert loaded.version == PROJECT_VERSION
    assert [(f.path, f.quantity, f.rotation) for f in loaded.files] == [
        ("a.pdf", 3, 90),
        ("b.pdf", 1, 0),
    ]
    assert loaded.settings["material_width"] == 1300.0
    assert loaded.settings["shared_faca"] is True


def test_arquivo_salvo_tem_versao(tmp_path):
    path = tmp_path / "x.printnest"
    ProjectStore().save(path, _doc())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == PROJECT_VERSION


def test_load_projeto_inexistente_levanta(tmp_path):
    with pytest.raises(ProjectError):
        ProjectStore().load(tmp_path / "nao_existe.printnest")


def test_load_json_invalido_levanta(tmp_path):
    path = tmp_path / "ruim.printnest"
    path.write_text("isto nao e json", encoding="utf-8")
    with pytest.raises(ProjectError):
        ProjectStore().load(path)


def test_sem_versao_levanta():
    with pytest.raises(ProjectError):
        ProjectDocument.from_dict({"files": [], "settings": {}})


def test_versao_futura_levanta():
    with pytest.raises(ProjectError):
        ProjectDocument.from_dict({"version": PROJECT_VERSION + 1, "files": []})


def test_from_dict_tolera_campos_ausentes():
    doc = ProjectDocument.from_dict({"version": PROJECT_VERSION})
    assert doc.files == []
    assert doc.settings == {}


def test_project_file_defaults_em_dados_parciais():
    pf = ProjectFile.from_dict({"path": "c.pdf"})
    assert (pf.path, pf.quantity, pf.rotation) == ("c.pdf", 1, 0)
