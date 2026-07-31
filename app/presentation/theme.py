"""PRINTNEST DESIGN SYSTEM — tokens (cores, espaçamento, raio, tipografia) e a
folha de estilo global (QSS) da aplicacao.

Fonte única de verdade do visual. Toda a interface deriva daqui; nunca use hex
literais espalhados pelos widgets. A linguagem e clara, sobria e industrial, no
nivel de softwares gráficos profissionais (Affinity, Figma, Illustrator): muito
espaco em branco, hierarquia forte, componentes consistentes e microinteracoes
discretas.

IMPORTANTE: os NOMES dos tokens são contrato com o resto do codigo — mude os
valores livremente, mas não renomeie/remova constantes já usadas.
"""

from __future__ import annotations

from app.shared.resources import resource_path

# Caminhos (com barras normais, exigidas pelo QSS) dos icones embutidos no
# estilo: check do checkbox e setas de spinbox/combo. Resolvidos em runtime —
# funcionam no dev e no executavel (PyInstaller/_MEIPASS). Quando o QSS
# estiliza os sub-botões, o Qt descarta as setas nativas: sem estas imagens,
# os botões ficam clicaveis porem invisiveis.
_CHECK_ICON = resource_path("assets/icons/check-white.svg").as_posix()
_RADIO_ON = resource_path("assets/icons/radio-on.svg").as_posix()
_ARROW_UP = resource_path("assets/icons/spin-up.svg").as_posix()
_ARROW_DOWN = resource_path("assets/icons/spin-down.svg").as_posix()

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
RADIUS = 8          # botões, inputs, dropdowns
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
BORDER = "#e4e8ee"      # bordas suaves (padrão)
BORDER_STRONG = "#d7dde5"  # bordas de input (um pouco mais visiveis)

# --- estados ---
HOVER = "#f0f4fa"       # hover neutro
SELECTED = "#dcebff"    # item selecionado

# --- texto ---
TEXT = "#111827"        # primario
TEXT_SECONDARY = "#6b7280"  # secundario
TEXT_MUTED = "#9ca3af"  # auxiliar / placeholder

# --- marca / acento ---
ACCENT = "#2563eb"      # primaria (CTA, foco, seleção)
ACCENT_HOVER = "#1d4ed8"
ACCENT_PRESSED = "#1e40af"
ACCENT_SOFT = "#dcebff"  # fundo suave do acento (seleção/hover-acento)

# --- semantica (status / alertas) ---
INFO = "#2563eb"
INFO_SOFT = "#e7f0ff"
SUCCESS = "#16a34a"
SUCCESS_SOFT = "#e6f6ec"
WARNING = "#f59e0b"
WARNING_SOFT = "#fdf3e2"
ERROR = "#dc2626"
ERROR_SOFT = "#fdeaea"

# --- canvas / produção ---
CUT = "#dc2626"          # faca (corte) em vermelho
MARK = "#111827"         # marcas de registro
SHEET = "#ffffff"        # chapa (página)
SHEET_BORDER = "#d4dae2"  # borda da chapa (suave, sobre mesa clara)
CANVAS_BG = "#eceff3"    # mesa (fundo externo do canvas) — claro, estilo Affinity
EMPTY = "#e5e9ef"        # peça sem raster

# --- icones ---
ICON = TEXT_SECONDARY
ICON_ON_ACCENT = "#ffffff"

# --- overlays translucidos (barrinha flutuante, medidor) ---
SURFACE_OVERLAY = "rgba(255,255,255,235)"

# ============================================================================
#  TIPOGRAFIA — escala fixa, nunca abaixo de 12px
# ============================================================================
FONT_FAMILY = "Segoe UI Variable, Segoe UI, Inter, system-ui, sans-serif"
FONT_CAPTION = 12   # descricoes / auxiliares
FONT_SM = 12        # legendas / labels compactos (piso: 12)
FONT_MD = 13        # texto padrão
FONT_LG = 15        # título de secao
FONT_XL = 18        # título de painel
FONT_2XL = 22       # título de janela


# ============================================================================
#  THEME ENGINE — os tokens de COR acima são o estado ATUAL; o ThemeManager
#  (app/presentation/themes) troca a paleta inteira em runtime. Os NOMES
#  continuam contrato: todo o app segue lendo theme.ACCENT etc.
# ============================================================================
_DARK_UI = False  # esquema atual (informativo p/ Qt nativo: menus, tooltips)


def set_palette(colors: dict, dark_ui: bool = False) -> None:
    """Injeta uma paleta nos tokens de cor (mesmos nomes). Camada 100% visual:
    nenhuma lógica muda — quem lê theme.X passa a ver a cor nova."""
    from app.presentation.themes.palettes import COLOR_TOKENS

    g = globals()
    for key in COLOR_TOKENS:
        if key in colors:
            g[key] = colors[key]
    g["_DARK_UI"] = bool(dark_ui)


def current_palette() -> dict:
    from app.presentation.themes.palettes import COLOR_TOKENS

    return {key: globals()[key] for key in COLOR_TOKENS}


def is_dark() -> bool:
    return _DARK_UI


def build_qpalette():
    """QPalette derivada dos tokens ATUAIS: cobre o que o QSS não alcança
    (viewport de tabelas/listas, textos nativos de checkbox, tooltips...).
    Sem ela, esses miolos ficavam BRANCOS no tema escuro (bug do beta)."""
    from PySide6.QtGui import QColor, QPalette

    pal = QPalette()
    pares = (
        (QPalette.Window, BG), (QPalette.WindowText, TEXT),
        (QPalette.Base, SURFACE), (QPalette.AlternateBase, SURFACE_ALT),
        (QPalette.Text, TEXT), (QPalette.PlaceholderText, TEXT_MUTED),
        (QPalette.Button, SURFACE_ALT), (QPalette.ButtonText, TEXT),
        (QPalette.Highlight, ACCENT), (QPalette.HighlightedText, ICON_ON_ACCENT),
        (QPalette.ToolTipBase, SURFACE), (QPalette.ToolTipText, TEXT),
        (QPalette.Link, INFO),
    )
    for role, hexcolor in pares:
        pal.setColor(role, QColor(hexcolor))
    # grupo DISABLED explícito: setColor(role, cor) pinta Active/Inactive/
    # Disabled iguais — sem isto, menu/botão desabilitado parecia clicável
    # (varredura 09/07, regressão no tema claro)
    apagado = QColor(TEXT_MUTED)
    for role in (QPalette.WindowText, QPalette.ButtonText, QPalette.Text):
        pal.setColor(QPalette.Disabled, role, apagado)
    return pal


def apply(app) -> None:
    """Aplica o design system inteiro a um QApplication (esquema + paleta
    nativa + QSS).

    USAR EM TODO entrypoint com GUI (app principal, License Studio, futuros
    utilitários) — QA 2.0: o License Studio nascia "pelado" porque só o
    __main__ injetava o QSS. Respeita a paleta ATUAL (Theme Engine)."""
    from PySide6.QtCore import Qt

    app.styleHints().setColorScheme(
        Qt.ColorScheme.Dark if _DARK_UI else Qt.ColorScheme.Light
    )
    app.setPalette(build_qpalette())
    app.setStyleSheet(build_app_qss())


def build_app_qss() -> str:
    """Folha de estilo global (aplicada no QApplication).

    Define o visual base de campos, botões, combos, checkboxes, abas, menus,
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
        color: {BG};
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
        padding: 5px 9px;   /* compensa a borda +1px para não "pular" */
    }}
    QSpinBox:disabled, QDoubleSpinBox:disabled,
    QComboBox:disabled, QLineEdit:disabled {{
        background: {SURFACE_ALT}; color: {TEXT_MUTED};
    }}
    QComboBox::drop-down {{
        border: none; width: 22px;
        subcontrol-origin: padding; subcontrol-position: center right;
    }}
    QComboBox::down-arrow {{
        image: url("{_ARROW_DOWN}"); width: 11px; height: 11px;
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
        border-radius: 4px;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background: {HOVER};
    }}
    /* setas dos botões (obrigatorias: estilizar o botão descarta as nativas) */
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: url("{_ARROW_UP}"); width: 10px; height: 10px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: url("{_ARROW_DOWN}"); width: 10px; height: 10px;
    }}
    QSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off,
    QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:off,
    QSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off,
    QDoubleSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:off {{
        width: 10px; height: 10px;
    }}

    /* ===================== botões ===================== */
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
        color: {ICON_ON_ACCENT}; font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{
        background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER};
    }}
    QPushButton[accent="true"]:pressed {{ background: {ACCENT_PRESSED}; }}
    /* ação destrutiva (vermelho, só no hover para não gritar) */
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
    /* radio marcado como IMAGEM (circulo azul + ponto branco): borda espessa
       com border-radius sai "quadrada" em algumas versoes do Qt. */
    QRadioButton::indicator:checked {{
        border: none; background: transparent;
        image: url("{_RADIO_ON}");
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

    /* trilho de icones do inspector (IconRailTabs): substitui as abas de
       texto, que eram cortadas quando o painel ficava estreito */
    QWidget#railBar {{
        background: {SURFACE_ALT};
        border-left: 1px solid {BORDER};
    }}
    QToolButton#railBtn {{
        border: none; border-radius: {RADIUS_SM}px;
        background: transparent; padding: 0;
    }}
    QToolButton#railBtn:hover {{ background: {HOVER}; }}
    QToolButton#railBtn:checked {{ background: {ACCENT_SOFT}; }}
    /* botao de recolher painel: precisa PARECER botao. Sem borda ele passava
       batido e o unico jeito de recolher era um clique que ninguem descobre */
    /* padding: 0 e obrigatorio. A regra geral de QToolButton usa 6px 10px, e
       num botao pequeno isso nao deixa espaco para o icone — ele encolhe para
       um ponto (visto em 29/07 na alca redonda). */
    QToolButton#collapseBtn {{
        border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px;
        background: {SURFACE}; padding: 0;
    }}
    QToolButton#collapseBtn:hover {{ background: {HOVER}; border-color: {ACCENT}; }}
    /* alca REDONDA de recolher, no divisor. A capsula alta de antes parecia
       barra de rolagem (relato de 29/07); circulo nao tem como ser confundido.
       12px de raio em 24px de lado = circulo. Comentario em ASCII de
       proposito: caractere fora de ASCII no QSS derruba a regra seguinte. */
    QToolButton#handleBtn {{
        border: 1px solid {BORDER_STRONG}; border-radius: 12px;
        background: {SURFACE}; padding: 0;
    }}
    QToolButton#handleBtn:hover {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; }}
    QLabel#railTitle {{
        background: {SURFACE_ALT};
        border-bottom: 1px solid {BORDER};
        color: {TEXT};
        font-size: {FONT_LG}px; font-weight: 600;
        padding: {SPACE_SM}px {SPACE_MD}px;
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
    /* cabecalho AZUL solido (cor do CTA "Gerar Faca") em TODOS os cards,
       compacto para ocupar menos altura. */
    QFrame#card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_CARD}px;
    }}
    QFrame#card[accent="resumo"] {{ background: {SURFACE_ALT}; }}
    QPushButton#cardHeader {{
        background: {ACCENT}; border: none; text-align: left;
        padding: 6px 12px; color: {ICON_ON_ACCENT};
        font-size: {FONT_MD}px; font-weight: 600;
        border-top-left-radius: {RADIUS_CARD}px;
        border-top-right-radius: {RADIUS_CARD}px;
    }}
    QPushButton#cardHeader:hover {{ background: {ACCENT_HOVER}; }}

    /* ===================== Ribbon / toolbar ===================== */
    /* a ribbon e um QToolBar (objectName "ribbon") — seletor correto */
    QToolBar#ribbon {{
        background: {TOOLBAR}; border: none; border-bottom: 1px solid {BORDER};
        padding: 4px 8px; spacing: 2px;
    }}
    QToolBar#ribbon::separator {{
        background: {BORDER}; width: 1px; margin: 6px 8px;
    }}
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
        background: {ACCENT}; color: {ICON_ON_ACCENT}; border-color: {ACCENT}; font-weight: 600;
    }}
    QToolButton[accent="true"]:hover {{ background: {ACCENT_HOVER}; }}

    /* Modo Corte (laser/CNC): destacado como o CTA "Gerar Faca", porem em azul
       ESCURO, para o operador nao confundir dois botoes que fazem coisas
       diferentes. O tom sai da mesma paleta, entao acompanha a troca de tema. */
    QToolButton[accent="corte"] {{
        background: {ACCENT_PRESSED}; color: {ICON_ON_ACCENT};
        border-color: {ACCENT_PRESSED}; font-weight: 600;
    }}
    QToolButton[accent="corte"]:hover {{
        background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER};
    }}
    QToolButton[accent="corte"]:pressed {{
        background: {ACCENT_PRESSED}; border-color: {ACCENT_PRESSED};
    }}
    QToolButton[accent="corte"]:checked {{
        background: {ACCENT_PRESSED}; color: {ICON_ON_ACCENT};
        border-color: {ACCENT_PRESSED};
    }}
    QToolButton[accent="corte"]:disabled {{ background: {BORDER}; border-color: {BORDER}; }}

    /* ===================== rotulos utilitarios ===================== */
    QLabel[role="caption"] {{ color: {TEXT_SECONDARY}; font-size: {FONT_SM}px; }}
    QLabel[role="hint"] {{ color: {TEXT_MUTED}; font-size: {FONT_CAPTION}px; }}
    QLabel[role="sectionTitle"] {{ color: {TEXT}; font-size: {FONT_LG}px; font-weight: 600; }}
    QLabel[role="panelTitle"] {{ color: {TEXT}; font-size: {FONT_XL}px; font-weight: 600; }}
    QLabel[role="metricValue"] {{ color: {TEXT}; font-weight: 700; font-size: {FONT_LG}px; }}
    QLabel[role="metricLabel"] {{ color: {TEXT_MUTED}; font-size: {FONT_SM}px; }}
    QLabel[role="accentTag"] {{ color: {ACCENT}; font-weight: 700; }}
    QLabel[role="dot"] {{ color: {TEXT_MUTED}; }}
    QLabel[role="cardTitle"] {{ color: {TEXT}; font-size: {FONT_MD}px; font-weight: 600; }}

    /* ============ superfícies nomeadas (Theme Engine: troca ao vivo) ====== */
    #propBar {{
        background: {SURFACE_ALT}; border: 1px solid {BORDER};
        border-radius: {RADIUS}px;
    }}
    #floatBar, #measureOverlay {{
        background: {SURFACE_OVERLAY}; border: 1px solid {BORDER};
        border-radius: {RADIUS_SM}px;
    }}
    QToolButton#tabPlus {{
        color: {ACCENT}; border: none; background: transparent;
        font-size: 26px; font-weight: 400; padding: 0 0 5px 0; margin-left: -8px;
    }}
    QToolButton#tabPlus:hover {{ color: {ACCENT_HOVER}; }}
    """
