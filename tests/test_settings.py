import pytest
from app.shared.config.settings import AppSettings, SettingsStore
from app.shared.errors import ConfigError


def test_load_or_create_cria_defaults(tmp_path):
    store = SettingsStore(tmp_path / "config.json")
    settings = store.load_or_create()
    assert settings.language == "pt-BR"
    assert settings.log_level == "INFO"
    assert (tmp_path / "config.json").exists()


def test_roundtrip_persiste_alteracoes(tmp_path):
    store = SettingsStore(tmp_path / "config.json")
    settings = store.load_or_create()
    settings.log_level = "DEBUG"
    store.save(settings)
    assert store.load().log_level == "DEBUG"


def test_chaves_desconhecidas_sao_ignoradas(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"language": "en", "bogus": 123}', encoding="utf-8")
    assert SettingsStore(path).load().language == "en"


def test_json_invalido_levanta_config_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{nao e json", encoding="utf-8")
    with pytest.raises(ConfigError):
        SettingsStore(path).load()


def test_to_dict_from_dict_simetrico():
    original = AppSettings(language="pt-BR", log_level="WARNING")
    assert AppSettings.from_dict(original.to_dict()) == original
