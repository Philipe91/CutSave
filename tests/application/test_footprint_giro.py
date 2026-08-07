"""Geometria da peca GIRADA — a base para o nesting do Modo Impressao girar.

O `MaxRectsPacker` ja sabe girar (allow_rotate), mas a rotacao esta desligada
porque quem desenha a peca — preview, PDF de impressao, faca e DXF — posiciona
a geometria com uma translacao simples e ignora `PlacedItem.rotation`. Ligar a
rotacao antes de consertar isso desenharia a peca SEM girar dentro do espaco
que o encaixe reservou GIRADO: pecas sobrepostas na chapa, sem erro nenhum.

Estes testes travam o contrato que todos vao usar:
  - a 90/270 os lados trocam;
  - sem giro, a conta e exatamente a de antes (layout antigo nao muda 1 mm);
  - girar 4x volta ao inicio;
  - o giro nunca tira a peca do espaco reservado para ela.
"""

from __future__ import annotations

import pytest

from app.application.footprint import (
    artwork_footprint,
    mapeador_da_peca,
    pontos_na_chapa,
    tamanho_ocupado,
)
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.placement import PlacedItem, Rotation


def _faca(w, h, off=0.0):
    return CutContour([
        Point2D(-off, -off), Point2D(w + off, -off),
        Point2D(w + off, h + off), Point2D(-off, h + off),
    ])


def _art(w=100.0, h=40.0, off=None):
    return Artwork(
        id="a0", name="a0", file_format=FileFormat.PDF,
        size=Size(w, h), kind=ArtKind.RETANGULAR,
        cut_contour=_faca(w, h, off) if off is not None else None,
    )


def test_sem_giro_os_lados_ficam_como_estao():
    assert tamanho_ocupado(_art(), 0) == Size(100.0, 40.0)


@pytest.mark.parametrize("graus", [90, 270])
def test_a_90_e_270_os_lados_trocam(graus):
    assert tamanho_ocupado(_art(), graus) == Size(40.0, 100.0)


def test_a_180_os_lados_ficam_como_estao():
    assert tamanho_ocupado(_art(), 180) == Size(100.0, 40.0)


def test_o_giro_conta_a_faca_junto():
    """A faca com sangria e maior que a arte: e ela que manda no espaco."""
    art = _art(100.0, 40.0, off=5.0)
    fp = artwork_footprint(art)
    assert (fp.min_x, fp.min_y, fp.max_x, fp.max_y) == (-5.0, -5.0, 105.0, 45.0)
    assert tamanho_ocupado(art, 0) == Size(110.0, 50.0)
    assert tamanho_ocupado(art, 90) == Size(50.0, 110.0)


def test_sem_giro_a_conta_e_a_de_sempre():
    """Regressao: layout antigo nao pode mudar 1 mm por causa desta base."""
    art = _art(100.0, 40.0, off=3.0)
    fp = artwork_footprint(art)
    mapear = mapeador_da_peca(art, 0)
    for p in art.cut_contour.points:
        esperado = Point2D(p.x - fp.min_x, p.y - fp.min_y)
        obtido = mapear(p)
        assert obtido.x == pytest.approx(esperado.x)
        assert obtido.y == pytest.approx(esperado.y)


@pytest.mark.parametrize("graus", [0, 90, 180, 270])
def test_a_peca_girada_cabe_exatamente_no_espaco_reservado(graus):
    """O contrato que impede peça sobreposta: o que o nesting reserva
    (tamanho_ocupado) tem de conter TODA a geometria mapeada, sem sobra."""
    art = _art(100.0, 40.0, off=3.0)
    ocupado = tamanho_ocupado(art, graus)
    mapear = mapeador_da_peca(art, graus)
    pontos = [mapear(p) for p in art.cut_contour.points]
    pontos += [
        mapear(Point2D(x, y))
        for x in (0.0, art.size.width) for y in (0.0, art.size.height)
    ]
    xs = [p.x for p in pontos]
    ys = [p.y for p in pontos]
    assert min(xs) == pytest.approx(0.0, abs=1e-9)
    assert min(ys) == pytest.approx(0.0, abs=1e-9)
    assert max(xs) == pytest.approx(ocupado.width, abs=1e-9)
    assert max(ys) == pytest.approx(ocupado.height, abs=1e-9)


@pytest.mark.parametrize("graus", [0, 90, 180, 270])
def test_o_giro_nao_deforma_a_peca(graus):
    """Invariante que pega qualquer erro de escala, espelho ou cisalhamento:
    a distância entre dois pontos quaisquer tem de sobreviver ao giro."""
    art = _art(100.0, 40.0, off=3.0)
    mapear = mapeador_da_peca(art, graus)
    amostra = [Point2D(0.0, 0.0), Point2D(100.0, 0.0), Point2D(37.0, 12.5),
               Point2D(-3.0, 45.0)]
    for i, a in enumerate(amostra):
        for b in amostra[i + 1:]:
            antes = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
            ma, mb = mapear(a), mapear(b)
            depois = ((ma.x - mb.x) ** 2 + (ma.y - mb.y) ** 2) ** 0.5
            assert depois == pytest.approx(antes, abs=1e-9)


def test_giro_invalido_e_tratado_como_zero():
    """Angulo livre vem do Modo Corte e tem caminho proprio; aqui vira 0."""
    assert tamanho_ocupado(_art(), 37.5) == tamanho_ocupado(_art(), 0)
    assert tamanho_ocupado(_art(), None) == tamanho_ocupado(_art(), 0)


def test_pontos_na_chapa_soma_a_posicao_do_item():
    art = _art(100.0, 40.0)
    item = PlacedItem("a0", Point2D(200.0, 50.0), Rotation.CW90)
    (canto,) = pontos_na_chapa(art, item, [Point2D(0.0, 0.0)])
    # a 90, o canto superior esquerdo art-local vai para o superior DIREITO
    assert canto.x == pytest.approx(200.0 + 40.0)
    assert canto.y == pytest.approx(50.0)


def test_pontos_na_chapa_aplica_o_deslocamento_entre_chapas():
    art = _art(100.0, 40.0)
    item = PlacedItem("a0", Point2D(10.0, 0.0))
    (p,) = pontos_na_chapa(art, item, [Point2D(0.0, 0.0)], dx=1300.0)
    assert p.x == pytest.approx(1310.0)
