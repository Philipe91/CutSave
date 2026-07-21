"""True-shape nesting (Modo Corte): encaixa pecas pelo CONTORNO real, nao pelo
bounding box — mesma tecnica do eCut/SVGnest (NFP + genetico).

Construido em sub-fases:
- 2A: oraculo bruteforce — posicionador simples e comprovadamente correto
  (teste de sobreposicao direto via pyclipper). Lento de proposito; serve de
  GABARITO para validar o NFP.
- 2B: No-Fit Polygon via Minkowski (_nfp/_nfp_blocks), validado por teste de
  concordancia ponto a ponto contra o oraculo.
- 2C: IFP retangular (_ifp_rect) + posicionador bottom-left (_place_nfp),
  validado contra o oraculo (mesmas pecas, contagem/area/sobreposicao).
- 2D: rotacao + algoritmo genetico (_optimize_ga): cromossomo = (ordem,
  rotacoes), NFP cacheado por (forma, rotacao) — nunca recomputado dentro do
  laco do GA —, fitness = chapa consumida (comprimento x largura) + penalidade
  alta por peca de fora. Deterministico por seed (random.Random local, nada de
  random global).
- 2E: interface publica TrueShapePacker (pack/pack_sheets -> Layout) +
  reconciliacao com o enum Rotation + simplificacao de contorno
  (approximation, estilo Approximation_CB do eCut).
- 6 (inside_check, "Allow inside" de mercado): peca pequena entra no FURO de
  outra peca ja posta (miolo do "O", vao do "8"). O furo vira um SEGUNDO
  container: _ifp_hole calcula, por erosao de Minkowski, onde a referencia da
  peca pode cair para ela ficar inteira dentro do furo.

Convencoes criticas (nao mudar sem revalidar contra o oraculo):
- ESCALA INTEIRA: pyclipper opera em ints. Toda geometria em mm passa por
  _to_clipper (x SCALE) antes e _from_clipper (/ SCALE) depois.
- PONTO DE REFERENCIA: canto inferior-esquerdo do bounding box da peca.
  'position' de uma peca = onde esse canto cai na chapa. NFP e IFP usam a
  MESMA referencia.
"""

from __future__ import annotations

import math
import random
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace

import pyclipper

from app.domain.geometry import Point2D
from app.domain.geometry.polygon import Polygon
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem, Rotation

# mm -> unidade inteira do clipper (0,1 micron). Ver "escala inteira" acima.
_SCALE = 10_000
# Tolerancia geometrica em mm (mesma ideia do _EPS do MaxRects).
_EPS = 0.01
# Areas menores que isso (mm2) sao residuo numerico de bordas encostadas.
_AREA_EPS = _EPS * _EPS
# Fitness: cada peca NAO colocada custa isso (mm2). Ordens de grandeza acima
# de qualquer area de bounding real — perder peca doi mais que qualquer ganho.
_UNPLACED_PENALTY = 1e8


@dataclass(frozen=True, slots=True)
class NestingShape:
    """Peca para o nesting true-shape: contorno real + rotacoes permitidas."""

    artwork_id: str
    contour: Polygon
    rotations: tuple[float, ...] = (0.0, 90.0, 180.0, 270.0)
    # Furos (letra "O"). Sem inside_check o motor usa SO o contour externo e os
    # furos apenas viajam ate a Fase 4, que exporta o corte interno com o MESMO
    # transform do outer. COM inside_check (Fase 6) eles viram container: cada
    # furo de uma peca posta recebe outras pecas dentro.
    holes: tuple[Polygon, ...] = ()


@dataclass(frozen=True, slots=True)
class _Placement:
    """Resultado interno: onde a referencia (bbox.min) da peca caiu na chapa."""

    artwork_id: str
    position: Point2D
    rotation: float


# --- ponte mm <-> clipper (Regra de Ouro n.1) --------------------------------


def _to_clipper(polygon: Polygon) -> list[tuple[int, int]]:
    return [(round(p.x * _SCALE), round(p.y * _SCALE)) for p in polygon.vertices]


def _from_clipper(path: Sequence[Sequence[int]]) -> Polygon:
    return Polygon(tuple(Point2D(x / _SCALE, y / _SCALE) for x, y in path))


def _offset(polygon: Polygon, delta_mm: float) -> Polygon:
    """Infla (delta>0) ou encolhe o poligono. JT_MITER preserva cantos retos."""
    if abs(delta_mm) < 1e-9:
        return polygon
    off = pyclipper.PyclipperOffset()
    off.AddPath(_to_clipper(polygon), pyclipper.JT_MITER, pyclipper.ET_CLOSEDPOLYGON)
    solution = off.Execute(delta_mm * _SCALE)
    # offset pode fragmentar; a fronteira externa e o caminho de maior area.
    outer = max(solution, key=lambda p: abs(pyclipper.Area(p)))
    return _from_clipper(outer)


def _shrunk(polygon: Polygon, delta_mm: float) -> Polygon | None:
    """Encolhe o poligono em 'delta_mm'. None quando ele SOME (peca/furo menor
    que o dobro da folga) — _offset nao serve aqui porque com solucao vazia o
    max() dele estouraria.
    """
    if delta_mm <= 1e-9:
        return polygon
    off = pyclipper.PyclipperOffset()
    off.AddPath(_to_clipper(polygon), pyclipper.JT_MITER, pyclipper.ET_CLOSEDPOLYGON)
    solution = off.Execute(-delta_mm * _SCALE)
    if not solution:
        return None
    inner = max(solution, key=lambda p: abs(pyclipper.Area(p)))
    if len(inner) < 3 or abs(pyclipper.Area(inner)) / (_SCALE * _SCALE) <= _AREA_EPS:
        return None
    return _from_clipper(inner)


# --- oraculo 2A: testes diretos, sem NFP -------------------------------------


def _material_paths(
    outer: Polygon, holes: Sequence[Polygon] = (), gap: float = 0.0
) -> list[list[tuple[int, int]]]:
    """MATERIAL da peca com a folga ja embutida, em caminhos do clipper:
    contorno inflado em gap/2 e furos ENCOLHIDOS em gap/2.

    Os dois lados do gap: a peca hospedada infla gap/2 e a parede do furo
    "avanca" gap/2 para dentro — senao o laser funde a peca interna na parede.
    Furo que some no encolhimento simplesmente deixa de valer como vao.

    Sem furos (o caso de sempre, e o unico quando inside_check esta desligado)
    isto e exatamente o contorno inflado de antes.
    """
    paths = [_to_clipper(_offset(outer, gap / 2))]
    for hole in holes:
        small = _shrunk(hole, gap / 2)
        if small is not None:
            paths.append(_to_clipper(small))
    return paths


def _overlaps_paths(
    paths_a: Sequence[Sequence[tuple[int, int]]],
    paths_b: Sequence[Sequence[tuple[int, int]]],
) -> bool:
    """Interseccao de dois materiais (saidas de _material_paths) com area real.

    EVENODD nos dois lados: o anel do furo vira vao qualquer que seja a
    orientacao que o clipper deu ao caminho.
    """
    pc = pyclipper.Pyclipper()
    pc.AddPaths(list(paths_a), pyclipper.PT_SUBJECT, True)
    pc.AddPaths(list(paths_b), pyclipper.PT_CLIP, True)
    inter = pc.Execute(pyclipper.CT_INTERSECTION, pyclipper.PFT_EVENODD, pyclipper.PFT_EVENODD)
    area_mm2 = sum(abs(pyclipper.Area(p)) for p in inter) / (_SCALE * _SCALE)
    return area_mm2 > _AREA_EPS


def _overlaps(
    poly_a: Polygon,
    poly_b: Polygon,
    gap: float = 0.0,
    holes_a: Sequence[Polygon] = (),
    holes_b: Sequence[Polygon] = (),
) -> bool:
    """True se as pecas ficam mais proximas que 'gap' (folga total entre elas).

    Cada peca e inflada em gap/2; sobreposicao das versoes infladas = distancia
    real < gap. Borda ENCOSTADA e permitida: interseccao de area ~0 nao conta.

    holes_a/holes_b (Fase 6): furos da respectiva peca, ja posicionados. Uma
    peca hospedada no furo de outra cai DENTRO do contorno externo do
    hospedeiro — sem descontar o furo, o oraculo acusaria sobreposicao com um
    miolo que na verdade e vazio.
    """
    return _overlaps_paths(
        _material_paths(poly_a, holes_a, gap), _material_paths(poly_b, holes_b, gap)
    )


def _contains(outer: Polygon, inner: Polygon) -> bool:
    """True se 'inner' cabe INTEIRO dentro de 'outer' (a diferenca nao sobra
    area). E o teste de contencao que valida cada anel do IFP de furo."""
    pc = pyclipper.Pyclipper()
    pc.AddPath(_to_clipper(inner), pyclipper.PT_SUBJECT, True)
    pc.AddPath(_to_clipper(outer), pyclipper.PT_CLIP, True)
    fora = pc.Execute(pyclipper.CT_DIFFERENCE, pyclipper.PFT_NONZERO, pyclipper.PFT_NONZERO)
    area_mm2 = sum(abs(pyclipper.Area(p)) for p in fora) / (_SCALE * _SCALE)
    return area_mm2 <= _AREA_EPS


def _inside_sheet(poly: Polygon, sheet_w: float, sheet_h: float, margin: float) -> bool:
    bb = poly.bounding_box
    return (
        bb.min_x >= margin - _EPS
        and bb.min_y >= margin - _EPS
        and bb.max_x <= sheet_w - margin + _EPS
        and bb.max_y <= sheet_h - margin + _EPS
    )


def _normalized(contour: Polygon) -> Polygon:
    """Leva a referencia (canto min do bbox) para a origem (Regra de Ouro n.2)."""
    bb = contour.bounding_box
    return contour.translated(-bb.min_x, -bb.min_y)


# --- 2B: No-Fit Polygon via Minkowski ----------------------------------------


def _interior_point(path: Sequence[Sequence[int]]) -> Point2D:
    """Um ponto ESTRITAMENTE interno de um anel clipper (p/ classificar furo).

    Centroide resolve quase sempre; em anel muito concavo (centroide fora),
    tenta a media centroide-vertice ate cair dentro.
    """
    poly = _from_clipper(path)
    c = poly.centroid
    if pyclipper.PointInPolygon((round(c.x * _SCALE), round(c.y * _SCALE)), path) == 1:
        return c
    for v in poly.vertices:
        m = Point2D((c.x + v.x) / 2, (c.y + v.y) / 2)
        if pyclipper.PointInPolygon((round(m.x * _SCALE), round(m.y * _SCALE)), path) == 1:
            return m
    return c  # melhor esforco; o teste de concordancia pega se falhar


def _nfp(poly_a: Polygon, poly_b: Polygon) -> tuple[Polygon, ...]:
    """No-Fit Polygon de A (parada) e B (orbitando): NFP(A,B) = A (+) -B.

    Pre-condicao: AMBAS ja com o offset de gap/2 aplicado (o mesmo que o
    oraculo _overlaps usa) e B normalizada (referencia bbox.min na origem).
    Retorna aneis: [0] = fronteira externa (maior area); demais = FUROS
    verdadeiros (vaos/concavidades onde B encaixa sem sobrepor).

    Armadilha do Clipper: MinkowskiSum soma o padrao com a BORDA do caminho,
    entao o resultado pode trazer furos que NAO sao vaos reais (ex.: B maior
    que A gera um miolo oco onde na verdade B engole A = sobrepoe). Por isso
    cada furo candidato e conferido com UM teste do oraculo: interior do furo
    sem sobreposicao real -> furo legitimo; senao e artefato e cai fora.
    """
    a = _to_clipper(poly_a)
    b_neg = [(-x, -y) for x, y in _to_clipper(poly_b)]
    paths = pyclipper.MinkowskiSum(a, b_neg, True)
    paths.sort(key=lambda p: abs(pyclipper.Area(p)), reverse=True)
    keep = [paths[0]]  # fronteira externa
    for hole in paths[1:]:
        if abs(pyclipper.Area(hole)) / (_SCALE * _SCALE) <= _AREA_EPS:
            continue  # residuo numerico
        t = _interior_point(hole)
        # gap=0: os poligonos JA vieram inflados; aqui e so interseccao crua.
        if not _overlaps(poly_a, poly_b.translated(t.x, t.y)):
            keep.append(hole)
    return tuple(_from_clipper(p) for p in keep)


def _nfp_blocks(nfp: Sequence[Polygon], point: Point2D) -> bool:
    """True se por a referencia de B em 'point' SOBREPOE A (ponto estritamente
    dentro do NFP). Fronteira de qualquer anel = encostar, permitido. Contagem
    par-impar sobre os aneis: dentro so da externa = bloqueado; dentro da
    externa E de um furo = vao legitimo, permitido.
    """
    pt = (round(point.x * _SCALE), round(point.y * _SCALE))
    dentro = 0
    for ring in nfp:
        r = pyclipper.PointInPolygon(pt, _to_clipper(ring))
        if r == -1:
            return False  # exatamente na fronteira: encosta
        if r == 1:
            dentro += 1
    return dentro % 2 == 1


def _place_bruteforce(
    shapes: Sequence[NestingShape],
    material: Material,
    sheet_h: float,
    step: float = 4.0,
) -> list[_Placement]:
    """Oraculo: varre uma grade grossa (passo 'step' mm) baixo->cima e
    esquerda->direita e fixa cada peca na primeira posicao valida. Sem rotacao
    e sem otimizacao — o valor dele e ser OBVIAMENTE correto para validar o NFP.
    Peca que nao coube fica de fora (o chamador compara pelas contagens).
    """
    gap = max(0.0, material.spacing)
    margin = material.margin
    sheet_w = material.width
    ordered = sorted(shapes, key=lambda s: s.contour.area, reverse=True)
    placements: list[_Placement] = []
    placed_polys: list[Polygon] = []
    for shape in ordered:
        base = _normalized(shape.contour)
        bb = base.bounding_box
        spot: tuple[float, float] | None = None
        y = margin
        while spot is None and y <= sheet_h - margin - bb.height + _EPS:
            x = margin
            while x <= sheet_w - margin - bb.width + _EPS:
                cand = base.translated(x, y)
                if _inside_sheet(cand, sheet_w, sheet_h, margin) and all(
                    not _overlaps(cand, p, gap) for p in placed_polys
                ):
                    spot = (x, y)
                    break
                x += step
            y += step
        if spot is None:
            continue
        placements.append(_Placement(shape.artwork_id, Point2D(*spot), 0.0))
        placed_polys.append(base.translated(*spot))
    return placements


# --- 2C: IFP retangular + posicionador NFP bottom-left ------------------------


def _ifp_rect(piece: Polygon, sheet_w: float, sheet_h: float, margin: float) -> Polygon | None:
    """Inner-Fit Polygon p/ chapa RETANGULAR: regiao valida da REFERENCIA
    (bbox.min) para a peca ficar inteira dentro da chapa respeitando a margem
    = retangulo [margin, margin] .. [sheet - margin - (w, h)].

    Usa o bbox da peca CRUA (sem o offset de gap): margem e distancia ate a
    borda da chapa, exatamente como o oraculo (_inside_sheet); o gap so vale
    ENTRE pecas. None = peca nao cabe na chapa em nenhuma posicao.

    Encaixe justo (sobra zero em x ou y): o retangulo degenera em linha e o
    clipper descartaria; alarga 1 unidade de clipper (1e-4 mm, muito abaixo
    de _EPS) so para a regiao sobreviver as diferencas.

    Container irregular (Use_Last_As_Container): TODO de fase futura.
    """
    bb = piece.bounding_box
    max_x = sheet_w - margin - bb.width
    max_y = sheet_h - margin - bb.height
    if max_x < margin - _EPS or max_y < margin - _EPS:
        return None
    max_x = max(max_x, margin + 1 / _SCALE)
    max_y = max(max_y, margin + 1 / _SCALE)
    return Polygon((
        Point2D(margin, margin),
        Point2D(max_x, margin),
        Point2D(max_x, max_y),
        Point2D(margin, max_y),
    ))


def _ifp_hole(hole: Polygon, piece: Polygon) -> tuple[Polygon, ...]:
    """Fase 6 — Inner-Fit Polygon de um FURO: regiao onde a REFERENCIA de
    'piece' (a origem do sistema dela, que por convencao e o bbox.min do
    contorno normalizado) pode cair para a peca ficar INTEIRA dentro do furo.

    Erosao de Minkowski, o espelho do NFP: somar a borda do furo com -peca
    varre uma FAIXA; o lado de fora da faixa e onde a peca escapa do furo e o
    ANEL INTERNO dela e exatamente {t : peca + t contida no furo}. Furo muito
    concavo (o vao do "8", um "C") pode partir a erosao em varios pedacos —
    por isso devolve TODOS os aneis internos que passarem no teste.

    Pre-condicoes (mesma convencao do _nfp): 'hole' ja ENCOLHIDO em gap/2 e
    'piece' ja INFLADA em gap/2 — o offset nao mexe na origem, entao a
    referencia continua valendo. Devolve () quando nada cabe.

    Armadilha do Clipper (a mesma do _nfp): a soma e feita pela BORDA, entao
    um anel interno pode ser artefato. Cada candidato leva um teste de
    contencao real (_contains) antes de entrar.
    """
    # Atalhos baratos antes do Minkowski (a conta cara). Sao condicoes
    # NECESSARIAS para a contencao, entao nao descartam nenhum encaixe real:
    # peca contida no furo tem bbox contido no bbox do furo e area menor. Num
    # lote de letras isso corta a esmagadora maioria dos pares (letra grande x
    # contraforma de outra letra) sem tocar no clipper.
    hb, pb = hole.bounding_box, piece.bounding_box
    if pb.width > hb.width + _EPS or pb.height > hb.height + _EPS:
        return ()
    if piece.area > hole.area:
        return ()
    piece_neg = [(-x, -y) for x, y in _to_clipper(piece)]
    paths = pyclipper.MinkowskiSum(piece_neg, _to_clipper(hole), True)
    if len(paths) < 2:
        return ()  # faixa sem miolo: o furo nao sobrou nada por dentro
    paths.sort(key=lambda p: abs(pyclipper.Area(p)), reverse=True)
    keep: list[Polygon] = []
    for ring in paths[1:]:  # [0] = fronteira externa da faixa
        if abs(pyclipper.Area(ring)) / (_SCALE * _SCALE) <= _AREA_EPS:
            continue  # residuo numerico
        if len(ring) < 3:
            continue
        t = _interior_point(ring)
        if _contains(hole, piece.translated(t.x, t.y)):
            keep.append(_from_clipper(ring))
    return tuple(keep)


def _rotated_parts(shape: NestingShape, rotation: float) -> tuple[Polygon, tuple[Polygon, ...]]:
    """Contorno e furos girados JUNTOS e normalizados pelo bbox do CONTORNO —
    a mesma regra da reconstrucao da Fase 4 (placed_cut_contours). Girar o
    furo pelo proprio centro, ou normaliza-lo pelo proprio bbox, o descolaria
    da letra. O contorno devolvido e identico ao _normalized(contour.rotated())
    de antes (o centro padrao do rotated ja e o centroide do contorno)."""
    center = shape.contour.centroid
    outer = shape.contour.rotated(rotation, around=center)
    bb = outer.bounding_box
    dx, dy = -bb.min_x, -bb.min_y
    holes = tuple(h.rotated(rotation, around=center).translated(dx, dy) for h in shape.holes)
    return outer.translated(dx, dy), holes


def _subtract(
    region: Sequence[Sequence[tuple[int, int]]],
    clips: Sequence[Sequence[Sequence[tuple[int, int]]]],
) -> list[list[tuple[int, int]]]:
    """Regiao (caminhos do clipper) menos cada grupo de caminhos de 'clips'.

    EVENODD nos dois lados: aneis aninhados (furos do NFP / ilhas da regiao)
    contam certo sem depender da orientacao que o clipper deu.
    """
    current = list(region)
    for clip in clips:
        if not current:
            return []
        pc = pyclipper.Pyclipper()
        pc.AddPaths(current, pyclipper.PT_SUBJECT, True)
        pc.AddPaths(list(clip), pyclipper.PT_CLIP, True)
        current = pc.Execute(
            pyclipper.CT_DIFFERENCE, pyclipper.PFT_EVENODD, pyclipper.PFT_EVENODD
        )
    return current


def _place_nfp(
    order: Sequence[NestingShape],
    rotations_choice: Sequence[float | tuple[float, ...]],
    material: Material,
    sheet_h: float,
    nfp_cache: dict[tuple[str, float, str, float], tuple[Polygon, ...]] | None = None,
    deadline: float | None = None,
    inside_check: bool = False,
    ifp_cache: dict[tuple[str, float, int, str, float], tuple[Polygon, ...]] | None = None,
    prefer_holes: bool = False,
) -> list[_Placement] | None:
    """Posicionador NFP bottom-left: para cada peca (na ordem e rotacao dadas)
    a regiao valida da referencia = IFP - uniao dos NFPs das pecas ja postas.

    Cada entrada de 'rotations_choice' pode ser UM angulo (comportamento do
    GA: rotacao fixa pelo gene) ou uma TUPLA de candidatos: a peca testa
    todos e fica com o ponto mais baixo (min y, depois x) — a busca de
    rotacao por peca do bottom-left-fill classico (SVGnest/eCut), que
    entrelaca pecas irregulares. 'deadline' (time.monotonic) aborta a
    passada devolvendo None — busca com candidatos custa |rotacoes| vezes
    mais e nao pode passar por cima do orcamento do chamador.

    Regra de Ouro n.2 ATRAVES de posicionamentos: _nfp(p, peca) e RELATIVO
    (p na origem); antes de subtrair, cada anel e transladado para a POSICAO
    REAL de p na chapa. A referencia escolhida e o vertice da regiao que
    minimiza (y, x) — empacota para baixo, depois para a esquerda.

    Guarda anti-arredondamento: vertices criados pela DIFERENCA (interseccao
    IFP x NFP em arestas diagonais) sao arredondados pelo clipper em ate 1
    unidade (1e-4 mm), o que numa aresta longa ja rende area de sobreposicao
    acima de _AREA_EPS. Cada candidato e confirmado com o oraculo antes de
    fixar; com NFP correto o primeiro candidato passa quase sempre.

    nfp_cache (2D): dict {(id_a, rot_a, id_b, rot_b): nfp} preenchido sob
    demanda — o GA passa o MESMO dict em todas as avaliacoes e o NFP de cada
    par (forma, rotacao) e computado uma unica vez. Precondicoes do cache:
    artwork_id identifica o contorno (mesmo id => mesmo contorno) e o dict
    nao pode ser reaproveitado entre materiais (o NFP embute o gap). None =
    sem cache (comportamento 2C).

    inside_check (Fase 6, "Allow inside"): cada FURO de peca ja posta vira um
    segundo container. A regiao valida passa a ser a UNIAO de
      (IFP da chapa - NFPs de todas as postas)
    com, para cada furo de cada posta,
      (IFP do furo - NFPs das outras postas, exceto o proprio hospedeiro).
    O hospedeiro fica de fora dessa subtracao de proposito: o NFP dele e
    calculado sobre o contorno EXTERNO (o motor nao conhece furo), entao
    apagaria justamente o vao que estamos tentando usar. Quem garante que a
    peca nao vaza para a parede e a contencao do proprio IFP do furo, e o
    oraculo confere no fim com os furos descontados.

    prefer_holes escolhe QUAL das duas regras de desempate vale, e as duas
    ganham em cenarios diferentes (por isso quem decide e o GA, ver
    _optimize_ga):
    - False: menor (y, x) GLOBAL, chapa e furo disputando igual. O furo so
      vence quando esta mais baixo que a sobra de chapa — o caso da chapa
      apertada. Em chapa folgada o resultado empata com o motor sem
      inside_check, o que torna esta a opcao que nunca piora.
    - True: FURO ANTES DE CHAPA, depois (y, x). Enche o vao mesmo com chapa
      livre embaixo. Ganha quando ha peca pequena e vao grande; perde quando
      tira as pecas pequenas da frente do bottom-left e as grandes se
      entrelacam pior (medido em 21/07: 50,5% -> 47,2% num lote misto de
      letras, e o inverso em aneis com miolo grande).

    ifp_cache: {(host_id, host_rot, indice_do_furo, id_b, rot_b): aneis},
    mesmas precondicoes do nfp_cache (o IFP tambem embute o gap).
    """
    gap = max(0.0, material.spacing)
    margin = material.margin
    sheet_w = material.width
    placements: list[_Placement] = []
    # material posicionado de cada peca posta (contorno inflado - furos
    # encolhidos), em caminhos do clipper: e contra isto que o oraculo testa.
    placed_mat: list[list[list[tuple[int, int]]]] = []
    # (posicao, contorno+gap/2 na origem, artwork_id, rotacao, furos na origem)
    placed_off: list[tuple[Point2D, Polygon, str, float, tuple[Polygon, ...]]] = []

    def hole_ifp(
        host_id: str,
        host_rot: float,
        index: int,
        hole: Polygon,
        piece_id: str,
        rotation: float,
        piece_off: Polygon,
    ) -> tuple[Polygon, ...]:
        """_ifp_hole com cache, ja com o furo encolhido em gap/2."""
        key = (host_id, host_rot, index, piece_id, rotation)
        if ifp_cache is not None and key in ifp_cache:
            return ifp_cache[key]
        small = _shrunk(hole, gap / 2)
        rings = () if small is None else _ifp_hole(small, piece_off)
        if ifp_cache is not None:
            ifp_cache[key] = rings
        return rings

    def best_spot(
        shape: NestingShape, rotation: float
    ):
        """Melhor referencia para a peca NESTA rotacao, ou None se nao couber.
        Devolve (chave de ordem, ref, contorno posicionado, contorno+gap/2,
        furos na origem, material posicionado em caminhos do clipper). A chave
        e (rank, y, x) — e ela, nao so o (y, x), que decide entre as rotacoes,
        senao a preferencia por furo se perderia na comparacao."""
        norm, norm_holes = _rotated_parts(shape, rotation)
        ifp = _ifp_rect(norm, sheet_w, sheet_h, margin)
        if ifp is None:
            return None
        norm_off = _offset(norm, gap / 2)
        # NFP de cada peca posta contra esta peca, ja transladado para a chapa.
        nfp_paths: list[list[list[tuple[int, int]]]] = []
        for pos, other_off, other_id, other_rot, _ in placed_off:
            if nfp_cache is None:
                nfp = _nfp(other_off, norm_off)
            else:
                key = (other_id, other_rot, shape.artwork_id, rotation)
                nfp = nfp_cache.get(key)
                if nfp is None:
                    nfp = nfp_cache[key] = _nfp(other_off, norm_off)
            nfp_paths.append([_to_clipper(ring.translated(pos.x, pos.y)) for ring in nfp])

        # rank: 0 = furo, 1 = chapa livre quando prefer_holes; sem preferencia
        # os dois entram como 0 e a ordenacao vira o (y, x) puro de sempre.
        livre = _subtract([_to_clipper(ifp)], nfp_paths)
        candidates = {(1 if prefer_holes else 0, y, x) for path in livre for x, y in path}
        if inside_check:
            for k, (pos, _, other_id, other_rot, other_holes) in enumerate(placed_off):
                outros = [p for j, p in enumerate(nfp_paths) if j != k]
                for index, hole in enumerate(other_holes):
                    rings = hole_ifp(
                        other_id, other_rot, index, hole, shape.artwork_id, rotation, norm_off
                    )
                    if not rings:
                        continue
                    dentro = [_to_clipper(r.translated(pos.x, pos.y)) for r in rings]
                    candidates |= {
                        (0, y, x) for path in _subtract(dentro, outros) for x, y in path
                    }
        if not candidates:
            return None

        # MATERIAL da peca (contorno inflado + furos encolhidos) montado UMA
        # vez por rotacao, na origem: o contorno inflado ja e o norm_off e o
        # encolhimento do furo nao depende da posicao, so a translacao muda.
        # Antes cada candidato refazia dois offsets de clipper por peca ja
        # posta — o custo dominante da passada.
        mine_base = [norm_off]
        if inside_check:
            mine_base += [s for s in (_shrunk(h, gap / 2) for h in norm_holes) if s is not None]
        for rank, y_int, x_int in sorted(candidates):
            ref = Point2D(x_int / _SCALE, y_int / _SCALE)
            poly = norm.translated(ref.x, ref.y)
            if not _inside_sheet(poly, sheet_w, sheet_h, margin):
                continue
            mine = [_to_clipper(p.translated(ref.x, ref.y)) for p in mine_base]
            if all(not _overlaps_paths(mine, other) for other in placed_mat):
                return (rank, ref.y, ref.x), ref, poly, norm_off, norm_holes, mine
        return None

    for shape, rot_spec in zip(order, rotations_choice, strict=True):
        if deadline is not None and time.monotonic() >= deadline:
            return None  # busca abortada: o chamador fica com o que ja tinha
        chosen = None
        for rotation in rot_spec if isinstance(rot_spec, tuple) else (rot_spec,):
            spot = best_spot(shape, rotation)
            if spot is not None and (chosen is None or spot[0] < chosen[1][0]):
                chosen = (rotation, spot)
        if chosen is None:
            continue  # nao coube nesta chapa; fica de fora (chamador compara contagens)
        rotation, (_, ref, _, norm_off, norm_holes, mine) = chosen
        placements.append(_Placement(shape.artwork_id, ref, rotation))
        placed_mat.append(mine)
        placed_off.append((ref, norm_off, shape.artwork_id, rotation, norm_holes))
    return placements


# --- 2D: rotacao + algoritmo genetico -----------------------------------------


def _placed_contour(shape: NestingShape, placement: _Placement) -> Polygon:
    """Contorno REAL da peca posicionada: rotacao do gene aplicada e a
    referencia (bbox.min do contorno JA girado) em placement.position."""
    return _normalized(shape.contour.rotated(placement.rotation)).translated(
        placement.position.x, placement.position.y
    )


def _order_crossover(
    rng: random.Random, pa: tuple[int, ...], pb: tuple[int, ...]
) -> tuple[int, ...]:
    """Order Crossover (OX): copia um segmento contiguo de A e completa as
    posicoes restantes com os genes que faltam, na ordem em que aparecem em B
    a partir do fim do segmento (com wrap). Sempre permutacao valida."""
    n = len(pa)
    if n < 2:
        return pa
    i, j = sorted(rng.sample(range(n), 2))
    seg = set(pa[i : j + 1])
    child: list[int] = list(pa)
    fill = [g for g in pb[j + 1 :] + pb[: j + 1] if g not in seg]
    positions = list(range(j + 1, n)) + list(range(i))
    for pos, g in zip(positions, fill, strict=True):
        child[pos] = g
    return tuple(child)


def _mutated(
    rng: random.Random,
    gene: tuple[tuple[int, ...], tuple[float, ...], bool],
    shapes: Sequence[NestingShape],
    prob: float,
    inside_check: bool = False,
) -> tuple[tuple[int, ...], tuple[float, ...], bool]:
    """Com probabilidade 'prob': troca duas pecas de posicao OU (50/50) muda a
    rotacao de uma peca para outra permitida por ela; e, so com inside_check,
    vira o bit de preferencia por furo em 1 de cada 4 mutacoes.

    O sorteio do bit fica no FIM e so acontece com inside_check ligado: assim
    a sequencia do rng com a caixa desligada e a mesma de antes da Fase 6 e o
    motor antigo continua bit a bit identico.
    """
    if rng.random() >= prob:
        return gene
    order, rot, prefer = list(gene[0]), list(gene[1]), gene[2]
    if rng.random() < 0.5 and len(order) >= 2:
        a, b = rng.sample(range(len(order)), 2)
        order[a], order[b] = order[b], order[a]
    else:
        k = rng.randrange(len(rot))
        rot[k] = rng.choice(shapes[k].rotations)
    if inside_check and rng.random() < 0.25:
        prefer = not prefer
    return tuple(order), tuple(rot), prefer


def _optimize_ga(
    shapes: Sequence[NestingShape],
    material: Material,
    sheet_h: float,
    *,
    seed: int,
    genetics_time: float | None = None,
    generations: int = 30,
    population_size: int = 16,
    tournament_k: int = 3,
    mutation_prob: float = 0.5,
    inside_check: bool = False,
) -> list[_Placement]:
    """Algoritmo genetico sobre (ordem, rotacoes, preferencia), avaliado com
    _place_nfp.

    Cromossomo: gene = (order, rot, prefer) — 'order' e permutacao dos indices
    de 'shapes'; rot[k] e a rotacao da peca k (independe da posicao na ordem)
    e sempre pertence a shapes[k].rotations.

    'prefer' (Fase 6) e o bit que escolhe a regra de desempate do bottom-left:
    encher furo antes de usar chapa livre, ou disputar pelo (y, x) puro. As
    duas ganham em cenarios opostos e nenhuma ganha sempre — entao quem decide
    e a BUSCA, nao uma regra fixa minha. Com inside_check desligado o bit fica
    preso em False e nenhum sorteio o toca, entao o motor da Fase 2 continua
    identico.

    O que o elitismo garante (e o que NAO garante): as sementes SEM
    preferencia sao avaliadas primeiro, entao o resultado nunca fica pior que
    o chute bottom-left de sempre. Nao garante empatar com a caixa desligada
    em qualquer lote — a populacao muda, o passeio aleatorio muda junto, e a
    diferenca fica no nivel do ruido (medido em 21/07: 49,33% x 49,54% em
    letras mistas, contra 46,10% quando a preferencia era regra fixa).

    Fitness (menor = melhor) = CHAPA CONSUMIDA (comprimento ocupado x largura
    da chapa) + _UNPLACED_PENALTY por peca nao colocada — nao a area do
    bounding box, ver o comentario em evaluate(). Cache de fitness por gene (dict;
    gene identico nunca e reavaliado) e cache de NFP por (forma, rotacao)
    compartilhado por TODAS as avaliacoes — _nfp nunca roda duas vezes para o
    mesmo par dentro do GA.

    GA: semente = ordem por area decrescente + rotacao 0 (o chute da 2C, que
    o elitismo garante nunca piorar), selecao por torneio, Order Crossover na
    ordem + crossover uniforme nas rotacoes, mutacao (troca de posicoes ou de
    rotacao), elitismo do melhor.

    Parada: 'genetics_time' segundos (time.monotonic, checado tambem entre
    avaliacoes — retorna o melhor ate entao) ou, se None, 'generations' fixas.
    DETERMINISMO: toda aleatoriedade vem de random.Random(seed) local; com
    genetics_time=None, mesmo seed => mesmo resultado, sempre.
    """
    n = len(shapes)
    if n == 0:
        return []
    rng = random.Random(seed)
    shapes = list(shapes)
    shape_by_id = {s.artwork_id: s for s in shapes}
    nfp_cache: dict[tuple[str, float, str, float], tuple[Polygon, ...]] = {}
    # IFP de furo (Fase 6): mesmo regime do nfp_cache — compartilhado por TODAS
    # as avaliacoes, cada (furo x peca x rotacoes) erodido uma unica vez.
    ifp_cache: dict[tuple[str, float, int, str, float], tuple[Polygon, ...]] = {}
    fitness_cache: dict[
        tuple[tuple[int, ...], tuple[float, ...], bool],
        tuple[tuple[float, float], list[_Placement]],
    ] = {}
    start = time.monotonic()

    def out_of_time() -> bool:
        return genetics_time is not None and time.monotonic() - start >= genetics_time

    def evaluate(
        gene: tuple[tuple[int, ...], tuple[float, ...], bool],
    ) -> tuple[tuple[float, float], list[_Placement]]:
        cached = fitness_cache.get(gene)
        if cached is not None:
            return cached
        order_idx, rot, prefer = gene
        order = [shapes[i] for i in order_idx]
        rot_seq = [rot[i] for i in order_idx]
        placements = _place_nfp(
            order,
            rot_seq,
            material,
            sheet_h,
            nfp_cache=nfp_cache,
            inside_check=inside_check,
            ifp_cache=ifp_cache,
            prefer_holes=prefer,
        )
        # CUSTO LEXICOGRAFICO: (chapa consumida, compacidade do bloco).
        #
        # 1) CHAPA CONSUMIDA = comprimento ocupado x largura da chapa. Era a
        #    area do bounding box sozinha ate 21/07 e estava errado: a largura
        #    da chapa e FIXA, entao estreitar o bloco nao devolve material —
        #    so encurta-lo devolve. A Fase 6 explodiu isso: encher o furo
        #    estreitava o bloco (292x242) e o GA preferia esse layout a um mais
        #    curto (368x200), gastando 42mm A MAIS de chapa.
        # 2) COMPACIDADE (area do bbox) entra so como DESEMPATE. Sem ela o
        #    custo vira um plato: duas pecas que cabem na mesma linha custam
        #    igual entrelacadas ou lado a lado, e o GA perde o incentivo de
        #    entrelacar — que e o que faz caber mais peca por linha (e, ai sim,
        #    encurtar a chapa). Foi o test_ga_rotacao_melhora_o_encaixe que
        #    pegou isso.
        # Ver docs/produto/FASE6-PRENCHER-FUROS.md secao 4.
        comprimento = compacidade = 0.0
        if placements:
            polys = [_placed_contour(shape_by_id[p.artwork_id], p) for p in placements]
            min_x = min(p.bounding_box.min_x for p in polys)
            min_y = min(p.bounding_box.min_y for p in polys)
            max_x = max(p.bounding_box.max_x for p in polys)
            max_y = max(p.bounding_box.max_y for p in polys)
            comprimento = (max_y - min_y) * material.width
            compacidade = (max_x - min_x) * (max_y - min_y)
        faltando = _UNPLACED_PENALTY * (n - len(placements))
        result = ((comprimento + faltando, compacidade + faltando), placements)
        fitness_cache[gene] = result
        return result

    best_gene: tuple[tuple[int, ...], tuple[float, ...], bool] | None = None
    _PIOR = (float("inf"), float("inf"))  # custo lexicografico "infinito"
    best: tuple[tuple[float, float], list[_Placement]] = (_PIOR, [])

    def consider(gene: tuple[tuple[int, ...], tuple[float, ...], bool]) -> None:
        nonlocal best_gene, best
        result = evaluate(gene)
        if result[0] < best[0]:
            best_gene, best = gene, result

    def pick(population: list) -> tuple[tuple[int, ...], tuple[float, ...], bool]:
        disputa = rng.sample(population, min(tournament_k, len(population)))
        return min(disputa, key=lambda g: fitness_cache.get(g, (_PIOR, []))[0])

    # populacao inicial: semente 2C + semente "deitada" + individuos aleatorios
    seeded = (
        tuple(sorted(range(n), key=lambda i: shapes[i].contour.area, reverse=True)),
        tuple(0.0 if 0.0 in s.rotations else s.rotations[0] for s in shapes),
        False,
    )

    def _rot_deitada(shape: NestingShape) -> float:
        """Rotacao permitida que deixa o bbox girado mais BAIXO (deita a
        peca). Empate fica com a primeira da tupla (deterministico)."""
        return min(shape.rotations, key=lambda r: shape.contour.rotated(r).bounding_box.height)

    # Em pecas mais altas que largas (letras), deitar encurta as linhas do
    # bottom-left. Sem esta semente, girar dependia de mutacao peca a peca —
    # com dezenas de pecas o orcamento de tempo acabava antes de qualquer
    # rotacao aparecer no resultado (caso real de 21/07, 44 letras).
    seeded_deitada = (seeded[0], tuple(_rot_deitada(s) for s in shapes), False)
    population = [seeded, seeded_deitada]
    # Sementes 'enche o furo' (Fase 6): as MESMAS duas com o bit ligado, logo
    # atras das originais. Entram cedo para o elitismo poder compara-las, mas
    # DEPOIS das duas obrigatorias — assim, se o orcamento estourar, o que
    # sobra e o resultado do motor de sempre.
    if inside_check and any(s.holes for s in shapes):
        population += [(seeded[0], seeded[1], True), (seeded_deitada[0], seeded_deitada[1], True)]
    while len(population) < population_size:
        population.append((
            tuple(rng.sample(range(n), n)),
            tuple(rng.choice(s.rotations) for s in shapes),
            bool(rng.getrandbits(1)) if inside_check else False,
        ))
    for i, gene in enumerate(population):
        # As DUAS sementes sempre avaliam — sao o minimo util da busca. Sem
        # isso, num trabalho pesado o orcamento estoura na 1a avaliacao e a
        # semente deitada (a unica que gira as pecas nesse cenario) nunca
        # entra: resultado voltava 100% em pe (caso real de 21/07, 44 letras
        # de PDF). O 'Tempo de otimizacao' vale do 3o individuo em diante.
        if i >= 2 and best_gene is not None and out_of_time():
            return list(best[1])
        consider(gene)

    # semente 3, estilo eCut/SVGnest: bottom-left com busca de rotacao POR
    # PECA (cada uma testa todas as rotacoes permitidas e fica com o ponto
    # mais baixo) — e o que entrelaca formas irregulares. Custa |rotacoes|
    # vezes uma avaliacao, entao respeita o relogio: estourou no meio, vale
    # o melhor das sementes anteriores.
    if any(len(s.rotations) > 1 for s in shapes) and not out_of_time():
        order_shapes = [shapes[i] for i in seeded[0]]
        greedy = _place_nfp(
            order_shapes,
            [tuple(s.rotations) for s in order_shapes],
            material,
            sheet_h,
            nfp_cache=nfp_cache,
            deadline=None if genetics_time is None else start + genetics_time,
            inside_check=inside_check,
            ifp_cache=ifp_cache,
        )
        if greedy:
            rot = list(seeded[1])
            pi = 0
            for oi in seeded[0]:
                if pi < len(greedy) and greedy[pi].artwork_id == shapes[oi].artwork_id:
                    rot[oi] = greedy[pi].rotation
                    pi += 1
            consider((seeded[0], tuple(rot), False))

    gen = 0
    while not out_of_time() and (genetics_time is not None or gen < generations):
        next_pop = [best_gene]  # elitismo: o melhor sobrevive intacto
        while len(next_pop) < population_size:
            pa, pb = pick(population), pick(population)
            child_order = _order_crossover(rng, pa[0], pb[0])
            child_rot = tuple(
                ra if rng.random() < 0.5 else rb for ra, rb in zip(pa[1], pb[1], strict=True)
            )
            # o bit de furo tambem cruza; sem inside_check nao ha sorteio
            # (a sequencia do rng fica identica a de antes da Fase 6).
            child_prefer = (pa[2] if rng.random() < 0.5 else pb[2]) if inside_check else False
            next_pop.append(
                _mutated(
                    rng, (child_order, child_rot, child_prefer), shapes, mutation_prob, inside_check
                )
            )
        for gene in next_pop:
            if out_of_time():
                break
            consider(gene)
        population = next_pop
        gen += 1
    return list(best[1])


# --- 2E: interface publica + reconciliacao com o enum Rotation -----------------


def _simplified(contour: Polygon, tolerance: float) -> Polygon:
    """Simplifica o contorno ate 'tolerance' mm (Approximation_CB do eCut):
    CleanPolygon do clipper remove vertices redundantes/quase-colineares.
    Menos vertices = NFP muito mais rapido.

    Guardas anti-destruicao de peca pequena: devolve o ORIGINAL se a
    simplificacao deixar menos de 3 vertices ou alterar a area em mais de 10%
    (peca menor que a tolerancia colapsaria em nada).
    """
    if tolerance <= 0 or len(contour.vertices) <= 4 or contour.area <= _AREA_EPS:
        return contour
    cleaned = pyclipper.CleanPolygon(_to_clipper(contour), tolerance * _SCALE)
    if len(cleaned) < 3:
        return contour
    poly = _from_clipper(cleaned)
    if abs(poly.area - contour.area) > 0.1 * contour.area:
        return contour
    return poly


def _to_rotation(angle: float) -> Rotation | float:
    """Rotacao float do gene -> enum Rotation quando cai nos 90 em 90 (os
    consumidores de impressao comparam com o enum), senao o PROPRIO angulo
    em graus (giro fino do Modo Corte, estilo 'Fix angle' do eCut). A
    reconstrucao da Fase 4 usa float(rotation), entao tanto faz o tipo."""
    value = angle % 360
    if abs(value - round(value)) < 1e-9 and int(round(value)) % 90 == 0:
        return Rotation(int(round(value)) % 360)
    return value


class TrueShapePacker:
    """Interface publica do nesting true-shape (fecha a Fase 2).

    Entrada = NestingShape (contorno real + rotacoes permitidas), NAO
    NestingPiece — nao e drop-in do GridPacker/MaxRectsPacker. A SAIDA
    (Layout/PlacedItem) e identica, entao pluga no mesmo pipeline de
    desenho/exportacao (Rotation e IntEnum: project_io ja serializa como int).

    gap/margin sao parametros do PACKER (Distance/Margin do dialogo de
    nesting, estilo eCut), nao do material: internamente monta um material
    efetivo com esses valores; o Layout devolvido carrega o material ORIGINAL.

    CONVENCAO DE RECONSTRUCAO (a Fase 4 depende disto): PlacedItem.position =
    onde o canto minimo do bounding box do contorno JA GIRADO cai na chapa.
    Para reconstruir a peca: girar o contorno original por PlacedItem.rotation
    (graus, qualquer centro), NORMALIZAR (bbox.min na origem) e transladar
    para position. Packer e Fase 4 usam a MESMA referencia (bbox.min) —
    mudar um lado sem o outro desloca a peca exportada.
    """

    def __init__(
        self,
        *,
        gap: float = 0.0,
        margin: float = 0.0,
        genetics_time: float = 10.0,
        generations: int | None = None,
        seed: int = 0,
        approximation: float = 0.1,
        inside_check: bool = False,
    ) -> None:
        # inside_check (Fase 6, "Allow inside"): peca pequena pode ocupar o
        # FURO de outra ja posta. Desligado = motor da Fase 2 sem alteracao
        # nenhuma (os furos voltam a so viajar ate a exportacao).
        self._inside_check = inside_check
        self._gap = gap
        self._margin = margin
        self._genetics_time = genetics_time
        # generations definido => modo deterministico (testes); ignora o tempo.
        self._generations = generations
        self._seed = seed
        self._approximation = approximation

    # -- publica ---------------------------------------------------------------

    def pack(self, shapes: Sequence[NestingShape], material: Material) -> Layout:
        """Chapa aberta: altura generosa (soma dos MAIORES lados — com rotacao
        uma peca deitada pode ficar de pe) e used_length pelo conteudo."""
        prepared = self._prepared(shapes)
        mat = self._effective_material(material)
        # teto por peca = diagonal do bbox: com giro LIVRE (45 graus etc.) o
        # bbox girado passa do maior lado e chega na hipotenusa.
        alturas = (
            math.hypot(s.contour.bounding_box.width, s.contour.bounding_box.height)
            for s in prepared
        )
        sheet_h = 2 * self._margin + sum(a + max(0.0, self._gap) for a in alturas) + 1.0
        placements = self._optimized(prepared, mat, max(sheet_h, 1.0))
        items, used_length = self._to_items(prepared, placements)
        return Layout(material=material, items=tuple(items), used_length=used_length)

    def pack_sheets(
        self,
        shapes: Sequence[NestingShape],
        material: Material,
        sheet_length: float,
    ) -> list[Layout]:
        """Enche chapas de altura fixa: nesta cada chapa com as pecas que
        restam, remove as colocadas e repete. sheet_length <= 0 = chapa aberta."""
        if sheet_length <= 0:
            return [self.pack(shapes, material)]
        remaining = self._prepared(shapes)
        mat = self._effective_material(material)
        sheets: list[Layout] = []
        # trava de seguranca: nunca mais voltas que pecas (evita loop infinito).
        for _ in range(len(remaining) + 1):
            if not remaining:
                break
            placements = self._optimized(remaining, mat, sheet_length)
            if not placements:
                # nenhuma peca coube numa chapa VAZIA (peca maior que a chapa):
                # coloca a primeira assim mesmo (convencao do MaxRects) e segue.
                big = remaining[0]
                item = PlacedItem(big.artwork_id, Point2D(self._margin, self._margin))
                sheets.append(Layout(material, (item,), sheet_length))
                remaining = remaining[1:]
                continue
            items, _ = self._to_items(remaining, placements)
            sheets.append(Layout(material, tuple(items), sheet_length))
            # remove as colocadas por MULTISET de id: copias com o mesmo id tem
            # o mesmo contorno (precondicao do cache), tanto faz qual sai.
            placed = Counter(p.artwork_id for p in placements)
            leftover = []
            for s in remaining:
                if placed.get(s.artwork_id, 0) > 0:
                    placed[s.artwork_id] -= 1
                else:
                    leftover.append(s)
            remaining = leftover
        return sheets

    # -- internas ----------------------------------------------------------------

    def _prepared(self, shapes: Sequence[NestingShape]) -> list[NestingShape]:
        return [
            # Furos passam INTACTOS de proposito, mesmo com inside_check: a
            # simplificacao tolera ate 10% de variacao de area e um furo
            # simplificado para FORA faria a peca hospedada encostar na parede
            # real. Custa NFP/IFP mais lento, e o preco de nao arriscar corte.
            NestingShape(
                s.artwork_id, _simplified(s.contour, self._approximation), s.rotations, s.holes
            )
            for s in shapes
        ]

    def _effective_material(self, material: Material) -> Material:
        """Material com o gap/margin DO PACKER (o motor 2A-2D le de la)."""
        return replace(material, spacing=self._gap, margin=self._margin)

    def _optimized(
        self, shapes: Sequence[NestingShape], material: Material, sheet_h: float
    ) -> list[_Placement]:
        if self._generations is not None:
            return _optimize_ga(
                shapes,
                material,
                sheet_h,
                seed=self._seed,
                generations=self._generations,
                inside_check=self._inside_check,
            )
        return _optimize_ga(
            shapes,
            material,
            sheet_h,
            seed=self._seed,
            genetics_time=self._genetics_time,
            inside_check=self._inside_check,
        )

    def _to_items(
        self, shapes: Sequence[NestingShape], placements: Sequence[_Placement]
    ) -> tuple[list[PlacedItem], float]:
        """_Placement (rotacao float) -> PlacedItem (enum) + used_length.

        used_length no espirito do MaxRects (fundo do conteudo + margens): as
        posicoes aqui ja sao absolutas (margem inclusa), entao e o maior
        bbox.max_y das pecas colocadas + a margem de baixo.
        """
        by_id = {s.artwork_id: s for s in shapes}
        items: list[PlacedItem] = []
        bottom = 0.0
        for p in placements:
            items.append(PlacedItem(p.artwork_id, p.position, _to_rotation(p.rotation)))
            bottom = max(bottom, _placed_contour(by_id[p.artwork_id], p).bounding_box.max_y)
        used_length = (bottom + self._margin) if items else 0.0
        return items, used_length
