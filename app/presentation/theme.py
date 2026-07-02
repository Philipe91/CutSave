"""PRINTNEST DESIGN SYSTEM — tokens (cores, espacamento, raio, tipografia) e a
folha de estilo global (QSS) da aplicacao.

Fonte unica de verdade do visual. Toda a interface deriva daqui; nunca use hex
literais espalhados pelos widgets. A linguagem e clara, sobria e industrial, no
nivel de softwares graficos profissionais (Affinity, Figma, Illustrator): muito
espaco em branco, hierarquia forte, componentes consistentes e microinteracoes
discretas.

IMPORTANTE: os NOMES dos tokens sao contrato com o resto do codigo — mude os
valores livremente, mas nao renomeie/remova constantes ja usadas.
"""

from __future__ import annotations

from app.shared.resources import resource_path

# Caminho (com barras normais, exigidas pelo QSS) do check branco do checkbox.
# Resolvido em runtime — funciona no dev e no executavel (PyInstaller/_MEIPASS).
_CHECK_ICON = resource_path("assets/icons/check-white.svg").as_posix()

# ============================================================================
#  ESPACAMENTO — grade de 4/8px (nunca valores aleatorios)
# ============================================================================
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_2XL = 32
SPACE_3XL = 40
SPACE_4XL = 48

# ============================================================================
#  RAIO DE BORDA
# ============================================================================
RADIUS = 8          # botoes, inputs, dropdowns
RADIUS_CARD = 10    # cards / paineis
RADIUS_SM = 6       # elementos menores / canvas
RADIUS_PILL = 999   # badges / pills

# ============================================================================
#  PALETA
# ============================================================================
# --- superficies / neutros ---
BG = "#f3f5f8"          # fundo principal da janela
SURFACE = "#ffffff"     # cards, inputs, paineis
SURFACE_ALT = "#f7f8fa"  # toolbar, header, faixas sutis
SIDEBAR = "#f8f9fb"     # barra lateral esquerda
TOOLBAR = "#f7f8fa"     # barra de ferramentas / cabecalho
BORDER = "#e4e8ee"      # bordas suaves (padrao)
BORDER_STRONG = "#d7dde5"  # bordas de input (um pouco mais visiveis)

# --- estados ---
HOVER = "#f0f4fa"       # hover neutro
SELECTED = "#dcebff"    # item selecionado

# --- texto ---
TEXT = "#111827"        # primario
TEXT_SECONDARY = "#6b7280"  # secundario
TEXT_MUTED = "#9ca3af"  # auxiliar / placeholder

# --- marca / acento ---
ACCENT = "#2563eb"      # primaria (CTA, foco, selecao)
ACCENT_HOVER = "#1d4ed8"
ACCENT_PRESSED = "#1e40af"
ACCENT_SOFT = "#dcebff"  # fundo suave do acento (selecao/hover-acento)

# --- semantica (status / alertas) ---
INFO = "#2563eb"
INFO_SOFT = "#e7f0ff"
SUCCESS = "#16a34a"
SUCCESS_SOFT = "#e6f6ec"
WARNING = "#f59e0b"
WARNING_SOFT = "#fdf3e2"
ERROR = "#dc2626"
ERROR_SOFT = "#fdeaea"

# --- canvas / producao ---
CUT = "#dc2626"          # faca (corte) em vermelho
MARK = "#111827"         # marcas de registro
SHEET = "#ffffff"        # chapa (pagina)
SHEET_BORDER = "#d4dae2"  # borda da chapa (suave, sobre mesa clara)
CANVAS_BG = "#eceff3"    # mesa (fundo externo do canvas) — claro, estilo Affinity
EMPTY = "#e5e9ef"        # peca sem raster

# --- icones ---
ICON = TEXT_SECONDARY
ICON_ON_ACCENT = "#ffffff"

# ============================================================================
#  TIPOGRAFIA — escala fixa, nunca abaixo de 12px
# ============================================================================
FONT_FAMILY = "Segoe UI Variable, Segoe UI, Inter, system-ui, sans-serif"
FONT_CAPTION = 12   # descricoes / auxiliares
FONT_SM = 12        # legendas / labels compactos (piso: 12)
FONT_MD = 13        # texto padrao
FONT_LG = 15        # titulo de secao
FONT_XL = 18        # titulo de painel
FONT_2XL = 22       # titulo de janela


def build_app_qss() -> str:
    """Folha de estilo global (aplicada no QApplication).

    Define o visual base de campos, botoes, combos, checkboxes, abas, menus,
    toolbar, scrollbars, status bar e dos componentes proprios (Card, Ribbon)
    via objectName/propriedade dinamica.
    """
    return f"""
    /* ===================== base ===================== */
    QWidget {{
        color: {TEXT};
        font-family: {FONT_FAMILY};
        font-size: {FONT_MD}px;
    }}
    QMainWindow, QDialog {{ background: {BG}; }}
    QToolTip {{
        background: {TEXT};
        color: #ffffff;
        border: none;
        border-radius: {RADIUS_SM}px;
        padding: 6px 9px;
        font-size: {FONT_SM}px;
    }}

    /* ===================== campos e combos ===================== */
    QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER_STRONG};
        border-radius: {RADIUS}px;
        padding: 6px 10px;
        min-height: 22px;
        selection-background-color: {ACCENT};
        selection-color: {ICON_ON_ACCENT};
    }}
    QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QLineEdit:hover {{
        border-color: {TEXT_MUTED};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {{
        border: 2px solid {ACCENT};
        padding: 5px 9px;   /* compensa a borda +1px para nao "pular" */
    }}
    QSpinBox:disabled, QDoubleSpinBox:disabled,
    QComboBox:disabled, QLineEdit:disabled {{
        background: {SURFACE_ALT}; color: {TEXT_MUTED};
    }}
    QComboBox::drop-down {{
        border: none; width: 22px;
        subcontrol-origin: padding; subcontrol-position: center right;
    }}
    QComboBox QAbstractItemView {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {RADIUS}px;
        padding: 4px;
        outline: none;
        selection-background-color: {ACCENT_SOFT};
        selection-color: {TEXT};
    }}
    QComboBox QAbstractItemView::item {{
        min-height: 28px; padding: 4px 8px; border-radius: {RADIUS_SM}px;
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        width: 18px; border: none; background: transparent;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background: {HOVER};
    }}

    /* ===================== botoes ===================== */
    QPushButton {{
        background: {SURFACE};
        border: 1px solid {BORDER_STRONG};
        border-radius: {RADIUS}px;
        padding: 7px 16px;
        min-height: 22px;
        color: {TEXT};
        font-weight: 500;
    }}
    QPushButton:hover {{ background: {HOVER}; border-color: {TEXT_MUTED}; }}
    QPushButton:pressed {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; }}
    QPushButton:disabled {{ color: {TEXT_MUTED}; background: {SURFACE_ALT}; }}
    /* CTA primario (azul) */
    QPushButton[accent="true"] {{
        background: {ACCENT}; border: 1px solid {ACCENT};
        color: #ffffff; font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{
        background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER};
    }}
    QPushButton[accent="true"]:pressed {{ background: {ACCENT_PRESSED}; }}
    /* acao destrutiva (vermelho, so no hover para nao gritar) */
    QPushButton[danger="true"]:hover {{
        background: {ERROR_SOFT}; border-color: {ERROR}; color: {ERROR};
    }}

    /* ===================== checkbox / radio ===================== */
    QCheckBox, QRadioButton {{ spacing: 8px; color: {TEXT}; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 18px; height: 18px;
        border: 1px solid {BORDER_STRONG};
        background: {SURFACE};
    }}
    QCheckBox::indicator {{ border-radius: 5px; }}
    QRadioButton::indicator {{ border-radius: 9px; }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border-color: {ACCENT};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT}; border-color: {ACCENT};
        image: url("{_CHECK_ICON}");
    }}
    QRadioButton::indicator:checked {{
        background: {ACCENT}; border: 5px solid {ACCENT};
    }}

    /* ===================== scrollarea ===================== */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 12px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_STRONG}; border-radius: 5px; min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
    QScrollBar:horizontal {{
        background: transparent; height: 12px; margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER_STRONG}; border-radius: 5px; min-width: 32px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {TEXT_MUTED}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* ===================== tabela / biblioteca ===================== */
    QTableWidget {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {RADIUS}px;
        gridline-color: transparent;
        outline: none;
    }}
    QTableWidget::item {{ padding: 6px; border-radius: {RADIUS_SM}px; }}
    QTableWidget::item:hover {{ background: {HOVER}; }}
    QTableWidget::item:selected {{ background: {SELECTED}; color: {TEXT}; }}
    QHeaderView::section {{
        background: {SURFACE_ALT};
        border: none; border-bottom: 1px solid {BORDER};
        padding: 8px; color: {TEXT_SECONDARY}; font-weight: 600;
    }}

    /* ===================== abas do inspector (Figma-style) ===================== */
    QTabWidget::pane {{ border: none; background: transparent; }}
    QTabBar {{ qproperty-drawBase: 0; }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_SECONDARY};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 14px;
        margin-right: 2px;
        font-weight: 500;
    }}
    QTabBar::tab:hover {{ color: {TEXT}; background: {HOVER}; border-radius: {RADIUS_SM}px; }}
    QTabBar::tab:selected {{
        color: {ACCENT}; border-bottom: 2px solid {ACCENT};
        font-weight: 600;
    }}

    /* ===================== status bar ===================== */
    QStatusBar {{
        background: {SURFACE}; border-top: 1px solid {BORDER};
        color: {TEXT_SECONDARY};
    }}
    QStatusBar::item {{ border: none; }}
    QLabel#statusBadge {{
        background: {SURFACE_ALT};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_SM}px;
        padding: 2px 8px;
        color: {TEXT_SECONDARY};
        font-size: {FONT_SM}px;
    }}

    /* ===================== menus ===================== */
    QMenuBar {{ background: {TOOLBAR}; border-bottom: 1px solid {BORDER}; padding: 2px; }}
    QMenuBar::item {{ padding: 6px 12px; border-radius: {RADIUS_SM}px; }}
    QMenuBar::item:selected {{ background: {HOVER}; }}
    QMenu {{
        background: {SURFACE}; border: 1px solid {BORDER};
        border-radius: {RADIUS}px; padding: 6px;
    }}
    QMenu::item {{ padding: 8px 24px 8px 12px; border-radius: {RADIUS_SM}px; }}
    QMenu::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}
    QMenu::separator {{ height: 1px; background: {BORDER}; margin: 6px 8px; }}
    QMenu::icon {{ padding-left: 8px; }}

    /* ===================== Card (inspector / acordeao) ===================== */
    QFrame#card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_CARD}px;
    }}
    /* faixa colorida por secao (borda esquerda, discreta) */
    QFrame#card[accent="producao"]  {{ border-left: 3px solid {ACCENT}; }}
    QFrame#card[accent="acabamento"] {{ border-left: 3px solid {WARNING}; }}
    QFrame#card[accent="imagens"]   {{ border-left: 3px solid {SUCCESS}; }}
    QFrame#card[accent="registro"]  {{ border-left: 3px solid #8b5cf6; }}
    QFrame#card[accent="avancado"]  {{ border-left: 3px solid {TEXT_MUTED}; }}
    QFrame#card[accent="resumo"] {{
        border-left: 3px solid {ACCENT}; background: {SURFACE_ALT};
    }}
    QPushButton#cardHeader {{
        background: transparent; border: none; text-align: left;
        padding: 12px 14px; color: {TEXT};
        font-size: {FONT_LG}px; font-weight: 600;
    }}
    QPushButton#cardHeader:hover {{ background: {HOVER}; }}

    /* ===================== Ribbon / toolbar ===================== */
    QFrame#ribbon {{ background: {TOOLBAR}; border-bottom: 1px solid {BORDER}; }}
    QLabel#ribbonGroupTitle {{
        color: {TEXT_MUTED}; font-size: {FONT_SM}px;
        text-transform: uppercase; letter-spacing: 1px;
    }}
    QFrame#ribbonSep {{ background: {BORDER}; max-width: 1px; min-width: 1px; }}
    QToolButton {{
        background: transparent; border: 1px solid transparent;
        border-radius: {RADIUS}px; padding: 6px 10px; color: {TEXT};
    }}
    QToolButton:hover {{ background: {HOVER}; border-color: {BORDER}; }}
    QToolButton:pressed {{ background: {ACCENT_SOFT}; }}
    QToolButton:checked {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; color: {ACCENT}; }}
    QToolButton[accent="true"] {{
        background: {ACCENT}; color: #ffffff; border-color: {ACCENT}; font-weight: 600;
    }}
    QToolButton[accent="true"]:hover {{ background: {ACCENT_HOVER}; }}

    /* ===================== rotulos utilitarios ===================== */
    QLabel[role="caption"] {{ color: {TEXT_SECONDARY}; font-size: {FONT_SM}px; }}
    QLabel[role="hint"] {{ color: {TEXT_MUTED}; font-size: {FONT_CAPTION}px; }}
    QLabel[role="sectionTitle"] {{ color: {TEXT}; font-size: {FONT_LG}px; font-weight: 600; }}
    QLabel[role="panelTitle"] {{ color: {TEXT}; font-size: {FONT_XL}px; font-weight: 600; }}
    QLabel[role="metricValue"] {{ color: {TEXT}; font-weight: 700; }}
    QLabel[role="metricLabel"] {{ color: {TEXT_MUTED}; font-size: {FONT_SM}px; }}
    """
