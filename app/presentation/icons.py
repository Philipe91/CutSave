"""Carregador de icones: renderiza os SVGs do Lucide (assets/icons) como QIcon,
recolorindo o traco ('currentColor') para a cor pedida.

Uso:
    from app.presentation import icons
    botao.setIcon(icons.icon("save"))
    botao.setIcon(icons.icon("zap", color=theme.ACCENT))

Os icones são cacheados por (nome, cor, tamanho). Se um SVG nao existir, retorna
um QIcon vazio (a UI segue funcionando, so sem o icone).
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.presentation import theme
from app.shared.resources import resource_path

_ICON_DIR = resource_path("assets/icons")


def device_ratio() -> float:
    """Fator de pixels do monitor: 1.0 a 100%, 1.25 a 125%, 1.5 a 150%.

    Sem QGuiApplication (teste puro, sem interface) devolve 1.0 — e 1.0 faz
    toda a receita de alta resolucao virar no-op, entao o desenho a 100%
    continua identico ao de antes."""
    app = QGuiApplication.instance()
    if app is None:
        return 1.0
    tela = app.primaryScreen()
    return float(tela.devicePixelRatio()) if tela is not None else 1.0


def blank(w: int, h: int, dpr: float) -> QPixmap:
    """Pixmap transparente de w x h LOGICOS, com resolucao real w*dpr x h*dpr.

    Quem desenha NAO muda nada: o QPainter aberto sobre este pixmap ja aplica
    o fator sozinho, entao as coordenadas continuam sendo as logicas de
    sempre. (Escalar de novo na mao, com painter.scale(dpr, dpr), aplica o
    fator DUAS vezes e o desenho vaza para fora do quadro — verificado.)"""
    pixmap = QPixmap(round(w * dpr), round(h * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)
    return pixmap


@lru_cache(maxsize=512)
def _pixmap(name: str, color: str, size: int, dpr: float = 1.0) -> QPixmap:
    path = _ICON_DIR / f"{name}.svg"
    pixmap = blank(size, size, dpr)
    if not path.exists():
        return pixmap
    data = path.read_text(encoding="utf-8").replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    painter = QPainter(pixmap)
    # alvo EXPLICITO em coordenadas logicas: render(painter) sozinho se guia
    # pelo viewport em pixels FISICOS e desenharia o icone dpr vezes maior.
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def icon(name: str, color: str | None = None, size: int = 18) -> QIcon:
    """QIcon do icone 'name' (sem extensao), recolorido para 'color'.

    'color=None' usa theme.ICON resolvido AGORA (varredura 09/07: o default
    avaliado na importação congelava a cor do tema claro para sempre)."""
    return QIcon(_pixmap(name, color or theme.ICON, size, device_ratio()))


def pixmap(name: str, color: str | None = None, size: int = 18) -> QPixmap:
    """QPixmap do icone (util para QLabel)."""
    return _pixmap(name, color or theme.ICON, size, device_ratio())


def clear_cache() -> None:
    """Esvazia o cache de pixmaps (trocou o tema: cores novas)."""
    _pixmap.cache_clear()
