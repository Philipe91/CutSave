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


# ---------------------------------------------------------------------------
# Espelho (1.1). Ordem canonica do PrintNest: espelhar PRIMEIRO, girar depois.
# ---------------------------------------------------------------------------

def test_espelho_horizontal_reflete_em_x():
    # caixa 10x4: (x, y) -> (W - x, y)
    out, w, h = crop_and_rotate_contour(_L(10, 4), 0, 0, 10, 4, mirror="h")
    assert (w, h) == (10, 4), "espelhar NAO troca largura por altura"
    assert [(p.x, p.y) for p in out.points] == [(9, 2), (0, 0), (0, 4), (10, 4)]


def test_espelho_vertical_reflete_em_y():
    out, w, h = crop_and_rotate_contour(_L(10, 4), 0, 0, 10, 4, mirror="v")
    assert (w, h) == (10, 4)
    assert [(p.x, p.y) for p in out.points] == [(1, 2), (10, 4), (10, 0), (0, 0)]


@pytest.mark.parametrize("eixo", ["h", "v", "hv"])
@pytest.mark.parametrize("rotacao", [0, 90, 180, 270])
def test_espelhar_duas_vezes_volta_ao_original(eixo, rotacao):
    """Espelho e involutivo: aplicar duas vezes tem de devolver o contorno de
    partida, em qualquer rotacao. Sem isso o botao vira armadilha — o operador
    clica de novo para desfazer e recebe outra coisa."""
    original = crop_and_rotate_contour(_L(10, 4), 0, rotacao, 10, 4)[0]
    espelhado, w, h = crop_and_rotate_contour(_L(10, 4), 0, rotacao, 10, 4, mirror=eixo)
    # espelhar o resultado de volta, no MESMO referencial em que ele foi gerado
    de_volta = crop_and_rotate_contour(
        CutContour(list(espelhado.points)), 0, 0, w, h,
        mirror=_eixo_na_tela(eixo, rotacao),
    )[0]
    assert [(round(p.x, 6), round(p.y, 6)) for p in de_volta.points] == [
        (round(p.x, 6), round(p.y, 6)) for p in original.points
    ]


def _eixo_na_tela(eixo: str, rotacao: int) -> str:
    """Depois de girar 90/270 o eixo do espelho aparece trocado na tela."""
    if rotacao % 180 == 0 or eixo == "hv":
        return eixo
    return {"h": "v", "v": "h"}[eixo]


def test_a_ordem_espelhar_depois_girar_e_a_que_vale():
    """Trava a ORDEM CANONICA com um caso onde as duas ordens divergem.

    Espelhar-e-girar != girar-e-espelhar. A ordem esta implementada num lugar
    so (`crop_and_rotate_contour`); este teste existe para que ela seja uma
    invariante, e nao uma intencao escrita em docstring. Se dois consumidores
    divergirem na ordem, a faca sai fora da arte.
    """
    # espelha em H e depois gira 90 (o que a funcao faz)
    canonico = crop_and_rotate_contour(_L(10, 4), 0, 90, 10, 4, mirror="h")[0]

    # a ordem INVERSA: gira 90 primeiro, espelha em H depois
    girado, w, h = crop_and_rotate_contour(_L(10, 4), 0, 90, 10, 4)
    invertido = crop_and_rotate_contour(
        CutContour(list(girado.points)), 0, 0, w, h, mirror="h"
    )[0]

    canon = [(p.x, p.y) for p in canonico.points]
    inver = [(p.x, p.y) for p in invertido.points]
    assert canon != inver, (
        "o caso de teste deixou de distinguir as duas ordens — troque a figura"
    )
    # e o resultado canonico e ESTE, ponto a ponto:
    # (1,2) espelha para (9,2) na caixa 10x4 e gira 90 -> (H-y, x) = (2, 9)
    assert canon == [(2, 9), (4, 0), (0, 0), (0, 10)]
