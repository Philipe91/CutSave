import pytest
from app.domain.cut.contour_ops import (
    crop_and_rotate_contour,
    offset_contour,
    smooth_contour,
)
from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


def _square(side):
    return CutContour([
        Point2D(0, 0), Point2D(side, 0), Point2D(side, side), Point2D(0, side)
    ])


def _L(w, h):
    # marcador assimetrico: ponto perto do canto superior-esquerdo de uma caixa w x h
    return CutContour([
        Point2D(1, 2), Point2D(w, 0), Point2D(w, h), Point2D(0, h)
    ])


def test_offset_zero_devolve_o_mesmo_contorno():
    c = _square(10)
    assert offset_contour(c, 0) is c


def test_offset_positivo_cresce():
    out = offset_contour(_square(10), 2)
    assert out.size.width == pytest.approx(14, abs=0.01)
    assert out.size.height == pytest.approx(14, abs=0.01)


def test_offset_negativo_encolhe():
    out = offset_contour(_square(10), -2)
    assert out.size.width == pytest.approx(6, abs=0.01)


def test_encolher_demais_levanta():
    with pytest.raises(ValidationError):
        offset_contour(_square(10), -10)


def test_offset_cantos_round_miter_bevel():
    # round arredonda (arco = muitos pontos); miter = ponta (poucos); bevel = chanfro.
    r_round = offset_contour(_square(10), 2, "round")
    r_miter = offset_contour(_square(10), 2, "miter")
    r_bevel = offset_contour(_square(10), 2, "bevel")
    assert len(r_miter.points) < len(r_round.points)   # ponta tem menos nos que arco
    assert len(r_bevel.points) <= len(r_round.points)
    # miter num quadrado = quadrado maior (14x14), cantos vivos
    assert r_miter.size.width == pytest.approx(14, abs=0.01)


def test_suavizar_zero_nao_altera():
    c = _square(10)
    assert smooth_contour(c, 0) is c


def test_suavizar_arredonda_cantos_e_aumenta_pontos():
    out = smooth_contour(_square(10), 1)
    # Chaikin: cada iteracao dobra os pontos (4 -> 8)
    assert len(out.points) == 8
    # nenhum ponto fica no canto original (0,0): os cantos foram cortados
    assert all(not (p.x == 0 and p.y == 0) for p in out.points)


def test_suavizar_mais_iteracoes_mais_pontos():
    p1 = len(smooth_contour(_square(10), 1).points)
    p2 = len(smooth_contour(_square(10), 2).points)
    assert p2 > p1


def test_suavizar_mantem_dentro_da_caixa_original():
    out = smooth_contour(_square(10), 3)
    xs = [p.x for p in out.points]
    ys = [p.y for p in out.points]
    assert min(xs) >= -0.001 and max(xs) <= 10.001
    assert min(ys) >= -0.001 and max(ys) <= 10.001


def test_crop_and_rotate_sem_efeito():
    c = _L(10, 4)
    out, w, h = crop_and_rotate_contour(c, 0, 0, 10, 4)
    assert (w, h) == (10, 4)
    assert [(p.x, p.y) for p in out.points] == [(1, 2), (10, 0), (10, 4), (0, 4)]


def test_crop_translada_e_encolhe_a_caixa():
    out, w, h = crop_and_rotate_contour(_L(10, 4), 1, 0, 10, 4)
    assert (w, h) == (8, 2)
    # cada ponto desloca -crop em x e y
    assert [(p.x, p.y) for p in out.points] == [(0, 1), (9, -1), (9, 3), (-1, 3)]


@pytest.mark.parametrize(
    "rotation,esperado_size",
    [(90, (4, 10)), (180, (10, 4)), (270, (4, 10))],
)
def test_crop_and_rotate_troca_dimensoes_em_90_e_270(rotation, esperado_size):
    _out, w, h = crop_and_rotate_contour(_L(10, 4), 0, rotation, 10, 4)
    assert (w, h) == esperado_size


def test_rotacao_90_segue_convencao_qtransform():
    # caixa 10x4 (W x H): (x, y) -> (H - y, x)
    out, w, h = crop_and_rotate_contour(_L(10, 4), 0, 90, 10, 4)
    assert (w, h) == (4, 10)
    assert [(p.x, p.y) for p in out.points] == [(2, 1), (4, 10), (0, 10), (0, 0)]


def test_rotacao_180():
    # (x, y) -> (W - x, H - y)
    out, w, h = crop_and_rotate_contour(_L(10, 4), 0, 180, 10, 4)
    assert (w, h) == (10, 4)
    assert [(p.x, p.y) for p in out.points] == [(9, 2), (0, 4), (0, 0), (10, 0)]


def test_rotacao_270():
    # (x, y) -> (W - x sobre o eixo trocado): (y, W - x)
    out, w, h = crop_and_rotate_contour(_L(10, 4), 0, 270, 10, 4)
    assert (w, h) == (4, 10)
    assert [(p.x, p.y) for p in out.points] == [(2, 9), (0, 0), (4, 0), (4, 10)]
