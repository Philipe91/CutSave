import pytest
from app.domain.cut.cartela import build_cartela_grid, cartela_separation_segments


def test_grade_centrada_na_chapa():
    g = build_cartela_grid(700, 1000, 330, 480, 0)
    assert (g.cols, g.rows) == (2, 2)
    assert g.origin_x == pytest.approx((700 - 2 * 330) / 2)
    assert g.origin_y == pytest.approx((1000 - 2 * 480) / 2)


def test_slots_em_ordem_de_leitura():
    g = build_cartela_grid(700, 1000, 330, 480, 0)
    assert g.slot_origin(0) == pytest.approx((20.0, 20.0))
    assert g.slot_origin(1) == pytest.approx((350.0, 20.0))   # direita
    assert g.slot_origin(2) == pytest.approx((20.0, 500.0))   # linha de baixo
    assert g.per_sheet == 4


def test_cartela_nao_cabe_devolve_none():
    assert build_cartela_grid(300, 400, 330, 480, 0) is None    # larga demais
    assert build_cartela_grid(700, 400, 330, 480, 0) is None    # alta demais


def test_chapa_aberta_cresce_em_linhas():
    g = build_cartela_grid(700, 0, 330, 480, 0)
    assert g.cols == 2
    assert g.rows == 0  # ilimitado
    assert g.block_height(3) == pytest.approx(2 * 480)  # 3 cartelas = 2 linhas


def test_linhas_fora_a_fora_com_dedupe():
    # gutter 0: bordas internas coincidem -> UMA linha (a maquina corta 1x)
    g = build_cartela_grid(700, 1000, 330, 480, 0)
    segs = cartela_separation_segments(g, 700, 1000)
    verticais = [s for s in segs if s.start.x == s.end.x]
    horizontais = [s for s in segs if s.start.y == s.end.y]
    assert len(verticais) == 3   # esquerda, meio (fundida), direita
    assert len(horizontais) == 3
    # fora a fora: atravessam a chapa INTEIRA
    assert all(s.start.y == 0 and s.end.y == 1000 for s in verticais)
    assert all(s.start.x == 0 and s.end.x == 700 for s in horizontais)


def test_linhas_com_gutter_dobram_no_meio():
    # gutter 10: cada boundary interno vira DUAS linhas (com apara no meio)
    g = build_cartela_grid(700, 1000, 330, 480, 10)
    segs = cartela_separation_segments(g, 700, 1000)
    verticais = [s for s in segs if s.start.x == s.end.x]
    assert len(verticais) == 4  # borda esq, 2 do vao central, borda dir
