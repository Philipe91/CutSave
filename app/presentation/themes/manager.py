"""ThemeManager — orquestra o Theme Engine (100% desacoplado da lógica).

Responsabilidades:
- resolver a paleta atual (tema base + acento + ajustes do usuário);
- injetar nos tokens de `theme` e reaplicar o QSS global (uma passada, cacheado
  pelo Qt) — LIVE, sem reiniciar;
- persistir tudo em QSettings e restaurar na próxima abertura;
- exportar/importar temas em JSON;
- modo "auto": segue o claro/escuro do Windows (colorSchemeChanged).

Integração mínima: `apply_startup(app)` no lugar de `theme.apply(app)` e, na
janela, conectar `manager().theme_changed` a um redraw do canvas.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtWidgets import QApplication

from app.presentation import theme
from app.presentation.themes import palettes

_ORG, _APP = "PrintNest", "PrintNestPremium"
AUTO = "auto"


class ThemeManager(QObject):
    """Estado do tema do usuário + aplicação ao vivo."""

    theme_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings(_ORG, _APP)
        base = str(self._settings.value("theme/base", "light"))
        self.theme_key: str = base if base in (*palettes.THEMES, AUTO) else "light"
        # cores lidas do disco passam pela mesma validacao do import: um
        # QSettings gravado por versao antiga com acento "red" nao pode mais
        # derrubar a abertura (13/10/2026) — cor invalida e simplesmente ignorada
        self.accent: str = (
            palettes.normalize_hex(self._settings.value("theme/accent", "")) or ""
        )
        try:
            raw = json.loads(str(self._settings.value("theme/overrides", "{}")))
        except (TypeError, ValueError):
            raw = {}
        self.overrides: dict = _clean_overrides(raw)
        self._auto_hooked = False

    # ---- resolução ----
    def _effective_key(self) -> str:
        if self.theme_key != AUTO:
            return self.theme_key
        app = QApplication.instance()
        if app is not None:
            # vindo de um tema fixo nesta sessao o esquema ainda esta preso
            # (setColorScheme): soltar ANTES de ler, senao colorScheme()
            # devolve o esquema fixado e nao o do Windows
            app.styleHints().unsetColorScheme()
        scheme = app.styleHints().colorScheme() if app else Qt.ColorScheme.Light
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"

    def palette(self) -> tuple[dict, bool]:
        return palettes.resolve(
            self._effective_key(), self.accent or None, self.overrides
        )

    # ---- aplicação (live) ----
    def apply(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        colors, dark_ui = self.palette()
        theme.set_palette(colors, dark_ui)
        # cache de ícones guarda a COR renderizada: esvazia para os próximos
        # ícones (toasts, diálogos novos) saírem na cor do tema novo
        from app.presentation import icons
        icons.clear_cache()
        # esquema nativo + QSS reconstruído dos tokens novos (no automático o
        # esquema fica solto para continuar seguindo o Windows)
        theme.apply(app, follow_system=self.theme_key == AUTO)
        if self.theme_key == AUTO and not self._auto_hooked:
            app.styleHints().colorSchemeChanged.connect(lambda _: self.apply())
            self._auto_hooked = True
        self.theme_changed.emit()

    # ---- mutações (persistem e aplicam na hora) ----
    def set_theme(self, key: str) -> None:
        self.theme_key = key
        self._save()
        self.apply()

    def set_accent(self, hexcolor: str) -> None:
        self.accent = hexcolor
        self._save()
        self.apply()

    def set_override(self, token: str, hexcolor: str) -> None:
        if token in palettes.COLOR_TOKENS:
            self.overrides[token] = hexcolor
            self._save()
            self.apply()

    def apply_preset(self, name: str) -> None:
        for pname, base, accent, extra in palettes.PRESETS:
            if pname == name:
                self.theme_key = base
                self.accent = accent
                self.overrides = dict(extra)
                self._save()
                self.apply()
                return

    def reset(self) -> None:
        """Volta ao PrintNest Original (claro, acento azul, sem ajustes)."""
        self.theme_key = "light"
        self.accent = ""
        self.overrides = {}
        self._save()
        self.apply()

    def snapshot(self) -> dict:
        """Estado atual (para Cancelar do diálogo restaurar)."""
        return {
            "theme": self.theme_key, "accent": self.accent,
            "overrides": dict(self.overrides),
        }

    def restore(self, snap: dict) -> None:
        self.theme_key = snap.get("theme", "light")
        self.accent = snap.get("accent", "")
        self.overrides = dict(snap.get("overrides", {}))
        self._save()
        self.apply()

    def _save(self) -> None:
        self._settings.setValue("theme/base", self.theme_key)
        self._settings.setValue("theme/accent", self.accent)
        self._settings.setValue("theme/overrides", json.dumps(self.overrides))

    # ---- exportar / importar (JSON) ----
    def export_json(self, path: str) -> None:
        doc = {
            "printnest_theme": 1,
            "base": self.theme_key,
            "accent": self.accent,
            "overrides": self.overrides,
        }
        Path(path).write_text(
            json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def import_json(self, path: str) -> None:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if doc.get("printnest_theme") != 1:
            raise ValueError("Arquivo não é um tema do PrintNest.")
        base = str(doc.get("base", "light"))
        # valida TUDO antes de mexer no estado/QSettings: antes o acento era
        # salvo cru e so o apply() descobria que "red" nao e hex — o import
        # mostrava o aviso, mas o lixo ja estava gravado e a PROXIMA abertura
        # do app caia sempre (13/10/2026)
        accent_raw = doc.get("accent", "") or ""
        accent = palettes.normalize_hex(accent_raw) if accent_raw else ""
        if accent is None:
            raise ValueError(
                f"Cor principal inválida no tema: {accent_raw!r} "
                "(use o formato #RRGGBB)."
            )
        raw = doc.get("overrides", {}) or {}
        if not isinstance(raw, dict):
            raise ValueError("Arquivo de tema corrompido (overrides).")
        self.theme_key = base if base in (*palettes.THEMES, AUTO) else "light"
        self.accent = accent
        # override com cor invalida e descartado (os demais valem)
        self.overrides = _clean_overrides(raw)
        self._save()
        self.apply()


def _clean_overrides(raw) -> dict:
    """So tokens conhecidos com cor hex valida (normalizada)."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        cor = palettes.normalize_hex(v)
        if k in palettes.COLOR_TOKENS and cor:
            out[k] = cor
    return out


_manager: ThemeManager | None = None


def manager() -> ThemeManager:
    global _manager
    if _manager is None:
        _manager = ThemeManager()
    return _manager


def apply_startup(app) -> None:
    """Entrypoint: restaura o tema salvo e aplica (substitui theme.apply)."""
    m = manager()
    try:
        colors, dark_ui = m.palette()
        theme.set_palette(colors, dark_ui)
        theme.apply(app, follow_system=m.theme_key == AUTO)
    except Exception:  # noqa: BLE001 — tema nunca pode impedir a abertura
        # rede de seguranca: qualquer paleta que ainda assim falhe (arquivo
        # editado a mao, versao futura) cai no PrintNest Original e REGRAVA o
        # padrao — o usuario abre o app em vez de ver um crash a cada clique
        # no atalho (13/10/2026)
        m.theme_key, m.accent, m.overrides = "light", "", {}
        m._save()
        colors, dark_ui = m.palette()
        theme.set_palette(colors, dark_ui)
        theme.apply(app)
    if m.theme_key == AUTO and not m._auto_hooked:
        app.styleHints().colorSchemeChanged.connect(lambda _: m.apply())
        m._auto_hooked = True
