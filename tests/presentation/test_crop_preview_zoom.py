"""Zoom na pre-visualizacao do RECORTAR (07/08/2026).

Pedido do Philipe. Sem zoom, recortar 2 mm de uma arte grande era chute: a
borda do recorte vira meio pixel na tela e nao da para ver o que esta sendo
cortado.

Tudo passa por CropPreview._geom(), entao desenho, posicao das bordas e o
arrasto delas acompanham o zoom sozinhos — estes testes cobrem exatamente
esse contrato, alem do zoom em si.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QPixmap, QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.presentation.main_window import CropPreview  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def preview(qapp):
    p = CropPreview()
    p.resize(400, 400)
    pm = QPixmap(200, 100)
    pm.fill(Qt.white)
    p.set_page(pm, 200.0, 100.0)
    return p


def _roda(preview, delta, x=200.0, y=200.0):
    preview.wheelEvent(
        QWheelEvent(
            QPointF(x, y), QPointF(x, y), QPoint(0, 0), QPoint(0, delta),
            Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False,
        )
    )


def test_nasce_enquadrado(preview):
    assert preview.zoom() == 1.0


def test_roda_para_cima_aproxima(preview):
    _roda(preview, 120)
    assert preview.zoom() > 1.0


def test_nao_afasta_alem_do_enquadrado(preview):
    """Afastar mais que a pagina inteira so afasta do que interessa."""
    for _ in range(5):
        _roda(preview, -120)
    assert preview.zoom() == 1.0


def test_tem_teto_de_zoom(preview):
    for _ in range(60):
        _roda(preview, 120)
    assert preview.zoom() == pytest.approx(CropPreview._ZOOM_MAX)


def test_duplo_clique_volta_a_enquadrar(preview):
    _roda(preview, 120)
    _roda(preview, 120)
    assert preview.zoom() > 1.0
    preview.mouseDoubleClickEvent(None)
    assert preview.zoom() == 1.0


def test_o_ponto_sob_o_cursor_nao_foge(preview):
    """Ancorar no cursor e o que faz o zoom ser util: aproximar da BORDA que
    se quer recortar, e nao do centro da pagina."""
    x, y = 120.0, 150.0
    ox, oy, dw, dh, _mx, _my = preview._geom()
    antes = ((x - ox) / dw, (y - oy) / dh)
    _roda(preview, 120, x, y)
    ox2, oy2, dw2, dh2, _m2, _m3 = preview._geom()
    depois = ((x - ox2) / dw2, (y - oy2) / dh2)
    assert depois[0] == pytest.approx(antes[0], abs=1e-6)
    assert depois[1] == pytest.approx(antes[1], abs=1e-6)


def test_pagina_nova_volta_enquadrada(preview):
    _roda(preview, 120)
    pm = QPixmap(300, 300)
    pm.fill(Qt.white)
    preview.set_page(pm, 300.0, 300.0)
    assert preview.zoom() == 1.0


def test_as_bordas_do_recorte_acompanham_o_zoom(preview):
    """O contrato que importa: a borda desenhada continua sobre a mesma
    posicao FISICA da pagina depois de aproximar."""
    preview.set_crop(10.0, 0.0, 0.0, 0.0)  # 10 mm da esquerda
    bordas, (ox, _oy, dw, _dh, _mx, _my) = preview._edges()
    fracao_antes = (bordas["l"] - ox) / dw
    _roda(preview, 120)
    bordas2, (ox2, _oy2, dw2, _dh2, _m2, _m3) = preview._edges()
    fracao_depois = (bordas2["l"] - ox2) / dw2
    assert fracao_depois == pytest.approx(fracao_antes, abs=1e-9)
    assert preview.crop()[0] == pytest.approx(10.0), "o zoom nao pode mexer no mm"


# ---- indicador de carregamento nas exportacoes (07/08/2026) ----------------
# "falta tmb o icone de carregamento ao exportar" — so a exportacao de IMAGEM
# tinha indicador; PDF, faca e DXF mostravam apenas o cursor de espera, e em
# arquivo pesado nao dava para saber se o programa trabalhava ou travara.

def test_toda_exportacao_mostra_e_esconde_o_indicador(qapp, monkeypatch):
    """O contrato do _exportando: liga ao entrar, desliga ao sair — inclusive
    quando a exportacao falha no meio."""
    from app.presentation.main_window import MainWindow

    eventos = []

    class _Falso:
        def start_progress(self, texto=""):
            eventos.append(("liga", texto))

        def end_progress(self):
            eventos.append(("desliga", None))

    janela = MainWindow.__new__(MainWindow)  # sem construir a UI inteira
    janela._status_ctl = _Falso()

    with janela._exportando("Exportando DXF de corte…"):
        pass
    assert eventos == [("liga", "Exportando DXF de corte…"), ("desliga", None)]

    eventos.clear()
    with pytest.raises(RuntimeError):
        with janela._exportando("Exportando…"):
            raise RuntimeError("disco cheio")
    assert eventos[-1] == ("desliga", None), (
        "indicador ficou aceso depois de a exportação falhar"
    )
