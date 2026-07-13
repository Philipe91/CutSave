"""Miniaturas ilustrativas dos tipos de faca (combos "Tipo de faca").

Cada modo ganha um desenho de 26px: a ARTE é uma estrela cinza e a LINHA DE
FACA é tracejada na cor theme.CUT — a mesma linguagem visual do canvas, para
o cliente reconhecer na hora o que cada opção faz com o corte.

Desenhadas com QPainter em runtime (nada de SVG externo): as cores dos tokens
entram na CHAVE do cache, então trocar o tema gera miniaturas novas sozinho.
"""

from __future__ import annotations

import math
from functools import lru_cache

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

from app.presentation import theme

# Texto que aparece ao pairar sobre CADA opção do dropdown (ToolTipRole).
MODE_HINTS = {
    "auto": (
        "Decide sozinho pelo tipo da arte:\n"
        "JPG/fundo sólido vira retângulo; PNG com\n"
        "transparência corta no formato do desenho."
    ),
    "rect": "Corta a caixa por fora (corte reto),\nvale para qualquer arte.",
    "contour": "Corta exatamente no formato do desenho.",
    "contour_smooth": (
        "Corta no formato do desenho arredondando\ncantos e serrilhados."
    ),
    "contour_simplify": (
        "Corta no formato com menos nós:\nfaca mais leve e corte mais fluido."
    ),
    "vector": "Usa a linha de corte vetorial que\njá veio dentro do PDF do cliente.",
}


def _star(cx: float, cy: float, r_out: float, r_in: float, n: int = 5) -> QPolygonF:
    """Estrela de n pontas centrada em (cx, cy), bico para cima."""
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        ang = -math.pi / 2 + i * math.pi / n
        pts.append(QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return QPolygonF(pts)


def _rounded_path(poly: QPolygonF, radius: float) -> QPainterPath:
    """Caminho fechado do polígono com os cantos aparados em curva."""
    n = poly.count()
    path = QPainterPath()
    for i in range(n):
        prev, cur, nxt = poly[(i - 1) % n], poly[i], poly[(i + 1) % n]
        v_in, v_out = cur - prev, nxt - cur
        len_in = math.hypot(v_in.x(), v_in.y()) or 1.0
        len_out = math.hypot(v_out.x(), v_out.y()) or 1.0
        d = min(radius, len_in / 2, len_out / 2)
        a = cur - v_in * (d / len_in)   # entra no canto
        b = cur + v_out * (d / len_out)  # sai do canto
        if i == 0:
            path.moveTo(a)
        else:
            path.lineTo(a)
        path.quadTo(cur, b)
    path.closeSubpath()
    return path


def _dash_pen(color: str, width: float = 1.4) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setStyle(Qt.DashLine)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


@lru_cache(maxsize=64)
def _mode_pixmap(mode: str, cut: str, muted: str, accent: str, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    c = size / 2.0
    art = _star(c, c, size * 0.30, size * 0.135)
    faca = _star(c, c, size * 0.43, size * 0.20)

    # arte: preenchimento discreto, sem borda (o protagonista é a faca)
    fill = QColor(muted)
    fill.setAlpha(110)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(fill))
    p.drawPolygon(art)

    p.setBrush(Qt.NoBrush)
    p.setPen(_dash_pen(cut))

    if mode == "rect":
        m = size * 0.11
        p.drawRect(int(m), int(m), int(size - 2 * m), int(size - 2 * m))
    elif mode == "contour":
        p.drawPolygon(faca)
    elif mode == "contour_smooth":
        p.drawPath(_rounded_path(faca, size * 0.10))
    elif mode == "contour_simplify":
        # só os 5 bicos (pentágono): "menos nós", com os nós marcados
        outer = QPolygonF([faca[i] for i in range(0, faca.count(), 2)])
        p.drawPolygon(outer)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(cut)))
        s = size * 0.09
        for i in range(outer.count()):
            v = outer[i]
            p.drawRect(int(v.x() - s / 2), int(v.y() - s / 2), int(s), int(s))
    elif mode == "vector":
        p.drawPolygon(faca)
        # nó com alças de curva (estilo vetor do Corel) no bico de cima
        top = faca[0]
        h = size * 0.16
        p.setPen(QPen(QColor(accent), 1.2))
        p.drawLine(top, QPointF(top.x() - h, top.y() + h * 0.35))
        p.drawLine(top, QPointF(top.x() + h, top.y() - h * 0.35))
        p.setBrush(QBrush(QColor(accent)))
        r = size * 0.05
        for pt in (
            QPointF(top.x() - h, top.y() + h * 0.35),
            QPointF(top.x() + h, top.y() - h * 0.35),
        ):
            p.drawEllipse(pt, r, r)
        p.setPen(Qt.NoPen)
        s = size * 0.10
        p.drawRect(int(top.x() - s / 2), int(top.y() - s / 2), int(s), int(s))
    else:  # "auto" (e qualquer modo futuro): contorno + selo "A" de automático
        p.drawPolygon(faca)
        badge_r = size * 0.17
        bx, by = size - badge_r - 1, size - badge_r - 1
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(accent)))
        p.drawEllipse(QPointF(bx, by), badge_r, badge_r)
        f = QFont()
        f.setPixelSize(int(badge_r * 1.5))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(
            int(bx - badge_r), int(by - badge_r), int(badge_r * 2), int(badge_r * 2),
            Qt.AlignCenter, "A",
        )

    p.end()
    return pm


def mode_icon(mode: str, size: int = 26) -> QIcon:
    """QIcon ilustrativo do tipo de faca, nas cores do tema ATUAL."""
    return QIcon(_mode_pixmap(mode, theme.CUT, theme.TEXT_MUTED, theme.ACCENT, size))
