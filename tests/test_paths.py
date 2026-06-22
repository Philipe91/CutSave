from pathlib import Path

from app.shared.config.paths import AppPaths


def test_default_usa_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PRINTNEST_HOME", str(tmp_path / "pn"))
    paths = AppPaths.default()
    assert paths.home == tmp_path / "pn"
    assert paths.config_file == tmp_path / "pn" / "config.json"


def test_ensure_cria_diretorios(monkeypatch, tmp_path):
    monkeypatch.setenv("PRINTNEST_HOME", str(tmp_path / "pn"))
    paths = AppPaths.default().ensure()
    assert paths.logs_dir.is_dir()
    assert paths.data_dir.is_dir()
    assert paths.cache_dir.is_dir()


def test_default_sem_env_usa_appdata(monkeypatch, tmp_path):
    monkeypatch.delenv("PRINTNEST_HOME", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    paths = AppPaths.default()
    assert paths.home == Path(tmp_path) / "PrintNest"
