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


# ---- tema importado invalido nao pode travar a abertura (13/10/2026) ----
def test_normalizar_hex_aceita_formatos_validos_e_recusa_o_resto():
    assert palettes.normalize_hex("#22C55E") == "#22c55e"
    assert palettes.normalize_hex("#f00") == "#ff0000"
    for ruim in ("red", "", "#12345", "#gggggg", None, 123, "22c55e"):
        assert palettes.normalize_hex(ruim) is None, ruim


def test_importar_tema_com_cor_invalida_nao_salva_nada(temp_manager, tmp_path):
    import json as _json

    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    m = temp_manager()
    m.reset()
    arq = tmp_path / "ruim.json"
    arq.write_text(_json.dumps({"printnest_theme": 1, "base": "dark",
                                "accent": "red", "overrides": {}}),
                   encoding="utf-8")
    with pytest.raises(ValueError):
        m.import_json(str(arq))
    # nada foi persistido: a proxima abertura le o tema anterior
    m2 = temp_manager()
    assert m2.theme_key == "light" and m2.accent == ""


def test_importar_tema_curto_normaliza_e_descarta_override_invalido(
        temp_manager, tmp_path):
    import json as _json

    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    m = temp_manager()
    arq = tmp_path / "curto.json"
    arq.write_text(_json.dumps({
        "printnest_theme": 1, "base": "dark", "accent": "#f00",
        "overrides": {"SHEET": "#abc", "BG": "azul"}}), encoding="utf-8")
    m.import_json(str(arq))
    assert m.accent == "#ff0000"
    assert m.overrides == {"SHEET": "#aabbcc"}


def test_abertura_com_tema_salvo_corrompido_volta_ao_padrao(temp_manager):
    # cenario real: QSettings ja gravado com acento "red" por uma versao antiga
    # -> toda abertura caia com ValueError. Agora abre no PrintNest Original.
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import importlib
    mgr_mod = importlib.import_module("app.presentation.themes.manager")
    m = temp_manager()
    m._settings.setValue("theme/base", "dark")
    m._settings.setValue("theme/accent", "red")
    m._settings.setValue("theme/overrides", '{"BG": "#zzz", "SHEET": "#abc"}')
    m._settings.sync()
    antigo = mgr_mod._manager
    mgr_mod._manager = None
    try:
        mgr_mod.apply_startup(app)  # nao pode levantar
        novo = mgr_mod._manager
        assert novo.accent == ""
        assert "BG" not in novo.overrides
    finally:
        mgr_mod._manager = antigo


def test_abertura_cai_no_padrao_se_aplicar_o_tema_falhar(temp_manager,
                                                         monkeypatch):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import importlib
    mgr_mod = importlib.import_module("app.presentation.themes.manager")
    m = temp_manager()
    m.theme_key = "dark"
    chamadas = []
    original = mgr_mod.palettes.resolve

    def _quebra_uma_vez(*a, **k):
        if not chamadas:
            chamadas.append(1)
            raise ValueError("paleta corrompida")
        return original(*a, **k)

    monkeypatch.setattr(mgr_mod.palettes, "resolve", _quebra_uma_vez)
    antigo = mgr_mod._manager
    mgr_mod._manager = m
    try:
        mgr_mod.apply_startup(app)
        assert m.theme_key == "light"
        assert theme.BG == palettes.LIGHT["BG"]
    finally:
        mgr_mod._manager = antigo


# ---- "Automatico (segue o Windows)" nao pode fixar o esquema (13/10/2026) ----
@pytest.fixture
def spy_esquema(monkeypatch):
    from PySide6.QtGui import QStyleHints

    chamadas: list = []
    monkeypatch.setattr(QStyleHints, "setColorScheme",
                        lambda self, s: chamadas.append(s))
    monkeypatch.setattr(QStyleHints, "unsetColorScheme",
                        lambda self: chamadas.append("unset"))
    return chamadas


def test_modo_automatico_nao_fixa_o_esquema_do_windows(temp_manager,
                                                       spy_esquema):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    m = temp_manager()
    m.set_theme("dark")
    assert spy_esquema[-1] != "unset"  # tema fixo: fixa o esquema nativo
    spy_esquema.clear()
    m.set_theme("auto")
    # antes: setColorScheme(Light/Dark) PRENDIA o esquema e o app parava de
    # acompanhar o Windows; agora so solta (unset) e nunca fixa
    assert "unset" in spy_esquema
    assert all(c == "unset" for c in spy_esquema), spy_esquema
    m.reset()


def test_abertura_em_modo_automatico_nao_fixa_o_esquema(temp_manager,
                                                        spy_esquema):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import importlib
    mgr_mod = importlib.import_module("app.presentation.themes.manager")
    m = temp_manager()
    m.theme_key = "auto"
    antigo = mgr_mod._manager
    mgr_mod._manager = m
    try:
        mgr_mod.apply_startup(app)
        assert spy_esquema and all(c == "unset" for c in spy_esquema)
    finally:
        mgr_mod._manager = antigo
        m.theme_key = "light"


# ---- Esc / X do dialogo descartam as mudancas (13/10/2026) ----
def test_dialogo_esc_restaura_como_cancelar(temp_manager):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from app.presentation.themes.settings_dialog import ThemeSettingsDialog

    m = temp_manager()
    m.reset()
    dlg = ThemeSettingsDialog(m)
    dlg._theme_combo.setCurrentIndex(dlg._theme_combo.findData("dark"))
    assert theme.BG == palettes.DARK["BG"]
    dlg.reject()  # o que Esc e o X da janela chamam
    assert theme.BG == palettes.LIGHT["BG"]
    assert m.theme_key == "light"
    dlg.deleteLater()


def test_dialogo_ok_mantem_as_mudancas(temp_manager):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from app.presentation.themes.settings_dialog import ThemeSettingsDialog

    m = temp_manager()
    m.reset()
    dlg = ThemeSettingsDialog(m)
    dlg._theme_combo.setCurrentIndex(dlg._theme_combo.findData("dark"))
    dlg.accept()
    assert m.theme_key == "dark"
    m.reset()
    dlg.deleteLater()


def test_combo_do_tema_acompanha_preset_e_restaurar(temp_manager):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from app.presentation.themes.settings_dialog import ThemeSettingsDialog

    m = temp_manager()
    m.reset()
    dlg = ThemeSettingsDialog(m)
    nome, base, *_ = next(p for p in palettes.PRESETS if p[1] != "light")
    m.apply_preset(nome)
    assert dlg._theme_combo.currentData() == base
    m.reset()  # "Restaurar padrao"
    assert dlg._theme_combo.currentData() == "light"
    dlg.deleteLater()
