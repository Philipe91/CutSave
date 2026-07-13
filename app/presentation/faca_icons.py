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


# ---------------------------------------------------------------------------
# Demais glifos ilustrativos (nós, modo do corte, sangria, registro, caixas,
# visualização, raio). Mesma receita: QPainter + cores do tema na chave.
# ---------------------------------------------------------------------------

NODE_HINTS = {
    "fino": "Mais nós: máximo detalhe nas curvas\n(desvio máx. 0,1mm).",
    "medio": "Equilíbrio entre detalhe e fluidez\n(desvio máx. 0,3mm) — recomendado.",
    "leve": "Menos nós: corte mais fluido na máquina\n(desvio máx. 0,6mm).",
}
SHARED_HINTS = {
    "piece": "Cada peça com a própria faca.\nCortes rentes se fundem sozinhos.",
    "grid": "Uma faca só, atravessando a chapa\nde fora a fora (estilo guilhotina).",
}
REG_HINTS = {
    "none": "Sem marcas de registro na chapa.",
    "circles": "Bolinhas nos cantos da chapa\n(leitura óptica das mesas IECHO).",
    "mimaki": "Marcas em L nos cantos\n(leitura das plotters Mimaki).",
    "both": "As duas marcas juntas: corta na\nMimaki e refila na IECHO.",
}
BOX_HINTS = {
    "media": "Usa a página inteira do PDF,\nincluindo a sangria (arte vaza).",
    "trim": "Usa a área final de corte do PDF\n(o tamanho fechado do produto).",
}
VIEW_HINTS = {
    "both": "Arte e linha de faca juntas no canvas.",
    "print": "Só a arte, sem as linhas de faca.",
    "cut": "Só as linhas de faca, sem a arte.",
    "split": "Impressão à esquerda, corte à direita.",
}


def _sheet_rect(p: QPainter, size: int, muted: str, margin: float = 0.14):
    """Chapinha de fundo (borda discreta); devolve o retângulo interno."""
    m = size * margin
    r = (m, m, size - 2 * m, size - 2 * m)
    p.setPen(QPen(QColor(muted), 1.2))
    p.setBrush(Qt.NoBrush)
    p.drawRect(int(r[0]), int(r[1]), int(r[2]), int(r[3]))
    return r


@lru_cache(maxsize=256)
def _glyph_pixmap(kind: str, key: str, cut: str, muted: str, accent: str, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = size / 2.0

    if kind == "nodes":
        # curva da faca com a densidade de nós do nível escolhido
        path = QPainterPath(QPointF(size * 0.10, size * 0.68))
        path.cubicTo(
            QPointF(size * 0.32, size * 0.05),
            QPointF(size * 0.55, size * 0.95),
            QPointF(size * 0.90, size * 0.35),
        )
        p.setPen(QPen(QColor(cut), 1.3))
        p.drawPath(path)
        count = {"fino": 8, "medio": 5, "leve": 3}.get(key, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(cut)))
        s = size * 0.11
        for i in range(count):
            pt = path.pointAtPercent(i / (count - 1))
            p.drawRect(int(pt.x() - s / 2), int(pt.y() - s / 2), int(s), int(s))

    elif kind == "shared":
        p.setBrush(Qt.NoBrush)
        p.setPen(_dash_pen(cut, 1.2))
        if key == "grid":
            m = size * 0.12
            p.drawRect(int(m), int(m), int(size - 2 * m), int(size - 2 * m))
            p.drawLine(QPointF(m, c), QPointF(size - m, c))        # fora a fora
            p.drawLine(QPointF(c, m), QPointF(c, size - m))
        else:  # piece: 4 quadradinhos, cada um com o próprio corte
            cell = size * 0.30
            gap = size * 0.14
            m = (size - 2 * cell - gap) / 2
            for dx in (0, cell + gap):
                for dy in (0, cell + gap):
                    p.drawRect(int(m + dx), int(m + dy), int(cell), int(cell))

    elif kind == "offset":
        art_r = size * 0.26 if key == "out" else size * 0.40
        faca_r = size * 0.41 if key == "out" else size * 0.25
        fill = QColor(muted)
        fill.setAlpha(110)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(fill))
        p.drawPolygon(_star(c, c, art_r, art_r * 0.45))
        p.setBrush(Qt.NoBrush)
        p.setPen(_dash_pen(cut))
        p.drawPolygon(_star(c, c, faca_r, faca_r * 0.45))

    elif kind == "regmark":
        r = _sheet_rect(p, size, muted)
        x0, y0, w, h = r
        x1, y1 = x0 + w, y0 + h
        ink = QColor(cut)
        if key in ("circles", "both"):
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(ink))
            d = size * 0.13
            inset = size * 0.09
            for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                cx = px + (inset if px == x0 else -inset)
                cy = py + (inset if py == y0 else -inset)
                p.drawEllipse(QPointF(cx, cy), d / 2, d / 2)
        if key in ("mimaki", "both"):
            p.setPen(QPen(ink, 1.4))
            p.setBrush(Qt.NoBrush)
            arm = size * 0.16
            off = size * 0.02 if key == "mimaki" else size * 0.20
            for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                sx = 1 if px == x0 else -1
                sy = 1 if py == y0 else -1
                ax, ay = px + sx * off, py + sy * off
                p.drawLine(QPointF(ax, ay), QPointF(ax + sx * arm, ay))
                p.drawLine(QPointF(ax, ay), QPointF(ax, ay + sy * arm))

    elif kind == "importbox":
        m = size * 0.12
        page = (m, m, size - 2 * m, size - 2 * m)
        fill = QColor(muted)
        fill.setAlpha(90)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(fill))
        if key == "media":  # arte vaza até a borda (sangria faz parte)
            p.drawRect(int(page[0]), int(page[1]), int(page[2]), int(page[3]))
        else:  # trim: arte no miolo, aparas em volta
            t = size * 0.11
            p.drawRect(
                int(page[0] + t), int(page[1] + t),
                int(page[2] - 2 * t), int(page[3] - 2 * t),
            )
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(muted), 1.0))
        p.drawRect(int(page[0]), int(page[1]), int(page[2]), int(page[3]))
        p.setPen(_dash_pen(cut, 1.2))
        if key == "media":
            p.drawRect(int(page[0]), int(page[1]), int(page[2]), int(page[3]))
        else:
            t = size * 0.11
            p.drawRect(
                int(page[0] + t), int(page[1] + t),
                int(page[2] - 2 * t), int(page[3] - 2 * t),
            )

    elif kind == "viewmode":
        r = _sheet_rect(p, size, muted, margin=0.10)
        fill = QColor(muted)
        fill.setAlpha(130)
        if key == "split":
            p.setPen(QPen(QColor(muted), 1.0))
            p.drawLine(QPointF(c, r[1]), QPointF(c, r[1] + r[3]))
            lx, rx = r[0] + r[2] * 0.25, r[0] + r[2] * 0.75
            cy = r[1] + r[3] / 2
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(fill))
            p.drawPolygon(_star(lx, cy, size * 0.16, size * 0.072))
            p.setBrush(Qt.NoBrush)
            p.setPen(_dash_pen(cut, 1.1))
            p.drawPolygon(_star(rx, cy, size * 0.16, size * 0.072))
        else:
            if key in ("both", "print"):
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(fill))
                p.drawPolygon(_star(c, c, size * 0.22, size * 0.10))
            if key in ("both", "cut"):
                p.setBrush(Qt.NoBrush)
                p.setPen(_dash_pen(cut, 1.2))
                p.drawPolygon(_star(c, c, size * 0.30, size * 0.135))

    elif kind == "radius":
        # canto vivo (cinza) virando canto arredondado (faca tracejada)
        m = size * 0.18
        p.setPen(QPen(QColor(muted), 1.3))
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(size - m, m), QPointF(m, m))
        p.drawLine(QPointF(m, m), QPointF(m, size - m))
        # paralela arredondada, deslocada para dentro
        rr = size * 0.34
        d = size * 0.16
        path = QPainterPath(QPointF(size - m, m + d))
        path.lineTo(QPointF(m + d + rr, m + d))
        path.quadTo(QPointF(m + d, m + d), QPointF(m + d, m + d + rr))
        path.lineTo(QPointF(m + d, size - m))
        p.setPen(_dash_pen(cut, 1.3))
        p.drawPath(path)

    p.end()
    return pm


def nodes_icon(level: str, size: int = 26) -> QIcon:
    return QIcon(_glyph_pixmap("nodes", level or "", theme.CUT, theme.TEXT_MUTED, theme.ACCENT, size))


def shared_icon(kind: str, size: int = 26) -> QIcon:
    return QIcon(_glyph_pixmap("shared", kind or "", theme.CUT, theme.TEXT_MUTED, theme.ACCENT, size))


def offset_icon(direction: str, size: int = 22) -> QIcon:
    return QIcon(_glyph_pixmap("offset", direction or "", theme.CUT, theme.TEXT_MUTED, theme.ACCENT, size))


def regmark_icon(kind: str, size: int = 26) -> QIcon:
    return QIcon(_glyph_pixmap("regmark", kind or "", theme.CUT, theme.TEXT_MUTED, theme.ACCENT, size))


def import_box_icon(kind: str, size: int = 26) -> QIcon:
    return QIcon(_glyph_pixmap("importbox", kind or "", theme.CUT, theme.TEXT_MUTED, theme.ACCENT, size))


def view_mode_icon(kind: str, size: int = 26) -> QIcon:
    return QIcon(_glyph_pixmap("viewmode", kind or "", theme.CUT, theme.TEXT_MUTED, theme.ACCENT, size))


def corner_radius_pixmap(size: int = 22) -> QPixmap:
    return _glyph_pixmap("radius", "", theme.CUT, theme.TEXT_MUTED, theme.ACCENT, size)


# ---------------------------------------------------------------------------
# Canvas vazio: os 3 passos do fluxo ilustrados (Adicionar → Gerar → Exportar)
# ---------------------------------------------------------------------------

_STEPS = ("Adicionar", "Gerar Faca", "Exportar")


@lru_cache(maxsize=16)
def _steps_pixmap(active: int, cut: str, muted: str, accent: str) -> QPixmap:
    col_w, glyph, label_h, arrow_w = 96, 44, 20, 26
    w = 3 * col_w + 2 * arrow_w
    h = glyph + 8 + label_h
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont()
    f.setPixelSize(13)

    for i in range(3):
        x0 = i * (col_w + arrow_w)
        color = accent if i == active else muted
        pen = QPen(QColor(color), 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        gx = x0 + (col_w - glyph) / 2  # canto do quadro do glifo
        cx, cy = gx + glyph / 2, glyph / 2

        if i == 0:  # página + seta entrando (arrastar/adicionar)
            pw, ph = glyph * 0.52, glyph * 0.68
            px, py = cx - pw / 2, cy - ph / 2 + glyph * 0.08
            ear = pw * 0.30
            page = QPainterPath(QPointF(px, py))
            page.lineTo(px + pw - ear, py)
            page.lineTo(px + pw, py + ear)
            page.lineTo(px + pw, py + ph)
            page.lineTo(px, py + ph)
            page.closeSubpath()
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(page)
            p.drawLine(QPointF(px + pw - ear, py), QPointF(px + pw - ear, py + ear))
            p.drawLine(QPointF(px + pw - ear, py + ear), QPointF(px + pw, py + ear))
            ax = px + pw * 0.38
            p.drawLine(QPointF(ax, py + ph * 0.22), QPointF(ax, py + ph * 0.62))
            p.drawLine(QPointF(ax - 5, py + ph * 0.42), QPointF(ax, py + ph * 0.62))
            p.drawLine(QPointF(ax + 5, py + ph * 0.42), QPointF(ax, py + ph * 0.62))
        elif i == 1:  # arte + faca tracejada (o coração do produto)
            fill = QColor(color)
            fill.setAlpha(110)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(fill))
            p.drawPolygon(_star(cx, cy, glyph * 0.26, glyph * 0.12))
            p.setBrush(Qt.NoBrush)
            dash = _dash_pen(cut if i != active else accent, 1.8)
            p.setPen(dash)
            p.drawPolygon(_star(cx, cy, glyph * 0.40, glyph * 0.185))
        else:  # página + seta saindo (exportar)
            pw, ph = glyph * 0.50, glyph * 0.66
            px, py = cx - pw / 2 - glyph * 0.06, cy - ph / 2 + glyph * 0.08
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(int(px), int(py), int(pw), int(ph))
            ay = py + ph * 0.45
            p.drawLine(QPointF(px + pw * 0.45, ay), QPointF(px + pw + glyph * 0.22, ay))
            tip = px + pw + glyph * 0.22
            p.drawLine(QPointF(tip - 6, ay - 5), QPointF(tip, ay))
            p.drawLine(QPointF(tip - 6, ay + 5), QPointF(tip, ay))

        # rótulo do passo ("1. Adicionar"), destacado quando é o passo atual
        f.setBold(i == active)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(x0, glyph + 8, col_w, label_h, Qt.AlignHCenter | Qt.AlignTop,
                   f"{i + 1}. {_STEPS[i]}")

        if i < 2:  # seta entre os passos
            axc = x0 + col_w + arrow_w / 2
            p.setPen(QPen(QColor(muted), 1.6, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(axc - 6, cy), QPointF(axc + 6, cy))
            p.drawLine(QPointF(axc + 1, cy - 5), QPointF(axc + 6, cy))
            p.drawLine(QPointF(axc + 1, cy + 5), QPointF(axc + 6, cy))

    p.end()
    return pm


def empty_steps_pixmap(active: int = 0) -> QPixmap:
    """Faixa com os 3 passos do fluxo para o canvas vazio; o passo ativo sai
    na cor de destaque do tema."""
    return _steps_pixmap(active, theme.CUT, theme.TEXT_MUTED, theme.ACCENT)
