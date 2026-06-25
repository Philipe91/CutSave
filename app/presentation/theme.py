"""Sistema de design do PrintNest: tokens (cores, espacamento, raio, tipografia)
e a folha de estilo global (QSS).

Centraliza tudo o que antes era hex espalhado pela interface. A paleta e clara,
sobria e consistente, no espirito de softwares graficos profissionais (Affinity,
Figma, LightBurn). Use as constantes deste modulo em vez de cores literais.
"""

from __future__ import annotations

# ---- espacamento (grid de 4/8px) ----
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

RADIUS = 8
RADIUS_SM = 6

# ---- paleta ----
# Superficies e neutros
BG = "#eef0f3"          # fundo da janela
SURFACE = "#ffffff"     # cartoes, paineis
SURFACE_ALT = "#f6f7f9"  # faixas sutis / hover leve
BORDER = "#e3e6ea"      # bordas suaves
BORDER_STRONG = "#cfd4db"

# Texto
TEXT = "#1f2733"        # primario
TEXT_SECONDARY = "#5b6675"
TEXT_MUTED = "#9097a3"

# Marca / acento
ACCENT = "#2f6fed"
ACCENT_HOVER = "#2257c4"
ACCENT_SOFT = "#e7f0ff"

# Semantica (alertas / status)
INFO = "#2f6fed"
INFO_SOFT = "#e7f0ff"
SUCCESS = "#1f9d57"
SUCCESS_SOFT = "#e4f6ec"
WARNING = "#c77700"
WARNING_SOFT = "#fdf1dd"
ERROR = "#d33a2c"
ERROR_SOFT = "#fbe7e4"

# Canvas / producao
CUT = "#dc2626"         # faca (corte) em vermelho
MARK = "#0a5ab4"        # marcas de registro
SHEET = "#ffffff"       # chapa (pagina)
SHEET_BORDER = "#283039"
CANVAS_BG = "#aab0b8"   # mesa cinza
EMPTY = "#c8cdd3"       # peca sem raster

# Cor do tema para os icones (Lucide recolorido)
ICON = TEXT_SECONDARY
ICON_ON_ACCENT = "#ffffff"

# ---- tipografia ----
FONT_FAMILY = "Segoe UI, Inter, system-ui, sans-serif"
FONT_SM = 11
FONT_MD = 12
FONT_LG = 14


def build_app_qss() -> str:
    """Folha de estilo global da aplicacao (aplicada no QApplication).

    Define o visual base de botoes, campos, combos, abas, toolbar, status bar e
    dos componentes proprios (Card, Alert, Ribbon) via objectName.
    """
    return f"""
    QWidget {{
        color: {TEXT};
        font-family: {FONT_FAMILY};
        font-size: {FONT_MD}px;
    }}
    QMainWindow, QDialog {{ background: {BG}; }}

    /* ---- campos numericos e combos ---- */
    QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER_STRONG};
        border-radius: {RADIUS_SM}px;
        padding: 4px 8px;
        min-height: 20px;
        selection-background-color: {ACCENT};
        selection-color: {ICON_ON_ACCENT};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {{
        border-color: {ACCENT};
    }}
    QComboBox::drop-down {{ border: none; width: 18px; }}

    /* ---- botoes padrao ---- */
    QPushButton {{
        background: {SURFACE};
        border: 1px solid {BORDER_STRONG};
        border-radius: {RADIUS_SM}px;
        padding: 6px 12px;
        color: {TEXT};
    }}
    QPushButton:hover {{ background: {SURFACE_ALT}; border-color: {ACCENT}; }}
    QPushButton:pressed {{ background: {ACCENT_SOFT}; }}
    QPushButton:disabled {{ color: {TEXT_MUTED}; background: {SURFACE_ALT}; }}
    QPushButton[accent="true"] {{
        background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{ background: {ACCENT_HOVER}; }}

    /* ---- checkbox ---- */
    QCheckBox {{ spacing: 8px; }}

    /* ---- scrollarea / paineis ---- */
    QScrollArea {{ border: none; background: transparent; }}

    /* ---- tabela / biblioteca ---- */
    QTableWidget {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM}px;
        gridline-color: transparent;
    }}
    QTableWidget::item {{ padding: 4px; }}
    QTableWidget::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}
    QHeaderView::section {{
        background: {SURFACE_ALT};
        border: none; border-bottom: 1px solid {BORDER};
        padding: 6px; color: {TEXT_SECONDARY}; font-weight: 600;
    }}

    /* ---- status bar ---- */
    QStatusBar {{
        background: {SURFACE}; border-top: 1px solid {BORDER};
        color: {TEXT_SECONDARY};
    }}
    QStatusBar::item {{ border: none; }}

    /* ---- menu ---- */
    QMenuBar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
    QMenuBar::item:selected {{ background: {ACCENT_SOFT}; }}
    QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; }}
    QMenu::item:selected {{ background: {ACCENT_SOFT}; }}

    /* ---- Card (acordeao moderno) ---- */
    QFrame#card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {RADIUS}px;
    }}
    /* faixa colorida por secao (borda esquerda) */
    QFrame#card[accent="producao"]  {{ border-left: 3px solid {ACCENT}; }}
    QFrame#card[accent="acabamento"] {{ border-left: 3px solid {WARNING}; }}
    QFrame#card[accent="imagens"]   {{ border-left: 3px solid {SUCCESS}; }}
    QFrame#card[accent="registro"]  {{ border-left: 3px solid #8e44ad; }}
    QFrame#card[accent="avancado"]  {{ border-left: 3px solid {TEXT_MUTED}; }}
    QFrame#card[accent="resumo"] {{
        border-left: 3px solid {ACCENT}; background: {SURFACE_ALT};
    }}
    QPushButton#cardHeader {{
        background: transparent; border: none; text-align: left;
        padding: 10px 12px; color: {TEXT}; font-weight: 600;
    }}
    QPushButton#cardHeader:hover {{ background: {SURFACE_ALT}; }}

    /* ---- Ribbon ---- */
    QFrame#ribbon {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
    QLabel#ribbonGroupTitle {{ color: {TEXT_MUTED}; font-size: {FONT_SM}px; }}
    QToolButton {{
        background: transparent; border: 1px solid transparent;
        border-radius: {RADIUS_SM}px; padding: 5px 8px; color: {TEXT};
    }}
    QToolButton:hover {{ background: {SURFACE_ALT}; border-color: {BORDER}; }}
    QToolButton:pressed {{ background: {ACCENT_SOFT}; }}
    QToolButton[accent="true"] {{ background: {ACCENT}; color: white; }}
    QToolButton[accent="true"]:hover {{ background: {ACCENT_HOVER}; }}

    /* ---- rotulos de secao/metrica ---- */
    QLabel[role="caption"] {{ color: {TEXT_SECONDARY}; font-size: {FONT_SM}px; }}
    QLabel[role="metricValue"] {{ color: {TEXT}; font-weight: 600; }}
    """
