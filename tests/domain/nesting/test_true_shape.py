"""Testes do nesting true-shape (Fase 2).

2A: o oraculo bruteforce e o gabarito de correcao — estes testes provam que
ele coloca pecas dentro da chapa sem sobreposicao. As sub-fases seguintes
(NFP, genetico) serao validadas CONTRA ele.
"""

import random
import time

import pytest

from app.domain.geometry import Point2D
from app.domain.geometry.polygon import Polygon
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem, Rotation
from app.domain.nesting.true_shape import (
    TrueShapePacker,
    _UNPLACED_PENALTY,
    NestingShape,
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


def test_packer_inside_check_e_fase_futura():
    with pytest.raises(NotImplementedError):
        TrueShapePacker(inside_check=True)


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
