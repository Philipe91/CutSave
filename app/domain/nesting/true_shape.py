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
  laco do GA —, fitness = area do bounding box + penalidade alta por peca de
  fora. Deterministico por seed (random.Random local, nada de random global).
- 2E: interface publica TrueShapePacker (pack/pack_sheets -> Layout) +
  reconciliacao com o enum Rotation + simplificacao de contorno
  (approximation, estilo Approximation_CB do eCut).

Convencoes criticas (nao mudar sem revalidar contra o oraculo):
- ESCALA INTEIRA: pyclipper opera em ints. Toda geometria em mm passa por
  _to_clipper (x SCALE) antes e _from_clipper (/ SCALE) depois.
- PONTO DE REFERENCIA: canto inferior-esquerdo do bounding box da peca.
  'position' de uma peca = onde esse canto cai na chapa. NFP e IFP usam a
  MESMA referencia.
"""

from __future__ import annotations

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
from app.shared.errors import ValidationError

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
    # Furos (letra "O"): o motor de nesting usa SO o contour externo — furos
    # nao afetam o empacotamento (inside_check e fase futura). Sao carregados
    # para a Fase 4 exportar o corte interno com o MESMO transform do outer.
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


# --- oraculo 2A: testes diretos, sem NFP -------------------------------------


def _overlaps(poly_a: Polygon, poly_b: Polygon, gap: float = 0.0) -> bool:
    """True se as pecas ficam mais proximas que 'gap' (folga total entre elas).

    Cada peca e inflada em gap/2; sobreposicao das versoes infladas = distancia
    real < gap. Borda ENCOSTADA e permitida: interseccao de area ~0 nao conta.
    """
    a = _offset(poly_a, gap / 2)
    b = _offset(poly_b, gap / 2)
    pc = pyclipper.Pyclipper()
    pc.AddPath(_to_clipper(a), pyclipper.PT_SUBJECT, True)
    pc.AddPath(_to_clipper(b), pyclipper.PT_CLIP, True)
    inter = pc.Execute(pyclipper.CT_INTERSECTION, pyclipper.PFT_NONZERO, pyclipper.PFT_NONZERO)
    area_mm2 = sum(abs(pyclipper.Area(p)) for p in inter) / (_SCALE * _SCALE)
    return area_mm2 > _AREA_EPS


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


def _place_nfp(
    order: Sequence[NestingShape],
    rotations_choice: Sequence[float],
    material: Material,
    sheet_h: float,
    nfp_cache: dict[tuple[str, float, str, float], tuple[Polygon, ...]] | None = None,
) -> list[_Placement]:
    """Posicionador NFP bottom-left: para cada peca (na ordem e rotacao dadas)
    a regiao valida da referencia = IFP - uniao dos NFPs das pecas ja postas.

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
    """
    gap = max(0.0, material.spacing)
    margin = material.margin
    sheet_w = material.width
    placements: list[_Placement] = []
    placed_raw: list[Polygon] = []   # contorno real posicionado
    # (posicao, contorno+gap/2 na origem, artwork_id, rotacao) das pecas postas
    placed_off: list[tuple[Point2D, Polygon, str, float]] = []
    for shape, rotation in zip(order, rotations_choice, strict=True):
        norm = _normalized(shape.contour.rotated(rotation))
        ifp = _ifp_rect(norm, sheet_w, sheet_h, margin)
        if ifp is None:
            continue
        norm_off = _offset(norm, gap / 2)
        region = [_to_clipper(ifp)]
        for pos, other_off, other_id, other_rot in placed_off:
            if nfp_cache is None:
                nfp = _nfp(other_off, norm_off)
            else:
                key = (other_id, other_rot, shape.artwork_id, rotation)
                nfp = nfp_cache.get(key)
                if nfp is None:
                    nfp = nfp_cache[key] = _nfp(other_off, norm_off)
            nfp_pos = [_to_clipper(ring.translated(pos.x, pos.y)) for ring in nfp]
            pc = pyclipper.Pyclipper()
            pc.AddPaths(region, pyclipper.PT_SUBJECT, True)
            pc.AddPaths(nfp_pos, pyclipper.PT_CLIP, True)
            # EVENODD nos dois lados: aneis aninhados (furos do NFP / ilhas da
            # regiao) contam certo sem depender da orientacao que o clipper deu.
            region = pc.Execute(
                pyclipper.CT_DIFFERENCE, pyclipper.PFT_EVENODD, pyclipper.PFT_EVENODD
            )
            if not region:
                break
        if not region:
            continue  # nao coube nesta chapa; fica de fora (chamador compara contagens)
        candidates = sorted({(y, x) for path in region for x, y in path})
        chosen: tuple[Point2D, Polygon] | None = None
        for y_int, x_int in candidates:
            ref = Point2D(x_int / _SCALE, y_int / _SCALE)
            poly = norm.translated(ref.x, ref.y)
            if _inside_sheet(poly, sheet_w, sheet_h, margin) and all(
                not _overlaps(poly, other, gap) for other in placed_raw
            ):
                chosen = (ref, poly)
                break
        if chosen is None:
            continue
        ref, poly = chosen
        placements.append(_Placement(shape.artwork_id, ref, rotation))
        placed_raw.append(poly)
        placed_off.append((ref, norm_off, shape.artwork_id, rotation))
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
    gene: tuple[tuple[int, ...], tuple[float, ...]],
    shapes: Sequence[NestingShape],
    prob: float,
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """Com probabilidade 'prob': troca duas pecas de posicao OU (50/50) muda a
    rotacao de uma peca para outra permitida por ela."""
    if rng.random() >= prob:
        return gene
    order, rot = list(gene[0]), list(gene[1])
    if rng.random() < 0.5 and len(order) >= 2:
        a, b = rng.sample(range(len(order)), 2)
        order[a], order[b] = order[b], order[a]
    else:
        k = rng.randrange(len(rot))
        rot[k] = rng.choice(shapes[k].rotations)
    return tuple(order), tuple(rot)


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
) -> list[_Placement]:
    """Algoritmo genetico sobre (ordem, rotacoes), avaliado com _place_nfp.

    Cromossomo: gene = (order, rot) — 'order' e permutacao dos indices de
    'shapes'; rot[k] e a rotacao da peca k (independe da posicao na ordem) e
    sempre pertence a shapes[k].rotations.

    Fitness (menor = melhor) = area do bounding box do layout +
    _UNPLACED_PENALTY por peca nao colocada. Cache de fitness por gene (dict;
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
    fitness_cache: dict[
        tuple[tuple[int, ...], tuple[float, ...]], tuple[float, list[_Placement]]
    ] = {}
    start = time.monotonic()

    def out_of_time() -> bool:
        return genetics_time is not None and time.monotonic() - start >= genetics_time

    def evaluate(gene: tuple[tuple[int, ...], tuple[float, ...]]) -> tuple[float, list[_Placement]]:
        cached = fitness_cache.get(gene)
        if cached is not None:
            return cached
        order_idx, rot = gene
        order = [shapes[i] for i in order_idx]
        rot_seq = [rot[i] for i in order_idx]
        placements = _place_nfp(order, rot_seq, material, sheet_h, nfp_cache=nfp_cache)
        area = 0.0
        if placements:
            polys = [_placed_contour(shape_by_id[p.artwork_id], p) for p in placements]
            min_x = min(p.bounding_box.min_x for p in polys)
            min_y = min(p.bounding_box.min_y for p in polys)
            max_x = max(p.bounding_box.max_x for p in polys)
            max_y = max(p.bounding_box.max_y for p in polys)
            area = (max_x - min_x) * (max_y - min_y)
        result = (area + _UNPLACED_PENALTY * (n - len(placements)), placements)
        fitness_cache[gene] = result
        return result

    best_gene: tuple[tuple[int, ...], tuple[float, ...]] | None = None
    best: tuple[float, list[_Placement]] = (float("inf"), [])

    def consider(gene: tuple[tuple[int, ...], tuple[float, ...]]) -> None:
        nonlocal best_gene, best
        result = evaluate(gene)
        if result[0] < best[0]:
            best_gene, best = gene, result

    def pick(population: list) -> tuple[tuple[int, ...], tuple[float, ...]]:
        disputa = rng.sample(population, min(tournament_k, len(population)))
        return min(disputa, key=lambda g: fitness_cache.get(g, (float("inf"), []))[0])

    # populacao inicial: semente 2C + individuos aleatorios
    seeded = (
        tuple(sorted(range(n), key=lambda i: shapes[i].contour.area, reverse=True)),
        tuple(0.0 if 0.0 in s.rotations else s.rotations[0] for s in shapes),
    )
    population = [seeded]
    while len(population) < population_size:
        population.append((
            tuple(rng.sample(range(n), n)),
            tuple(rng.choice(s.rotations) for s in shapes),
        ))
    for gene in population:
        if best_gene is not None and out_of_time():
            return list(best[1])
        consider(gene)

    gen = 0
    while not out_of_time() and (genetics_time is not None or gen < generations):
        next_pop = [best_gene]  # elitismo: o melhor sobrevive intacto
        while len(next_pop) < population_size:
            pa, pb = pick(population), pick(population)
            child_order = _order_crossover(rng, pa[0], pb[0])
            child_rot = tuple(
                ra if rng.random() < 0.5 else rb for ra, rb in zip(pa[1], pb[1], strict=True)
            )
            next_pop.append(_mutated(rng, (child_order, child_rot), shapes, mutation_prob))
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


def _to_rotation(angle: float) -> Rotation:
    """Rotacao float do gene -> enum Rotation. NestingShape.rotations e
    restrito a {0, 90, 180, 270}; cair fora daqui e bug do chamador, entao
    erro explicito em vez de arredondar em silencio."""
    value = int(round(angle)) % 360
    try:
        return Rotation(value)
    except ValueError as exc:
        raise ValidationError(
            f"Rotacao {angle} do nesting nao mapeia para o enum Rotation (0/90/180/270)."
        ) from exc


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
        if inside_check:
            raise NotImplementedError(
                "inside_check (nestar dentro dos vaos do container / "
                "Use_Last_As_Container) e fase futura do true-shape."
            )
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
        alturas = (
            max(s.contour.bounding_box.width, s.contour.bounding_box.height) for s in prepared
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
            # furos passam intactos: so o contorno externo entra no motor.
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
                shapes, material, sheet_h, seed=self._seed, generations=self._generations
            )
        return _optimize_ga(
            shapes, material, sheet_h, seed=self._seed, genetics_time=self._genetics_time
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
