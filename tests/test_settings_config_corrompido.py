"""config.json estragado NUNCA pode impedir o PrintNest de abrir (13/10/2026).

O load_or_create roda antes do log de crash e do excepthook: uma excecao
aqui e o .exe que "abre e fecha" para sempre, sem rastro. A auditoria achou
quatro jeitos de chegar la com um config editado a mao ou gravado por outra
ferramenta: JSON que nao e objeto ([] ou null), arquivo salvo em ANSI pelo
Bloco de Notas, BOM do UTF-8 e campo com tipo errado passando direto para a
UI (material_width = "abc" estourava so depois, no meio da tela).
"""

from __future__ import annotations

import pytest
from app.shared.config.settings import AppSettings, SettingsStore
from app.shared.errors import ConfigError


@pytest.mark.parametrize("conteudo", [b"[]", b"null", b"42", b'"texto"', b"\x00" * 64])
def test_json_que_nao_e_objeto_abre_com_padroes(tmp_path, conteudo):
    path = tmp_path / "config.json"
    path.write_bytes(conteudo)
    with pytest.raises(ConfigError):
        SettingsStore(path).load()
    settings = SettingsStore(path).load_or_create()
    assert settings == AppSettings()
    assert (tmp_path / "config.json.corrompido").exists()


def test_arquivo_ansi_do_bloco_de_notas_e_lido(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes('{"last_dir": "C:\\\\Usuários\\\\Gráfica", "unit": "mm"}'.encode("cp1252"))
    settings = SettingsStore(path).load_or_create()
    assert settings.last_dir == "C:\\Usuários\\Gráfica"
    assert settings.unit == "mm"


def test_bom_utf8_e_aceito_sem_perder_a_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b'\xef\xbb\xbf{"unit": "mm"}')
    assert SettingsStore(path).load_or_create().unit == "mm"
    assert not (tmp_path / "config.json.corrompido").exists()


def test_campo_com_tipo_errado_volta_ao_padrao_so_ele(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"material_width": "abc", "export_dpi": null, "spacing": 7,'
        ' "export_quality": 90.0, "snap_enabled": "sim", "auto_rotate": true,'
        ' "unit": 5, "material_height": 1e999}',
        encoding="utf-8",
    )
    s = SettingsStore(path).load_or_create()
    padrao = AppSettings()
    assert s.material_width == padrao.material_width   # "abc" -> padrao
    assert s.export_dpi == padrao.export_dpi           # null -> padrao
    assert s.spacing == 7.0 and isinstance(s.spacing, float)  # int vale float
    assert s.export_quality == 90 and isinstance(s.export_quality, int)
    assert s.snap_enabled is padrao.snap_enabled       # "sim" nao e bool
    assert s.auto_rotate is True                       # o que veio certo fica
    assert s.unit == padrao.unit
    assert s.material_height == padrao.material_height  # infinito nao e medida


def test_from_dict_nao_aceita_bool_como_numero():
    s = AppSettings.from_dict({"rotation": True, "spacing": False})
    assert s.rotation == AppSettings().rotation
    assert s.spacing == AppSettings().spacing
