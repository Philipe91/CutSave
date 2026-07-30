"""Theme Engine: paletas, contraste WCAG AA, persistência, JSON e diálogo."""

from __future__ import annotations

import os

import pytest
from app.presentation import theme
from app.presentation.themes import palettes
from app.presentation.themes.manager import ThemeManager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---- paletas ----
def test_toda_paleta_define_todos_os_tokens():
    for key, (label, colors, _dark) in palettes.THEMES.items():
        faltando = [t for t in palettes.COLOR_TOKENS if t not in colors]
        assert not faltando, f"{label}: tokens faltando {faltando}"


def test_contraste_wcag_aa_em_todos_os_temas():
    # nunca texto cinza sobre fundo cinza (brief): AA = 4.5:1 p/ texto normal
    for key, (label, c, _d) in palettes.THEMES.items():
        for fundo in ("BG", "SURFACE", "SURFACE_ALT", "SIDEBAR", "TOOLBAR"):
            razao = palettes.contrast(c["TEXT"], c[fundo])
            assert razao >= 4.5, f"{label}: TEXT sobre {fundo} = {razao:.2f}"
        razao2 = palettes.contrast(c["TEXT_SECONDARY"], c["SURFACE"])
        assert razao2 >= 4.5, f"{label}: TEXT_SECONDARY = {razao2:.2f}"


def test_texto_sobre_o_acento_legivel_em_todos_os_presets():
    # C10: o texto do botao de destaque (GERAR FACA etc.) precisa de AA (4.5:1)
    # sobre o acento em TODOS os presets que o app oferece — Emerald/Graphite/
    # Turquesa reprovavam com o branco fixo.
    for nome, base, accent, extra in palettes.PRESETS:
        colors, _ = palettes.resolve(base, accent=accent, overrides=extra)
        razao = palettes.contrast(colors["ICON_ON_ACCENT"], colors["ACCENT"])
        assert razao >= 4.5, f"{nome}: ICON_ON_ACCENT sobre ACCENT = {razao:.2f}"
    # temas base sem acento custom tambem
    for key in palettes.THEMES:
        colors, _ = palettes.resolve(key)
        razao = palettes.contrast(colors["ICON_ON_ACCENT"], colors["ACCENT"])
        assert razao >= 4.5, f"{key}: ICON_ON_ACCENT sobre ACCENT = {razao:.2f}"


def test_tooltip_legivel_em_todos_os_temas():
    # C9: o QSS do tooltip usa fundo=TEXT e texto=BG — nos temas escuros o
    # antigo texto branco fixo sumia no fundo branco (1.0:1)
    for key, (label, c, _d) in palettes.THEMES.items():
        razao = palettes.contrast(c["BG"], c["TEXT"])
        assert razao >= 4.5, f"{label}: tooltip (BG sobre TEXT) = {razao:.2f}"


def test_acento_derivado_muda_selecao_e_links():
    colors, _ = palettes.resolve("dark", accent="#22c55e")
    assert colors["ACCENT"] == "#22c55e"
    assert colors["INFO"] == "#22c55e"          # links seguem o acento
    assert colors["SELECTED"] != palettes.DARK["SELECTED"]  # seleção recalculada
    assert colors["ACCENT_HOVER"] != colors["ACCENT"]


def test_override_do_usuario_vence_a_base():
    colors, _ = palettes.resolve("light", overrides={"CANVAS_BG": "#123456"})
    assert colors["CANVAS_BG"] == "#123456"
    # chave desconhecida e ignorada com seguranca
    colors2, _ = palettes.resolve("light", overrides={"NAO_EXISTE": "#000"})
    assert "NAO_EXISTE" not in colors2


def test_presets_apontam_para_temas_validos():
    for nome, base, accent, extra in palettes.PRESETS:
        assert base in palettes.THEMES, nome
        assert accent.startswith("#"), nome
        assert all(k in palettes.COLOR_TOKENS for k in extra), nome


# ---- tokens dinamicos ----
def test_set_palette_troca_e_restaura_tokens():
    original = theme.current_palette()
    try:
        theme.set_palette(palettes.DARK, dark_ui=True)
        assert theme.BG == palettes.DARK["BG"]
        assert theme.is_dark()
    finally:
        theme.set_palette(original, dark_ui=False)
    assert theme.BG == palettes.LIGHT["BG"] and not theme.is_dark()


# ---- manager (QSettings isolado em arquivo temporario) ----
@pytest.fixture
def temp_manager(tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings

    ini = str(tmp_path / "temas.ini")

    def _factory(*_a, **_k):
        return QSettings(ini, QSettings.IniFormat)

    import importlib
    mgr_mod = importlib.import_module("app.presentation.themes.manager")
    monkeypatch.setattr(mgr_mod, "QSettings", _factory)
    original = theme.current_palette()
    yield ThemeManager
    theme.set_palette(original, dark_ui=False)


def test_manager_persiste_e_restaura(temp_manager):
    m = temp_manager()
    m.theme_key, m.accent = "midnight", "#8b5cf6"
    m.overrides = {"CANVAS_BG": "#0b0e14"}
    m._save()
    # "proxima abertura": novo manager le do mesmo QSettings
    m2 = temp_manager()
    assert m2.theme_key == "midnight"
    assert m2.accent == "#8b5cf6"
    assert m2.overrides == {"CANVAS_BG": "#0b0e14"}


def test_manager_exporta_e_importa_json(temp_manager, tmp_path):
    m = temp_manager()
    m.theme_key, m.accent = "carbon", "#f97316"
    m.overrides = {"SHEET": "#fafafa"}
    arq = tmp_path / "Minha Empresa.json"
    m.export_json(str(arq))

    m2 = temp_manager()
    m2.import_json(str(arq))
    assert m2.theme_key == "carbon"
    assert m2.accent == "#f97316"
    assert m2.overrides == {"SHEET": "#fafafa"}

    ruim = tmp_path / "x.json"
    ruim.write_text('{"qualquer": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        m2.import_json(str(ruim))


def test_manager_aplica_ao_vivo_e_reseta(temp_manager):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    m = temp_manager()
    m.set_theme("dark")
    assert theme.BG == palettes.DARK["BG"]  # tokens trocaram AO VIVO
    m.reset()
    assert theme.BG == palettes.LIGHT["BG"]  # PrintNest Original de volta


# ---- dialogo ----
def test_dialogo_personalizar_abre_e_cancela_restaura(temp_manager):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from app.presentation.themes.settings_dialog import ThemeSettingsDialog

    m = temp_manager()
    m.reset()
    dlg = ThemeSettingsDialog(m)
    # live preview: trocar o tema pelo combo aplica na hora
    dlg._theme_combo.setCurrentIndex(dlg._theme_combo.findData("dark"))
    assert theme.BG == palettes.DARK["BG"]
    # cancelar devolve o estado de quando abriu
    dlg._cancel()
    assert theme.BG == palettes.LIGHT["BG"]
    dlg.deleteLater()
