"""Espaco que uma peca ocupa na chapa, e como levar a geometria dela ate la.

Duas coisas moram aqui porque sao a MESMA conta vista de dois angulos: o
nesting pergunta "quanto isto ocupa?" e o preview/exportadores perguntam "onde
fica cada ponto?". Quando as duas respostas discordam, a peca sai desenhada
fora do espaco que o encaixe reservou para ela — e ninguem percebe ate a chapa
impressa.
"""

from __future__ import annotations

from collections.abc import Callable

from app.domain.geometry import BoundingBox, Point2D, Size
from app.domain.model.artwork import Artwork

# Giros que o nesting de IMPRESSAO emite. O Modo Corte usa angulo livre e tem
# caminho proprio (run_true_shape_nesting).
GIROS_RETOS = (0, 90, 180, 270)


def artwork_footprint(art: Artwork) -> BoundingBox:
    """Area que a peca ocupa na chapa (art-local): uniao da arte com a faca.

    Garante footprint correto mesmo quando a faca e menor que a arte (recuo
    de seguranca): nesse caso vale a arte, evitando sobreposicao no nesting.
    """
    min_x, min_y = 0.0, 0.0
    max_x, max_y = art.size.width, art.size.height
    if art.has_cut:
        faca = art.cut_contour
        ox, oy = faca.origin.x, faca.origin.y
        min_x = min(min_x, ox)
        min_y = min(min_y, oy)
        max_x = max(max_x, ox + faca.size.width)
        max_y = max(max_y, oy + faca.size.height)
    return BoundingBox(min_x, min_y, max_x, max_y)


def giro_reto(rotacao) -> int:
    """Normaliza o giro para 0/90/180/270. Qualquer outro valor vira 0."""
    try:
        graus = int(round(float(rotacao))) % 360
    except (TypeError, ValueError):
        return 0
    return graus if graus in GIROS_RETOS else 0


def tamanho_ocupado(art: Artwork, rotacao=0) -> Size:
    """Quanto a peca ocupa na chapa JA GIRADA (a 90/270 os lados trocam)."""
    fp = artwork_footprint(art)
    if giro_reto(rotacao) in (90, 270):
        return Size(fp.height, fp.width)
    return Size(fp.width, fp.height)


def mapeador_da_peca(art: Artwork, rotacao=0) -> Callable[[Point2D], Point2D]:
    """Leva um ponto art-local para a peca GIRADA, com origem em (0, 0).

    Somar `item.position` ao resultado da a coordenada na chapa. Sem giro, a
    conta e a de sempre — ponto menos o canto do footprint —, entao layout
    antigo continua saindo pixel a pixel igual.

    O eixo Y aponta para BAIXO (convencao da tela e do PDF de impressao), por
    isso o giro de 90 leva (x, y) em (max_y - y, x): o que estava em cima vai
    para a direita.
    """
    fp = artwork_footprint(art)
    graus = giro_reto(rotacao)
    if graus == 90:
        return lambda p: Point2D(fp.max_y - p.y, p.x - fp.min_x)
    if graus == 180:
        return lambda p: Point2D(fp.max_x - p.x, fp.max_y - p.y)
    if graus == 270:
        return lambda p: Point2D(p.y - fp.min_y, fp.max_x - p.x)
    return lambda p: Point2D(p.x - fp.min_x, p.y - fp.min_y)


def pontos_na_chapa(art: Artwork, item, pontos, dx: float = 0.0) -> list[Point2D]:
    """Pontos art-local -> coordenadas da chapa, honrando o giro da instancia."""
    mapear = mapeador_da_peca(art, getattr(item, "rotation", 0))
    ox, oy = item.position.x + dx, item.position.y
    saida = []
    for p in pontos:
        q = mapear(p)
        saida.append(Point2D(q.x + ox, q.y + oy))
    return saida
