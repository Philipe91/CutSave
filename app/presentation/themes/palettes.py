"""Paletas do Theme Engine — APENAS dados (sem Qt): testável e serializável.

Cada paleta define TODOS os tokens de cor do design system (mesmos nomes de
`app/presentation/theme.py`). O ThemeManager injeta a paleta escolhida nos
tokens e o QSS global é reconstruído — zero mudança de lógica no app.

Contraste: os pares texto/fundo seguem WCAG AA (ver test_themes).
"""

from __future__ import annotations

# tokens de COR que uma paleta precisa definir (espacamento/tipografia ficam
# fixos no theme.py — fase de escala/densidade vem depois)
COLOR_TOKENS = (
    "BG", "SURFACE", "SURFACE_ALT", "SURFACE_OVERLAY", "SIDEBAR", "TOOLBAR",
    "BORDER", "BORDER_STRONG", "HOVER", "SELECTED",
    "TEXT", "TEXT_SECONDARY", "TEXT_MUTED",
    "ACCENT", "ACCENT_HOVER", "ACCENT_PRESSED", "ACCENT_SOFT",
    "INFO", "INFO_SOFT", "SUCCESS", "SUCCESS_SOFT",
    "WARNING", "WARNING_SOFT", "ERROR", "ERROR_SOFT",
    "CUT", "MARK", "SHEET", "SHEET_BORDER", "CANVAS_BG", "EMPTY",
    "ICON", "ICON_ON_ACCENT",
)

# rotulos amigaveis dos tokens editaveis no "Personalizar Interface"
CUSTOM_LABELS = (
    ("ACCENT", "Cor principal (acento)"),
    ("BG", "Fundo da janela"),
    ("SURFACE", "Painéis / cards / campos"),
    ("SURFACE_ALT", "Barra superior / faixas"),
    ("SIDEBAR", "Barra lateral"),
    ("TOOLBAR", "Barra de ferramentas"),
    ("SELECTED", "Seleção"),
    ("HOVER", "Hover"),
    ("BORDER", "Linhas / separadores"),
    ("BORDER_STRONG", "Bordas de campos"),
    ("TEXT", "Textos"),
    ("TEXT_SECONDARY", "Textos secundários"),
    ("ICON", "Ícones"),
    ("CANVAS_BG", "Área de trabalho (mesa)"),
    ("SHEET", "Chapa (página)"),
    ("INFO", "Links / informação"),
)


# ---------- utilidades de cor (hex puro, sem Qt) ----------
def _rgb(hexcolor: str) -> tuple[int, int, int]:
    h = hexcolor.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(r: float, g: float, b: float) -> str:
    c = lambda v: max(0, min(255, round(v)))  # noqa: E731
    return f"#{c(r):02x}{c(g):02x}{c(b):02x}"


def mix(a: str, b: str, t: float) -> str:
    """Mistura a→b (t em 0..1)."""
    ar, ag, ab_ = _rgb(a)
    br, bg, bb = _rgb(b)
    return _hex(ar + (br - ar) * t, ag + (bg - ag) * t, ab_ + (bb - ab_) * t)


def luminance(hexcolor: str) -> float:
    """Luminância relativa (WCAG)."""
    def lin(v: float) -> float:
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(hexcolor)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    """Razão de contraste WCAG (1..21)."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def accent_set(base: str, dark_ui: bool) -> dict:
    """Deriva ACCENT_HOVER/PRESSED/SOFT + INFO a partir da cor escolhida."""
    return {
        "ACCENT": base,
        "ACCENT_HOVER": mix(base, "#ffffff" if dark_ui else "#000000", 0.16),
        "ACCENT_PRESSED": mix(base, "#ffffff" if dark_ui else "#000000", 0.30),
        "ACCENT_SOFT": mix(base, "#1e1e1e" if dark_ui else "#ffffff", 0.72),
        "SELECTED": mix(base, "#1e1e1e" if dark_ui else "#ffffff", 0.72),
        "INFO": base,
        "INFO_SOFT": mix(base, "#1e1e1e" if dark_ui else "#ffffff", 0.82),
    }


# ---------- paletas base ----------
# PrintNest Original (o claro de sempre — valores idênticos ao theme.py)
LIGHT = {
    "BG": "#f3f5f8", "SURFACE": "#ffffff", "SURFACE_ALT": "#f7f8fa",
    "SURFACE_OVERLAY": "rgba(255,255,255,235)",
    "SIDEBAR": "#f8f9fb", "TOOLBAR": "#f7f8fa",
    "BORDER": "#e4e8ee", "BORDER_STRONG": "#d7dde5",
    "HOVER": "#f0f4fa", "SELECTED": "#dcebff",
    "TEXT": "#111827", "TEXT_SECONDARY": "#6b7280", "TEXT_MUTED": "#9ca3af",
    "ACCENT": "#2563eb", "ACCENT_HOVER": "#1d4ed8",
    "ACCENT_PRESSED": "#1e40af", "ACCENT_SOFT": "#dcebff",
    "INFO": "#2563eb", "INFO_SOFT": "#e7f0ff",
    "SUCCESS": "#16a34a", "SUCCESS_SOFT": "#e6f6ec",
    "WARNING": "#f59e0b", "WARNING_SOFT": "#fdf3e2",
    "ERROR": "#dc2626", "ERROR_SOFT": "#fdeaea",
    "CUT": "#dc2626", "MARK": "#111827",
    "SHEET": "#ffffff", "SHEET_BORDER": "#d4dae2",
    "CANVAS_BG": "#eceff3", "EMPTY": "#e5e9ef",
    "ICON": "#6b7280", "ICON_ON_ACCENT": "#ffffff",
}

# Escuro premium (paleta do brief: VS2022/Illustrator/Figma)
DARK = {
    "BG": "#1e1e1e", "SURFACE": "#2d2d30", "SURFACE_ALT": "#2a2a2a",
    "SURFACE_OVERLAY": "rgba(45,45,48,235)",
    "SIDEBAR": "#252526", "TOOLBAR": "#2a2a2a",
    "BORDER": "#3c3c3c", "BORDER_STRONG": "#404040",
    "HOVER": "#333337", "SELECTED": "#14324f",
    "TEXT": "#ffffff", "TEXT_SECONDARY": "#c5c5c5", "TEXT_MUTED": "#8a8a8e",
    "ACCENT": "#0a84ff", "ACCENT_HOVER": "#3396ff",
    "ACCENT_PRESSED": "#5cabff", "ACCENT_SOFT": "#14324f",
    "INFO": "#0a84ff", "INFO_SOFT": "#112a42",
    "SUCCESS": "#00c853", "SUCCESS_SOFT": "#0f2e1c",
    "WARNING": "#ffb300", "WARNING_SOFT": "#332a10",
    "ERROR": "#ff5252", "ERROR_SOFT": "#391d1f",
    "CUT": "#ff5252", "MARK": "#e8e8e8",
    "SHEET": "#ffffff", "SHEET_BORDER": "#4a4a4f",
    "CANVAS_BG": "#191919", "EMPTY": "#3a3a3f",
    "ICON": "#c5c5c5", "ICON_ON_ACCENT": "#ffffff",
}

# Midnight (azul profundo, estilo Fusion/Resolve)
MIDNIGHT = {
    **DARK,
    "BG": "#10141f", "SURFACE": "#182031", "SURFACE_ALT": "#141b2a",
    "SURFACE_OVERLAY": "rgba(24,32,49,235)",
    "SIDEBAR": "#131a28", "TOOLBAR": "#141b2a",
    "BORDER": "#26304a", "BORDER_STRONG": "#2e3a58",
    "HOVER": "#1d2740", "SELECTED": "#1c3a63",
    "TEXT_MUTED": "#7d8798",
    "ACCENT": "#4c8dff", "ACCENT_HOVER": "#6ba1ff",
    "ACCENT_PRESSED": "#8ab5ff", "ACCENT_SOFT": "#1c3a63",
    "INFO": "#4c8dff", "INFO_SOFT": "#162a4a",
    "CANVAS_BG": "#0c1018", "EMPTY": "#242e46",
    "SHEET_BORDER": "#33405f",
    "TEXT_SECONDARY": "#b9c2d0", "ICON": "#b9c2d0",
}

# Carbon (grafite neutro, estilo Adobe)
CARBON = {
    **DARK,
    "BG": "#17181a", "SURFACE": "#222327", "SURFACE_ALT": "#1d1e21",
    "SURFACE_OVERLAY": "rgba(34,35,39,235)",
    "SIDEBAR": "#1b1c1f", "TOOLBAR": "#1d1e21",
    "BORDER": "#34363b", "BORDER_STRONG": "#3d4046",
    "HOVER": "#2a2c31", "SELECTED": "#2e3f57",
    "ACCENT": "#5c9ded", "ACCENT_HOVER": "#7cb0f1",
    "ACCENT_PRESSED": "#9cc3f5", "ACCENT_SOFT": "#243447",
    "INFO": "#5c9ded", "INFO_SOFT": "#1d2937",
    "CANVAS_BG": "#121315", "EMPTY": "#2e3036",
    "SHEET_BORDER": "#44474e",
}

THEMES = {
    "light": ("Claro", LIGHT, False),
    "dark": ("Escuro", DARK, True),
    "midnight": ("Midnight", MIDNIGHT, True),
    "carbon": ("Carbon", CARBON, True),
}

# acentos rapidos (o Personalizar aceita QUALQUER cor via seletor)
ACCENTS = (
    ("Azul", "#0a84ff"), ("Roxo", "#8b5cf6"), ("Verde", "#22c55e"),
    ("Laranja", "#f97316"), ("Vermelho", "#ef4444"),
    ("Turquesa", "#14b8a6"), ("Cinza", "#6b7280"),
)

# presets = (tema base, acento, ajustes extras)
PRESETS = (
    ("PrintNest Original", "light", "#2563eb", {}),
    ("Material Blue", "dark", "#2196f3", {}),
    ("Graphite", "carbon", "#9aa4b2", {}),
    ("Carbon", "carbon", "#5c9ded", {}),
    ("Ocean", "midnight", "#14b8a6", {}),
    ("Emerald", "dark", "#22c55e", {}),
    ("Purple Night", "midnight", "#8b5cf6", {}),
    ("Midnight", "midnight", "#4c8dff", {}),
    ("Adobe Dark", "carbon", "#5c9ded", {"BG": "#323232", "SURFACE": "#3a3a3a",
        "SURFACE_ALT": "#363636", "SIDEBAR": "#343434", "TOOLBAR": "#363636",
        "BORDER": "#4a4a4a", "BORDER_STRONG": "#525252", "HOVER": "#454545",
        "CANVAS_BG": "#2b2b2b", "EMPTY": "#4a4a4a"}),
    ("Visual Studio", "dark", "#0a84ff", {}),
)


def resolve(theme_key: str, accent: str | None = None,
            overrides: dict | None = None) -> tuple[dict, bool]:
    """Monta a paleta final: base + acento derivado + ajustes do usuário."""
    _, base, dark_ui = THEMES.get(theme_key, THEMES["light"])
    palette = dict(base)
    if accent:
        palette.update(accent_set(accent, dark_ui))
    if overrides:
        palette.update({k: v for k, v in overrides.items() if k in COLOR_TOKENS})
    return palette, dark_ui
