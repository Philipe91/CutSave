"""TAREFA E3 — manipulacao manual e UI/UX da janela do Modo Corte.

Os testes de arrastar/girar chamam _on_piece_moved/_rotate_selected direto
(o que os handlers de mouse chamam): o contrato central e que o retoque
escreva em self._layouts — preview, DXF, Corel e SVG leem dali.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.presentation import faca_icons  # noqa: E402
from app.presentation.cut_mode_dialog import CutModeDialog  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_XMLNS = 'xmlns="http://www.w3.org/2000/svg"'


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp):
    dlg = CutModeDialog(export_dxf=ExportDxfUseCase(DxfExporter()))
    # tempo minimo: o teste valida o FLUXO, nao a qualidade do encaixe.
    dlg._seconds.setValue(0.5)
    yield dlg
    dlg.deleteLater()


def _rect_svg(tmp_path, w: float, h: float, name: str = "peca.svg") -> str:
    path = tmp_path / name
    path.write_text(
        f'<svg {_XMLNS} width="100mm" height="100mm" viewBox="0 0 100 100">'
        f'<rect x="0" y="0" width="{w}" height="{h}"/></svg>',
        encoding="utf-8",
    )
    return str(path)


def _nest_one(dialog, tmp_path, *, sheet_len: float = 100.0):
    """Um retangulo 40x20 organizado em cenario deterministico (sem giro)."""
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._width.setValue(200.0)
    dialog._sheet_len.setValue(sheet_len)
    dialog._rotate_mode.setCurrentIndex(0)  # Sem giro: previsivel
    dialog.nest()
    return dialog._gfx_by_index[(0, 0)]  # chave (chapa, indice) desde 4751f08


# -- Missao 1: mover e girar escrevem em self._layouts ------------------------


def test_arrastar_peca_atualiza_a_posicao_no_layout(dialog, tmp_path):
    gfx = _nest_one(dialog, tmp_path)
    antes = dialog._layouts[0].items[0].position
    gfx.setPos(7.0, 3.0)
    dialog._on_piece_moved(gfx)  # o que o soltar do mouse chama
    depois = dialog._layouts[0].items[0].position
    assert (depois.x, depois.y) == pytest.approx((antes.x + 7.0, antes.y + 3.0))
    # a cena volta a espelhar o layout: caminho reconstruido, delta zerado
    assert gfx.pos().isNull()


def test_girar_atualiza_a_rotacao_no_layout(dialog, tmp_path):
    gfx = _nest_one(dialog, tmp_path)
    gfx.setSelected(True)
    dialog._rotate_selected()
    # combo em "Sem giro" (passo 0): o giro MANUAL nao pode ficar refem do
    # parametro do nesting — cai no passo de 90°
    assert float(dialog._layouts[0].items[0].rotation) == pytest.approx(90.0)
    dialog._rotate_selected()
    assert float(dialog._layouts[0].items[0].rotation) == pytest.approx(180.0)


def test_girar_sem_selecao_nao_faz_nada(dialog, tmp_path):
    _nest_one(dialog, tmp_path)
    antes = dialog._layouts
    dialog._rotate_selected()
    assert dialog._layouts == antes


def test_dxf_apos_arrastar_reflete_a_nova_posicao(dialog, tmp_path):
    # prova de que exportacao e preview NAO divergiram: o DXF gravado depois
    # do arrasto sai deslocado exatamente pelo delta do arrasto.
    gfx = _nest_one(dialog, tmp_path)
    antes = str(tmp_path / "antes.dxf")
    dialog.export(antes)
    gfx.setPos(10.0, 0.0)  # so em X: o espelhamento vertical do DXF nao entra
    dialog._on_piece_moved(gfx)
    depois = str(tmp_path / "depois.dxf")
    dialog.export(depois)

    def min_x(path: str) -> float:
        pts = ezdxf.readfile(path).modelspace().query("LWPOLYLINE")[0].get_points()
        return min(p[0] for p in pts)

    assert min_x(depois) == pytest.approx(min_x(antes) + 10.0)


def test_peca_nao_sai_da_chapa_configurada(dialog, tmp_path):
    gfx = _nest_one(dialog, tmp_path, sheet_len=100.0)
    eps = 1e-6  # folga de ponto flutuante do clamp (nanometros)
    gfx.setPos(-500.0, -500.0)  # itemChange deve devolver para dentro
    caixa = gfx.path().boundingRect().translated(gfx.pos())
    assert caixa.left() >= -eps and caixa.top() >= -eps
    gfx.setPos(5000.0, 5000.0)
    caixa = gfx.path().boundingRect().translated(gfx.pos())
    assert caixa.right() <= 200.0 + eps and caixa.bottom() <= 100.0 + eps


def test_ctrl_z_desfaz_o_ultimo_retoque(dialog, tmp_path):
    gfx = _nest_one(dialog, tmp_path)
    original = dialog._layouts[0].items[0]
    gfx.setPos(10.0, 0.0)
    dialog._on_piece_moved(gfx)
    assert dialog._layouts[0].items[0] != original
    dialog._undo_manip()  # o que o Ctrl+Z chama
    assert dialog._layouts[0].items[0] == original
    dialog._undo_manip()  # pilha vazia: nao explode
    assert dialog._layouts[0].items[0] == original


# -- Missao 2: UI/UX — guia do proximo passo possivel -------------------------


def test_dialogo_vazio_mostra_guia_do_passo_0(dialog):
    assert dialog._view.empty_hint == "Adicione um arquivo (SVG/PDF) ou um texto"
    assert dialog._view.empty_step == 0
    assert not faca_icons.cut_steps_pixmap(0).isNull()  # faixa dos 3 passos


def test_com_peca_o_guia_vira_passo_1(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    assert dialog._view.empty_hint == "Clique em Organizar"
    assert dialog._view.empty_step == 1
    dialog.nest()
    assert dialog._view.empty_hint == ""  # organizado: o arranjo fala por si


def test_guia_nunca_aponta_para_botao_desabilitado(dialog, tmp_path):
    # sem peca: Organizar esta DESABILITADO, entao nem o status nem o guia
    # podem mandar clicar nele (era o defeito original da janela)
    assert not dialog._btn_nest.isEnabled()
    guia = dialog._status.text() + dialog._view.empty_hint
    assert "Organizar" not in guia
    assert "Adicione" in guia
    # com peca: agora sim, e o botao esta habilitado
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    assert dialog._btn_nest.isEnabled()
    assert "Organizar" in dialog._view.empty_hint


def test_acao_primaria_acompanha_o_passo(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    assert dialog._btn_nest.property("accent") == "true"  # passo: Organizar
    assert dialog._btn_export.property("accent") == "false"
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()
    assert dialog._btn_export.property("accent") == "true"  # passo: Exportar
    assert dialog._btn_nest.property("accent") == "false"


def test_botao_desabilitado_diz_o_que_o_destrava(dialog, tmp_path):
    assert "Organizar" in dialog._btn_export.toolTip()  # "Disponivel depois de"
    assert "Organizar" in dialog._btn_corel.toolTip()
    assert "adicionar" in dialog._btn_nest.toolTip()
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()
    assert "Disponível" not in dialog._btn_export.toolTip()
    assert "Disponível" not in dialog._btn_rotate.toolTip()


def test_tooltip_do_giro_nao_repete_o_mito_do_mais_fino(dialog):
    # medido em 22/07: mais fino encaixa PIOR no orcamento padrao de 10s
    tip = dialog._rotate_mode.toolTip()
    assert "encaixa melhor, porém demora mais" not in tip
    assert "90°" in tip
