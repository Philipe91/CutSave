"""Fusao automatica de cortes rentes (merge_touching_rect_cuts).

Quadrados COLADOS (espacamento 0) devem virar uma grade de linhas continuas
(a maquina corta 1x por linha, sem passar 2x na mesma borda); pecas com
espacamento ou contornos nao-retangulares ficam com corte individual.
"""

from app.domain.cut.shared import Segment, merge_touching_rect_cuts
from app.domain.geometry import Point2D


def _rect(x0, y0, x1, y1):
    return [Point2D(x0, y0), Point2D(x1, y0), Point2D(x1, y1), Point2D(x0, y1)]


def _circle_ish():
    # contorno nao-retangular (6 pontos)
    return [
        Point2D(5, 0), Point2D(10, 3), Point2D(10, 7),
        Point2D(5, 10), Point2D(0, 7), Point2D(0, 3),
    ]


def test_grade_2x2_colada_funde_em_6_linhas_continuas():
    contours = [
        _rect(0, 0, 50, 50), _rect(50, 0, 100, 50),
        _rect(0, 50, 50, 100), _rect(50, 50, 100, 100),
    ]
    consumed, segs = merge_touching_rect_cuts(contours)
    assert consumed == {0, 1, 2, 3}  # todos os quadrados viraram grade
    # 3 verticais (x=0, 50, 100) + 3 horizontais, todas fora a fora
    assert len(segs) == 6
    assert Segment(Point2D(50, 0), Point2D(50, 100)) in segs   # linha interna 1x
    assert Segment(Point2D(0, 50), Point2D(100, 50)) in segs
    assert Segment(Point2D(0, 0), Point2D(0, 100)) in segs      # borda externa


def test_pecas_com_espacamento_ficam_individuais():
    contours = [_rect(0, 0, 50, 50), _rect(52, 0, 102, 50)]  # 2mm de vao
    consumed, segs = merge_touching_rect_cuts(contours)
    assert consumed == set() and segs == []  # nada muda: corte por peca


def test_misto_so_funde_quem_esta_colado():
    contours = [
        _rect(0, 0, 50, 50), _rect(50, 0, 100, 50),  # coladas entre si
        _rect(200, 0, 250, 50),                       # isolada (longe)
        _circle_ish(),                                # contorno curvo
    ]
    consumed, segs = merge_touching_rect_cuts(contours)
    assert consumed == {0, 1}
    assert Segment(Point2D(50, 0), Point2D(50, 50)) in segs  # borda comum: 1 linha
    # bloco 2x1: 3 verticais + 2 horizontais
    assert len(segs) == 5


def test_tolerancia_absorve_folga_numerica():
    # bordas a 0.05mm (residuo de float do nesting) ainda contam como coladas
    contours = [_rect(0, 0, 50, 50), _rect(50.05, 0, 100, 50)]
    consumed, segs = merge_touching_rect_cuts(contours)
    assert consumed == {0, 1}
    verticais = [s for s in segs if abs(s.start.x - s.end.x) < 1e-6]
    assert len(verticais) == 3  # borda comum fundida numa linha so


def test_encostar_so_no_canto_nao_funde():
    # contato de canto (diagonal) nao e borda compartilhada
    contours = [_rect(0, 0, 50, 50), _rect(50, 50, 100, 100)]
    consumed, segs = merge_touching_rect_cuts(contours)
    assert consumed == set() and segs == []


def test_coluna_com_vao_gera_segmentos_separados_na_mesma_linha():
    # duas duplas coladas, com 20mm de vao vertical entre os blocos:
    # a linha x=50 existe nos dois blocos mas NAO atravessa o vao
    contours = [
        _rect(0, 0, 50, 50), _rect(50, 0, 100, 50),
        _rect(0, 70, 50, 120), _rect(50, 70, 100, 120),
    ]
    consumed, segs = merge_touching_rect_cuts(contours)
    assert consumed == {0, 1, 2, 3}
    meio = sorted(
        [s for s in segs if abs(s.start.x - 50) < 1e-6 and abs(s.end.x - 50) < 1e-6],
        key=lambda s: s.start.y,
    )
    assert len(meio) == 2  # um por bloco, sem cruzar o vao
    assert (meio[0].start.y, meio[0].end.y) == (0, 50)
    assert (meio[1].start.y, meio[1].end.y) == (70, 120)
