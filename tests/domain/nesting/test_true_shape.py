"""Testes do nesting true-shape (Fase 2).

2A: o oraculo bruteforce e o gabarito de correcao — estes testes provam que
ele coloca pecas dentro da chapa sem sobreposicao. As sub-fases seguintes
(NFP, genetico) serao validadas CONTRA ele.
"""

import math
import random
import time

import pytest
from app.domain.geometry import Point2D
from app.domain.geometry.polygon import Polygon
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem, Rotation
from app.domain.nesting.true_shape import (
    _UNPLACED_PENALTY,
    NestingShape,
    TrueShapePacker,
    _contains,
    _ifp_hole,
    _ifp_rect,
    _inside_sheet,
    _nfp,
    _nfp_blocks,
    _normalized,
    _offset,
    _optimize_ga,
    _overlaps,
    _place_bruteforce,
    _place_nfp,
    _placed_contour,
    _rotated_parts,
    _shrunk,
    _simplified,
)


def _rect(w, h):
    return Polygon((Point2D(0, 0), Point2D(w, 0), Point2D(w, h), Point2D(0, h)))


def _tri(size):
    return Polygon((Point2D(0, 0), Point2D(size, 0), Point2D(0, size)))


def _placed_poly(shapes, placement):
    """Reconstroi o contorno posicionado (rotacao aplicada, ref em 'position')."""
    shape = next(s for s in shapes if s.artwork_id == placement.artwork_id)
    return _placed_contour(shape, placement)


def _sem_sobreposicao(shapes, placements, gap):
    polys = [_placed_poly(shapes, p) for p in placements]
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            if _overlaps(polys[i], polys[j], gap):
                return False
    return True


# --- 2A: oraculo -------------------------------------------------------------


def test_overlaps_detecta_sobreposicao_e_aceita_encostar():
    a = _rect(50, 50)
    assert _overlaps(a, a.translated(25, 25))          # sobrepoe de fato
    assert not _overlaps(a, a.translated(50, 0))       # encostado: permitido
    assert not _overlaps(a, a.translated(60, 0))       # separado
    assert _overlaps(a, a.translated(51, 0), gap=4.0)  # folga menor que o gap


def test_inside_sheet_respeita_margem():
    assert _inside_sheet(_rect(50, 50).translated(10, 10), 200, 200, margin=10)
    assert not _inside_sheet(_rect(50, 50).translated(5, 10), 200, 200, margin=10)
    assert not _inside_sheet(_rect(50, 50).translated(160, 10), 200, 200, margin=10)


def test_oraculo_dois_quadrados():
    shapes = [NestingShape("q1", _rect(50, 50)), NestingShape("q2", _rect(50, 50))]
    mat = Material("chapa", width=200, margin=0, spacing=0)
    placements = _place_bruteforce(shapes, mat, sheet_h=200)
    assert len(placements) == 2
    assert _sem_sobreposicao(shapes, placements, gap=0.0)


def test_oraculo_mix_sem_sobreposicao_e_dentro_da_chapa():
    shapes = [
        NestingShape("q1", _rect(60, 60)),
        NestingShape("r1", _rect(80, 30)),
        NestingShape("t1", _tri(50)),
        NestingShape("q2", _rect(40, 40).translated(300, 300)),  # origem nao importa
    ]
    mat = Material("chapa", width=200, margin=5, spacing=2)
    placements = _place_bruteforce(shapes, mat, sheet_h=200)
    assert len(placements) == 4  # tudo coube
    assert _sem_sobreposicao(shapes, placements, gap=2.0)
    for p in placements:
        assert _inside_sheet(_placed_poly(shapes, p), 200, 200, margin=5)


def test_oraculo_peca_grande_demais_fica_de_fora():
    shapes = [NestingShape("ok", _rect(50, 50)), NestingShape("gigante", _rect(500, 500))]
    mat = Material("chapa", width=200, margin=0, spacing=0)
    placements = _place_bruteforce(shapes, mat, sheet_h=200)
    assert [p.artwork_id for p in placements] == ["ok"]


# --- 2B: concordancia NFP x oraculo ------------------------------------------

_GAP = 3.0


def _ele(w=80, h=80, braco=30):
    """'L' concavo: braco horizontal e vertical de largura 'braco'."""
    return Polygon((
        Point2D(0, 0), Point2D(w, 0), Point2D(w, braco),
        Point2D(braco, braco), Point2D(braco, h), Point2D(0, h),
    ))


def _u(w=80, h=80, boca=30, fundo=20):
    """'U': vao central de largura 'boca' descendo ate y='fundo'."""
    x0 = (w - boca) / 2
    return Polygon((
        Point2D(0, 0), Point2D(w, 0), Point2D(w, h), Point2D(x0 + boca, h),
        Point2D(x0 + boca, fundo), Point2D(x0, fundo), Point2D(x0, h), Point2D(0, h),
    ))


def _divergencias(a_placed, b_norm, gap, lo, hi, n=200, seed=20260720):
    """Compara ponto-dentro-do-NFP contra o oraculo em n posicoes da mesma
    semente. Retorna (nfp, lista de divergencias, nº de casos com sobreposicao)."""
    rng = random.Random(seed)
    nfp = _nfp(_offset(a_placed, gap / 2), _offset(b_norm, gap / 2))
    divergencias = []
    casos_overlap = 0
    for _ in range(n):
        t = Point2D(rng.uniform(lo, hi), rng.uniform(lo, hi))
        oraculo = _overlaps(a_placed, b_norm.translated(t.x, t.y), gap)
        casos_overlap += oraculo
        if oraculo != _nfp_blocks(nfp, t):
            divergencias.append((round(t.x, 3), round(t.y, 3), oraculo))
    return nfp, divergencias, casos_overlap


def test_nfp_concordancia_retangulo_x_retangulo():
    a = _rect(60, 40).translated(20, 30)
    b = _normalized(_rect(30, 20))
    _, div, overlap = _divergencias(a, b, _GAP, lo=-60, hi=140)
    assert div == []
    assert 0 < overlap < 200  # amostragem cobriu as duas classes


def test_nfp_concordancia_concavo_x_quadrado():
    a = _ele().translated(40, 40)
    b = _normalized(_rect(25, 25))
    _, div, overlap = _divergencias(a, b, _GAP, lo=-40, hi=160)
    assert div == []
    assert 0 < overlap < 200


def test_nfp_concordancia_encaixe_no_vao():
    # quadrado 20 cabe no vao do U (boca 30 - gap 3 dos dois lados = 24 livres)
    a = _u().translated(50, 50)
    b = _normalized(_rect(20, 20))
    nfp, div, overlap = _divergencias(a, b, _GAP, lo=-40, hi=180)
    assert div == []
    assert 0 < overlap < 200
    # vao ABERTO por cima: as posicoes validas viram uma FENDA no NFP (regiao
    # conectada ao exterior, nao furo). Meio do vao, folga > gap: permitido.
    dentro_do_vao = Point2D(80, 80)  # vao em coords da chapa: x 75..105, y 70..130
    assert not _nfp_blocks(nfp, dentro_do_vao)
    assert not _overlaps(a, b.translated(dentro_do_vao.x, dentro_do_vao.y), _GAP)


def _camara(w=80, h=80, cam=40, boca=10):
    """Peca com camara interna 'cam' x 'cam' ligada ao topo por pescoco de
    largura 'boca' < peca orbitante: o vao vira FURO fechado no NFP."""
    c0 = (w - cam) / 2                    # camara: x/y em [c0, c0+cam]
    n0 = (w - boca) / 2                   # pescoco: x em [n0, n0+boca]
    return Polygon((
        Point2D(0, 0), Point2D(w, 0), Point2D(w, h),
        Point2D(n0 + boca, h), Point2D(n0 + boca, c0 + cam),
        Point2D(c0 + cam, c0 + cam), Point2D(c0 + cam, c0),
        Point2D(c0, c0), Point2D(c0, c0 + cam),
        Point2D(n0, c0 + cam), Point2D(n0, h), Point2D(0, h),
    ))


def test_nfp_furo_verdadeiro_camara_fechada():
    # quadrado 20 CABE na camara 40x40 mas NAO passa pelo pescoco de 10:
    # as posicoes validas ficam cercadas de invalidas = furo real no NFP.
    a = _camara().translated(50, 50)
    b = _normalized(_rect(20, 20))
    nfp, div, overlap = _divergencias(a, b, _GAP, lo=-40, hi=180)
    assert div == []
    assert 0 < overlap < 200
    assert len(nfp) >= 2  # fronteira externa + furo da camara
    # camara em coords da chapa: x/y em 70..110 -> referencia valida em 73..87
    no_meio = Point2D(80, 80)
    assert not _nfp_blocks(nfp, no_meio)
    assert not _overlaps(a, b.translated(no_meio.x, no_meio.y), _GAP)
    # no pescoco (largura 10 < peca 20): bloqueado
    assert _nfp_blocks(nfp, Point2D(80, 120))


def test_nfp_orbitante_maior_nao_cria_furo_falso():
    # B maior que A: o Minkowski do clipper gera um "miolo oco" que NAO e vao
    # real (B ali engole A = sobrepoe). O _nfp tem que descartar esse furo.
    a = _rect(20, 20).translated(60, 60)
    b = _normalized(_rect(100, 100))
    nfp, div, overlap = _divergencias(a, b, _GAP, lo=-80, hi=120)
    assert div == []
    assert 0 < overlap < 200
    assert len(nfp) == 1  # so a fronteira externa; miolo oco foi descartado
    # B centrada sobre A (engolindo-a): tem que estar bloqueado
    assert _nfp_blocks(nfp, Point2D(10, 10))


# --- 2C: IFP retangular + posicionador NFP x oraculo ---------------------------


def _ordenar(shapes):
    """Mesma ordem que o oraculo usa internamente (area desc)."""
    return sorted(shapes, key=lambda s: s.contour.area, reverse=True)


def _bbox_area(shapes, placements):
    """Area do bounding box que envolve TODAS as pecas colocadas."""
    polys = [_placed_poly(shapes, p) for p in placements]
    min_x = min(p.bounding_box.min_x for p in polys)
    min_y = min(p.bounding_box.min_y for p in polys)
    max_x = max(p.bounding_box.max_x for p in polys)
    max_y = max(p.bounding_box.max_y for p in polys)
    return (max_x - min_x) * (max_y - min_y)


def test_ifp_rect_regiao_valida_e_peca_grande_demais():
    ifp = _ifp_rect(_rect(50, 50), 200, 100, margin=10)
    bb = ifp.bounding_box
    assert (bb.min_x, bb.min_y, bb.max_x, bb.max_y) == (10, 10, 140, 40)
    assert _ifp_rect(_rect(500, 500), 200, 200, margin=0) is None
    assert _ifp_rect(_rect(190, 50), 200, 200, margin=10) is None  # nao sobra p/ margem


def test_nfp_encaixe_justo_vai_para_o_canto():
    # sobra ZERO nos dois eixos: IFP degenera em ponto; tem que colocar mesmo
    # assim, com a referencia no canto (margin, margin).
    shapes = [NestingShape("justa", _rect(180, 180))]
    mat = Material("chapa", width=200, margin=10, spacing=0)
    placements = _place_nfp(shapes, [0.0], mat, sheet_h=200)
    assert len(placements) == 1
    assert abs(placements[0].position.x - 10) < 0.01
    assert abs(placements[0].position.y - 10) < 0.01


def test_nfp_posicionador_bate_oraculo_no_mix():
    # retangulos + triangulo (aresta diagonal) + 'L' (concavo)
    shapes = [
        NestingShape("q1", _rect(60, 60)),
        NestingShape("r1", _rect(80, 30)),
        NestingShape("t1", _tri(50)),
        NestingShape("L1", _ele(70, 70, 25)),
        NestingShape("q2", _rect(40, 40).translated(300, 300)),  # origem nao importa
    ]
    mat = Material("chapa", width=200, margin=5, spacing=2)
    order = _ordenar(shapes)
    nfp_p = _place_nfp(order, [0.0] * len(order), mat, sheet_h=200)
    ora_p = _place_bruteforce(shapes, mat, sheet_h=200)
    # coloca tudo que o oraculo coloca (aqui: todas as 5)
    assert len(ora_p) == len(shapes)
    assert len(nfp_p) >= len(ora_p)
    # zero sobreposicao + tudo dentro da chapa
    assert _sem_sobreposicao(shapes, nfp_p, gap=2.0)
    for p in nfp_p:
        assert _inside_sheet(_placed_poly(shapes, p), 200, 200, margin=5)
    # NFP empacota igual ou melhor que o oraculo
    assert _bbox_area(shapes, nfp_p) <= _bbox_area(shapes, ora_p) + 1e-6


def test_nfp_posicionador_peca_gigante_fica_de_fora():
    shapes = [NestingShape("ok", _rect(50, 50)), NestingShape("gigante", _rect(500, 500))]
    mat = Material("chapa", width=200, margin=0, spacing=0)
    order = _ordenar(shapes)
    placements = _place_nfp(order, [0.0] * len(order), mat, sheet_h=200)
    assert [p.artwork_id for p in placements] == ["ok"]


def test_nfp_posicionador_deterministico():
    shapes = [
        NestingShape("q1", _rect(60, 60)),
        NestingShape("t1", _tri(50)),
        NestingShape("L1", _ele(70, 70, 25)),
    ]
    mat = Material("chapa", width=200, margin=5, spacing=2)
    order = _ordenar(shapes)
    a = _place_nfp(order, [0.0] * len(order), mat, sheet_h=200)
    b = _place_nfp(order, [0.0] * len(order), mat, sheet_h=200)
    assert a == b


# --- 2D: rotacao + algoritmo genetico ------------------------------------------


def _fitness_de(shapes, placements):
    """Mesma formula do GA: area do bounding + penalidade por peca de fora."""
    area = _bbox_area(shapes, placements) if placements else 0.0
    return area + _UNPLACED_PENALTY * (len(shapes) - len(placements))


def test_ga_deterministico_mesmo_seed():
    shapes = [
        NestingShape("q1", _rect(60, 60)),
        NestingShape("r1", _rect(80, 30)),
        NestingShape("t1", _tri(50)),
        NestingShape("L1", _ele(70, 70, 25)),
    ]
    mat = Material("chapa", width=200, margin=5, spacing=2)
    a = _optimize_ga(shapes, mat, 200, seed=42, generations=8, population_size=8)
    b = _optimize_ga(shapes, mat, 200, seed=42, generations=8, population_size=8)
    assert a == b  # posicoes, rotacoes e ordem identicas => mesmo gene/fitness


def test_ga_rotacao_melhora_o_encaixe():
    # dois 'L' iguais: com rot 0 ficam lado a lado (bbox ~163x80); girando um
    # deles 180 eles se ENTRELACAM (bbox ~113x80). So a rotacao destrava isso.
    shapes = [
        NestingShape("L1", _ele(80, 80, 30)),
        NestingShape("L2", _ele(80, 80, 30)),
    ]
    mat = Material("chapa", width=200, margin=0, spacing=3)
    order = _ordenar(shapes)
    naive = _place_nfp(order, [0.0] * len(order), mat, sheet_h=100)
    ga = _optimize_ga(shapes, mat, 100, seed=11, generations=20, population_size=12)
    assert len(naive) == 2 and len(ga) == 2
    assert _fitness_de(shapes, ga) < _fitness_de(shapes, naive)  # genetico agrega
    assert _sem_sobreposicao(shapes, ga, gap=3.0)
    for p in ga:
        assert _inside_sheet(_placed_poly(shapes, p), 200, 100, margin=0)


def test_ga_melhor_gene_sem_sobreposicao_e_todas_que_cabem():
    shapes = [
        NestingShape("q1", _rect(50, 50)),
        NestingShape("r1", _rect(80, 30)),
        NestingShape("t1", _tri(40)),
        NestingShape("gigante", _rect(500, 500)),
    ]
    mat = Material("chapa", width=200, margin=5, spacing=2)
    ga = _optimize_ga(shapes, mat, 200, seed=3, generations=10, population_size=10)
    assert {p.artwork_id for p in ga} == {"q1", "r1", "t1"}  # tudo que cabe; gigante fora
    assert _sem_sobreposicao(shapes, ga, gap=2.0)
    for p in ga:
        assert _inside_sheet(_placed_poly(shapes, p), 200, 200, margin=5)


def test_ga_respeita_orcamento_de_tempo():
    shapes = [
        NestingShape("q1", _rect(60, 60)),
        NestingShape("q2", _rect(40, 40)),
        NestingShape("r1", _rect(80, 30)),
        NestingShape("t1", _tri(50)),
        NestingShape("L1", _ele(70, 70, 25)),
    ]
    mat = Material("chapa", width=200, margin=5, spacing=2)
    start = time.monotonic()
    ga = _optimize_ga(shapes, mat, 200, seed=1, genetics_time=1.0, population_size=10)
    elapsed = time.monotonic() - start
    assert elapsed < 3.0  # 1s de orcamento + folga p/ terminar a avaliacao corrente
    assert len(ga) == len(shapes)  # devolveu o melhor ate entao, valido
    assert _sem_sobreposicao(shapes, ga, gap=2.0)


# --- 2E: TrueShapePacker (interface publica + enum Rotation) --------------------


def _item_poly(shapes, item):
    """Reconstroi a peca do PlacedItem pela CONVENCAO da Fase 4: gira o
    contorno original pelo enum, normaliza (bbox.min na origem) e translada
    para item.position."""
    shape = next(s for s in shapes if s.artwork_id == item.artwork_id)
    return _normalized(shape.contour.rotated(float(item.rotation))).translated(
        item.position.x, item.position.y
    )


def _itens_sem_sobreposicao(shapes, items, gap):
    polys = [_item_poly(shapes, it) for it in items]
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            if _overlaps(polys[i], polys[j], gap):
                return False
    return True


def test_packer_pack_ponta_a_ponta():
    shapes = [
        NestingShape("q1", _rect(60, 60)),
        NestingShape("r1", _rect(80, 30)),
        NestingShape("t1", _tri(50)),
        NestingShape("L1", _ele(70, 70, 25)),
    ]
    mat = Material("chapa", width=200)
    packer = TrueShapePacker(gap=2.0, margin=5.0, generations=10, seed=42)
    layout = packer.pack(shapes, mat)
    assert isinstance(layout, Layout)
    assert layout.material is mat  # material ORIGINAL; gap/margin sao do packer
    assert len(layout.items) == len(shapes)
    for item in layout.items:
        assert isinstance(item, PlacedItem)
        assert isinstance(item.rotation, Rotation)  # enum, nao float
        bb = _item_poly(shapes, item).bounding_box
        assert bb.min_x >= 5 - 0.01 and bb.max_x <= 195 + 0.01 and bb.min_y >= 5 - 0.01
    assert _itens_sem_sobreposicao(shapes, layout.items, gap=2.0)
    fundo = max(_item_poly(shapes, it).bounding_box.max_y for it in layout.items)
    assert layout.used_length == pytest.approx(fundo + 5.0)


def test_packer_pack_sheets_varias_chapas_nada_perdido():
    shapes = [NestingShape(f"q{i}", _rect(50, 50)) for i in range(5)]
    # largura util 110 (2 pecas por linha), altura util 55 (1 linha por chapa)
    mat = Material("chapa", width=120)
    packer = TrueShapePacker(gap=2.0, margin=5.0, generations=5, seed=1)
    sheets = packer.pack_sheets(shapes, mat, sheet_length=65)
    assert len(sheets) == 3  # 2 + 2 + 1
    ids = sorted(it.artwork_id for s in sheets for it in s.items)
    assert ids == sorted(s.artwork_id for s in shapes)  # nada perdido, nada duplicado
    for sheet in sheets:
        assert sheet.used_length == 65
        assert _itens_sem_sobreposicao(shapes, sheet.items, gap=2.0)
        for item in sheet.items:
            bb = _item_poly(shapes, item).bounding_box
            assert bb.min_x >= 5 - 0.01 and bb.max_x <= 115 + 0.01
            assert bb.min_y >= 5 - 0.01 and bb.max_y <= 60 + 0.01


def test_packer_reconciliacao_rotacao_vira_enum():
    # 80x40 numa chapa de 60 de largura: a 0 NAO cabe; a 90 (40x80) cabe.
    # O GA e OBRIGADO a girar, e o PlacedItem tem que sair com o ENUM de 90.
    shapes = [NestingShape("deitada", _rect(80, 40), rotations=(0.0, 90.0))]
    mat = Material("chapa", width=60)
    packer = TrueShapePacker(generations=10, seed=2)
    layout = packer.pack(shapes, mat)
    assert len(layout.items) == 1
    item = layout.items[0]
    assert item.rotation is Rotation.CW90
    bb = _item_poly(shapes, item).bounding_box
    assert bb.width == pytest.approx(40) and bb.height == pytest.approx(80)


def test_place_nfp_busca_rotacao_por_peca():
    # entrada em TUPLA = candidatos: a peca testa as rotacoes e usa a que
    # couber mais baixo (aqui, so a 90 cabe na chapa estreita).
    shapes = [NestingShape("p", _rect(80, 40), rotations=(0.0, 90.0))]
    mat = Material("chapa", width=60)
    placements = _place_nfp(shapes, [(0.0, 90.0)], mat, sheet_h=200)
    assert placements is not None and len(placements) == 1
    assert placements[0].rotation == 90.0


def test_sementes_avaliadas_mesmo_com_orcamento_estourado():
    # orcamento zero: estoura ja na 1a avaliacao. As DUAS sementes sao o
    # minimo util — sem avaliar a 'deitada', trabalho pesado nunca girava
    # (caso real de 21/07: 44 letras de PDF voltavam 100% em pe).
    shapes = [NestingShape(f"p{i}", _rect(30, 90)) for i in range(4)]
    mat = Material("chapa", width=500, spacing=5)
    ga = _optimize_ga(shapes, mat, 500, seed=1, genetics_time=0.0)
    assert len(ga) == 4
    # com o espacamento, deitar as 4 pecas da bbox menor que em pe
    assert all(int(p.rotation) % 360 == 90 for p in ga)


def test_packer_giro_fino_sai_como_float_em_graus():
    # Angulo fora dos 90 em 90 ('Fix angle' fino do Modo Corte): o PlacedItem
    # carrega o float em graus e a reconstrucao da Fase 4 (float(rotation))
    # fecha o circuito sem enum.
    shapes = [NestingShape("fina", _rect(80, 40), rotations=(45.0,))]
    layout = TrueShapePacker(generations=3, seed=1).pack(shapes, Material("chapa", width=200))
    assert len(layout.items) == 1
    item = layout.items[0]
    assert not isinstance(item.rotation, Rotation)
    assert float(item.rotation) == pytest.approx(45.0)
    bb = _item_poly(shapes, item).bounding_box
    # retangulo 80x40 girado 45 graus: bbox quadrado de (80+40)/raiz(2)
    assert bb.width == pytest.approx(120 / 2**0.5, rel=1e-3)
    assert bb.height == pytest.approx(120 / 2**0.5, rel=1e-3)


# --- 6: inside_check — peca dentro do furo de outra ("Allow inside") ---------


def _anel(lado=100.0, furo=60.0):
    """Letra 'O' esquematica: quadrado 'lado' com furo quadrado centrado.
    Devolve (contorno, furo) em coordenadas ja normalizadas (bbox.min na
    origem), que e como o motor trata a peca."""
    off = (lado - furo) / 2
    return _rect(lado, lado), _rect(furo, furo).translated(off, off)


def _circulo(raio, n=32, cx=0.0, cy=0.0):
    return Polygon(tuple(
        Point2D(cx + raio * math.cos(2 * math.pi * i / n),
                cy + raio * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ))


def _no_ifp(rings, t):
    """Ponto dentro da regiao do IFP (contagem par-impar sobre os aneis)."""
    return sum(1 for ring in rings if ring.contains(t)) % 2 == 1


def _confere_ifp(hole, piece, lo, hi, n=400, seed=20260721):
    """Compara o IFP de furo com o bruteforce (contencao real) em n posicoes.
    Devolve (falsos_positivos, encontrados, cabem_de_verdade)."""
    rings = _ifp_hole(hole, piece)
    rng = random.Random(seed)
    falsos = achados = cabem = 0
    for _ in range(n):
        t = Point2D(rng.uniform(lo, hi), rng.uniform(lo, hi))
        real = _contains(hole, piece.translated(t.x, t.y))
        diz = _no_ifp(rings, t)
        cabem += real
        achados += real and diz
        falsos += diz and not real
    return falsos, achados, cabem


def test_ifp_hole_quadrado_em_furo_quadrado_e_exato():
    # quadrado 10 num furo 30 em (10,10): a referencia (bbox.min) cabe em
    # [10,30] nos dois eixos — quadrado de lado 20, area 400.
    hole = _rect(30, 30).translated(10, 10)
    rings = _ifp_hole(hole, _rect(10, 10))
    assert len(rings) == 1
    bb = rings[0].bounding_box
    assert rings[0].area == pytest.approx(400, rel=1e-6)
    assert (bb.min_x, bb.min_y) == pytest.approx((10, 10))
    assert (bb.max_x, bb.max_y) == pytest.approx((30, 30))


def test_ifp_hole_concorda_com_bruteforce():
    # Sanidade que protege o corte: NADA que o IFP aprova pode escapar do furo
    # (falso positivo = peca colidindo com a parede). Perder um pedacinho da
    # regiao so custa densidade, entao a cobertura vale com folga.
    hole = _rect(30, 30).translated(10, 10)
    falsos, achados, cabem = _confere_ifp(hole, _rect(10, 10), lo=0, hi=45)
    assert falsos == 0
    assert cabem > 20 and achados >= 0.95 * cabem

    # furo redondo x quadrado: erosao sem forma analitica, mesma exigencia
    redondo = _circulo(20, cx=30, cy=30)
    falsos, achados, cabem = _confere_ifp(redondo, _rect(15, 15), lo=5, hi=55)
    assert falsos == 0
    assert cabem > 20 and achados >= 0.95 * cabem


def test_ifp_hole_vazio_quando_a_peca_nao_cabe():
    hole = _rect(30, 30).translated(10, 10)
    assert _ifp_hole(hole, _rect(40, 40)) == ()   # maior que o furo
    assert _ifp_hole(hole, _rect(31, 5)) == ()    # cabe em area, nao em forma


def test_shrunk_devolve_none_quando_o_furo_some():
    assert _shrunk(_rect(30, 30), 2.0).area == pytest.approx(26 * 26)
    assert _shrunk(_rect(4, 4), 5.0) is None


def test_rotated_parts_gira_furo_junto_com_o_contorno():
    outer, hole = _anel(100, 40)
    shape = NestingShape("O", outer, holes=(hole,))
    norm, holes = _rotated_parts(shape, 90.0)
    # o contorno normalizado bate com o caminho antigo (_normalized(rotated))
    assert norm.bounding_box.min_x == pytest.approx(0)
    assert norm.bounding_box.min_y == pytest.approx(0)
    # furo continua centrado DENTRO do contorno, nao normalizado por si so
    assert len(holes) == 1
    bb = holes[0].bounding_box
    assert (bb.min_x, bb.min_y) == pytest.approx((30, 30))
    assert (bb.max_x, bb.max_y) == pytest.approx((70, 70))
    assert _contains(norm, holes[0])


def _o_e_quadrado(gap, lado_quadrado=20.0):
    """Cenario padrao da fase: um 'O' 100x100 (furo 60) que toma a chapa
    inteira e um quadrado que SO tem o furo como sobra."""
    outer, hole = _anel(100, 60)
    shapes = [
        NestingShape("O", outer, rotations=(0.0,), holes=(hole,)),
        NestingShape("q", _rect(lado_quadrado, lado_quadrado), rotations=(0.0,)),
    ]
    mat = Material("chapa", width=110, margin=0, spacing=gap)
    return shapes, mat


def test_inside_check_quadrado_entra_no_furo_do_O():
    gap = 2.0
    shapes, mat = _o_e_quadrado(gap)
    placements = _place_nfp(shapes, [0.0, 0.0], mat, sheet_h=110, inside_check=True)
    assert placements is not None and len(placements) == 2

    o_poly = _placed_poly(shapes, placements[0])
    q_poly = _placed_poly(shapes, placements[1])
    _, furos = _rotated_parts(shapes[0], placements[0].rotation)
    furo = furos[0].translated(placements[0].position.x, placements[0].position.y)

    assert _contains(furo, q_poly)                       # dentro do furo
    assert not _overlaps(o_poly, q_poly, gap, holes_a=[furo])  # gap respeitado
    # ...e a folga e mesmo a pedida: encostar (gap 0) passaria, gap+0.1 nao.
    assert _overlaps(o_poly, q_poly, gap + 0.5, holes_a=[furo])


def test_inside_check_nao_rouba_a_peca_do_bottom_left():
    # CHAPA LARGA: sobra chapa livre ao lado do 'O', toda com y MENOR que o
    # miolo. A regra continua sendo o menor (y, x) global, entao o quadrado
    # vai para a chapa — o furo nao ganha na marra. Isso e o que garante que
    # ligar a caixa nunca piora: forcar a preferencia tirava as pecas
    # pequenas da frente do bottom-left e as grandes se entrelacavam pior
    # (medido em 21/07: 50,5% -> 47,2% num lote misto de letras).
    outer, hole = _anel(100, 60)
    shapes = [
        NestingShape("O", outer, rotations=(0.0,), holes=(hole,)),
        NestingShape("q", _rect(20, 20), rotations=(0.0,)),
    ]
    mat = Material("chapa", width=400, margin=0, spacing=2.0)
    com = _place_nfp(shapes, [0.0, 0.0], mat, sheet_h=400, inside_check=True)
    sem = _place_nfp(shapes, [0.0, 0.0], mat, sheet_h=400)
    assert com == sem  # chapa folgada: inside_check nao muda NADA


def test_inside_check_desligado_deixa_o_furo_vazio():
    # mesma cena, motor da Fase 2: o quadrado nao tem para onde ir.
    shapes, mat = _o_e_quadrado(2.0)
    placements = _place_nfp(shapes, [0.0, 0.0], mat, sheet_h=110)
    assert placements is not None
    assert [p.artwork_id for p in placements] == ["O"]


def test_inside_check_duas_pecas_no_mesmo_furo_nao_se_sobrepoem():
    gap = 2.0
    outer, hole = _anel(100, 60)
    shapes = [
        NestingShape("O", outer, rotations=(0.0,), holes=(hole,)),
        NestingShape("q1", _rect(20, 20), rotations=(0.0,)),
        NestingShape("q2", _rect(20, 20), rotations=(0.0,)),
    ]
    mat = Material("chapa", width=110, margin=0, spacing=gap)
    placements = _place_nfp(shapes, [0.0] * 3, mat, sheet_h=110, inside_check=True)
    assert placements is not None and len(placements) == 3

    _, furos = _rotated_parts(shapes[0], placements[0].rotation)
    furo = furos[0].translated(placements[0].position.x, placements[0].position.y)
    q1, q2 = (_placed_poly(shapes, p) for p in placements[1:])
    assert _contains(furo, q1) and _contains(furo, q2)
    assert not _overlaps(q1, q2, gap)


def test_inside_check_gap_grande_barra_a_entrada_no_furo():
    # furo 60 com folga 30 dos dois lados sobra 30 de vao util: o quadrado 20
    # inflado em 15 vira 50 e NAO cabe. Nada de "quase encaixou".
    shapes, mat = _o_e_quadrado(gap=30.0)
    placements = _place_nfp(shapes, [0.0, 0.0], mat, sheet_h=110, inside_check=True)
    assert placements is not None
    assert [p.artwork_id for p in placements] == ["O"]


def test_packer_inside_check_liga_pelo_construtor():
    shapes, mat = _o_e_quadrado(2.0)
    cheio = TrueShapePacker(
        gap=2.0, margin=0.0, generations=3, seed=1, approximation=0.0, inside_check=True
    ).pack(shapes, mat)
    vazio = TrueShapePacker(
        gap=2.0, margin=0.0, generations=3, seed=1, approximation=0.0
    ).pack(shapes, mat)
    # chapa ABERTA: os dois colocam tudo — o que muda e ONDE. Com o furo
    # aproveitado o quadrado some dentro do 'O' e a chapa usada nao cresce;
    # sem, ele desce para uma linha nova (100 + gap + 20).
    assert len(cheio.items) == len(vazio.items) == 2
    assert cheio.used_length == pytest.approx(100.0)
    assert vazio.used_length == pytest.approx(122.0)


def test_inside_check_prefere_furo_quando_o_gene_manda():
    # o bit 'prefer_holes' do cromossomo: com chapa LARGA sobra espaco livre
    # com y menor que o miolo, entao a regra normal manda o quadrado para a
    # chapa; com o bit ligado ele vai para o furo. E o GA que escolhe.
    outer, hole = _anel(100, 60)
    shapes = [
        NestingShape("O", outer, rotations=(0.0,), holes=(hole,)),
        NestingShape("q", _rect(20, 20), rotations=(0.0,)),
    ]
    mat = Material("chapa", width=400, margin=0, spacing=2.0)
    _, furos = _rotated_parts(shapes[0], 0.0)

    normal = _place_nfp(shapes, [0.0, 0.0], mat, sheet_h=400, inside_check=True)
    cheio = _place_nfp(
        shapes, [0.0, 0.0], mat, sheet_h=400, inside_check=True, prefer_holes=True
    )
    assert normal is not None and cheio is not None
    furo = furos[0].translated(normal[0].position.x, normal[0].position.y)
    assert not _contains(furo, _placed_poly(shapes, normal[1]))  # foi p/ chapa
    assert _contains(furo, _placed_poly(shapes, cheio[1]))       # foi p/ o furo


def test_packer_inside_check_nao_piora_o_encaixe():
    # Ligar a caixa nao pode custar encaixe: as sementes SEM preferencia por
    # furo entram primeiro e o elitismo guarda o melhor. Antes do bit no
    # cromossomo, encher o furo era regra fixa, tirava as pecas pequenas da
    # frente do bottom-left e o lote saia PIOR (21/07: 50,5% -> 47,2% em
    # letras mistas). Cuidado ao mexer: a garantia vale contra as SEMENTES,
    # nao contra o passeio aleatorio do GA — em lote grande a diferenca fica
    # no nivel do ruido, nao em zero.
    outer, hole = _anel(100, 60)
    shapes = [
        NestingShape("O", outer, rotations=(0.0, 90.0), holes=(hole,)),
        NestingShape("q1", _rect(20, 20), rotations=(0.0, 90.0)),
        NestingShape("q2", _rect(30, 15), rotations=(0.0, 90.0)),
    ]
    for largura in (110.0, 400.0):
        mat = Material("chapa", width=largura)
        kw = dict(gap=2.0, margin=0.0, generations=6, seed=5, approximation=0.0)
        ligado = TrueShapePacker(**kw, inside_check=True).pack(shapes, mat)
        desligado = TrueShapePacker(**kw).pack(shapes, mat)
        assert len(ligado.items) >= len(desligado.items)
        assert ligado.used_length <= desligado.used_length + 0.01


def test_packer_inside_check_deterministico():
    shapes, mat = _o_e_quadrado(2.0)

    def run():
        return TrueShapePacker(
            gap=2.0, margin=0.0, generations=6, seed=11, approximation=0.0, inside_check=True
        ).pack(shapes, mat)

    assert run() == run()


def test_packer_deterministico_com_generations_e_seed():
    shapes = [
        NestingShape("q1", _rect(60, 60)),
        NestingShape("t1", _tri(50)),
        NestingShape("L1", _ele(70, 70, 25)),
    ]
    mat = Material("chapa", width=200)
    a = TrueShapePacker(gap=2.0, margin=5.0, generations=8, seed=7).pack(shapes, mat)
    b = TrueShapePacker(gap=2.0, margin=5.0, generations=8, seed=7).pack(shapes, mat)
    assert a == b  # Layout inteiro identico (itens, rotacoes, used_length)


def test_simplified_remove_redundantes_sem_destruir_peca_pequena():
    # quadrado 50x50 com vertices colineares no meio das arestas: caem fora
    redundante = Polygon((
        Point2D(0, 0), Point2D(25, 0), Point2D(50, 0), Point2D(50, 25),
        Point2D(50, 50), Point2D(25, 50), Point2D(0, 50), Point2D(0, 25),
    ))
    simples = _simplified(redundante, 0.1)
    assert len(simples.vertices) == 4
    assert simples.area == pytest.approx(2500)
    # peca MENOR que a tolerancia: a simplificacao a destruiria; fica o original
    minuscula = Polygon((Point2D(0, 0), Point2D(0.05, 0), Point2D(0, 0.05)))
    assert _simplified(minuscula, 0.1) is minuscula
