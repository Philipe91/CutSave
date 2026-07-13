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

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.presentation import theme
from app.shared.resources import resource_path

_ICON_DIR = resource_path("assets/icons")


@lru_cache(maxsize=512)
def _pixmap(name: str, color: str, size: int) -> QPixmap:
    path = _ICON_DIR / f"{name}.svg"
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    if not path.exists():
        return pixmap
    data = path.read_text(encoding="utf-8").replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def icon(name: str, color: str | None = None, size: int = 18) -> QIcon:
    """QIcon do icone 'name' (sem extensao), recolorido para 'color'.

    'color=None' usa theme.ICON resolvido AGORA (varredura 09/07: o default
    avaliado na importação congelava a cor do tema claro para sempre)."""
    return QIcon(_pixmap(name, color or theme.ICON, size))


def pixmap(name: str, color: str | None = None, size: int = 18) -> QPixmap:
    """QPixmap do icone (util para QLabel)."""
    return _pixmap(name, color or theme.ICON, size)


def clear_cache() -> None:
    """Esvazia o cache de pixmaps (trocou o tema: cores novas)."""
    _pixmap.cache_clear()
