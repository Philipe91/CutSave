"""FASE 2B (QA) — cantos da E3 (retoque manual: arrastar/girar/desfazer).

Cada teste documenta o comportamento observado; nao julga o motor de
nesting (congelado). So vira xfail quando ha sobreposicao REAL indevida,
peca perdida ou corte errado.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.run_true_shape_nesting import placed_cut_contours  # noqa: E402
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.presentation.cut_mode_dialog import CutModeDialog  # noqa: E402
from app.shared.errors import ValidationError  # noqa: E402
from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_XMLNS = 'xmlns="http://www.w3.org/2000/svg"'


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp):
    dlg = CutModeDialog(export_dxf=ExportDxfUseCase(DxfExporter()))
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
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._width.setValue(200.0)
    dialog._sheet_len.setValue(sheet_len)
    dialog._rotate_mode.setCurrentIndex(0)  # sem giro: previsivel
    dialog.nest()
    return dialog._gfx_by_index[0]


# -- arrastar para fora da chapa -----------------------------------------------


def test_arrastar_para_fora_mantem_dentro_mesmo_partindo_de_peca_deslocada(dialog, tmp_path):
    # a peca[1] nao comeca em (0,0) — clamp precisa valer para qualquer
    # posicao de partida, nao so para a primeira peca da chapa.
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    piece.quantity = 2
    dialog._width.setValue(200.0)
    dialog._gap.setValue(5.0)
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()
    assert dialog._layouts[0].item_count == 2
    assert dialog._layouts[0].items[1].position.x > 0  # de fato deslocada

    gfx = dialog._gfx_by_index[1]
    eps = 1e-3
    gfx.setPos(-99_999.0, -99_999.0)
    dialog._on_piece_moved(gfx)
    item = dialog._layouts[0].items[1]
    assert item.position.x >= -eps and item.position.y >= -eps

    gfx.setPos(99_999.0, 99_999.0)
    dialog._on_piece_moved(gfx)
    item = dialog._layouts[0].items[1]
    bounds = gfx.bounds
    assert item.position.x + 40 <= bounds.right() + eps
    assert item.position.y + 20 <= bounds.bottom() + eps


# -- R com multiplas folhas -----------------------------------------------------


def test_r_gira_so_a_peca_da_folha_selecionada_sem_vazar_para_outra(dialog, tmp_path):
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    piece.quantity = 2
    dialog._width.setValue(60.0)
    dialog._margin.setValue(0.0)
    dialog._gap.setValue(0.0)
    dialog._sheet_len.setValue(25.0)
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()
    assert len(dialog._layouts) == 2

    dialog._sheet_pick.setCurrentIndex(1)  # mostra a folha 2
    gfx = dialog._gfx_by_index[0]
    gfx.setSelected(True)
    dialog._rotate_selected()

    assert float(dialog._layouts[1].items[0].rotation) == pytest.approx(90.0)
    assert float(dialog._layouts[0].items[0].rotation) == pytest.approx(0.0)  # folha 1 intacta
    assert dialog._undo[-1][0] == 1  # o desfazer sabe que o retoque foi na folha 2


# -- Ctrl+Z depois de trocar a folha exibida no combo --------------------------


def test_ctrl_z_apos_trocar_a_folha_exibida_desfaz_na_folha_certa(dialog, tmp_path):
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    piece.quantity = 2
    dialog._width.setValue(60.0)
    dialog._margin.setValue(0.0)
    dialog._gap.setValue(0.0)
    dialog._sheet_len.setValue(25.0)
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()
    assert len(dialog._layouts) == 2

    original = dialog._layouts[0].items[0]
    gfx0 = dialog._gfx_by_index[0]
    gfx0.setPos(3.0, 0.0)
    dialog._on_piece_moved(gfx0)  # retoque na folha 1 (a exibida)
    assert dialog._layouts[0].items[0] != original

    dialog._sheet_pick.setCurrentIndex(1)  # troca para a folha 2 sem mexer nela
    dialog._undo_manip()  # Ctrl+Z

    assert dialog._layouts[0].items[0] == original  # desfez na folha 1, nao na 2
    # a cena exibida acompanha: o combo volta sozinho pra folha onde o
    # desfazer aconteceu (senao o operador nao veria o resultado do Ctrl+Z)
    assert dialog._sheet_pick.currentIndex() == 0


# -- arrastar -> Organizar de novo -> Ctrl+Z ------------------------------------


def test_organizar_de_novo_limpa_a_pilha_de_desfazer_do_retoque_anterior(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._width.setValue(200.0)
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()
    gfx = dialog._gfx_by_index[0]
    gfx.setPos(10.0, 0.0)
    dialog._on_piece_moved(gfx)
    assert dialog._undo  # tem retoque na pilha

    dialog.nest()  # organiza de novo: novo calculo, novo layout
    assert not dialog._undo  # _apply_nest limpou a pilha antiga

    fresh = dialog._layouts[0].items[0]
    dialog._undo_manip()  # pilha vazia: nao pode ressuscitar o retoque velho
    assert dialog._layouts[0].items[0] == fresh


# -- mudar quantidade / remover peca depois de organizar ------------------------


def test_mudar_quantidade_apos_organizar_invalida_o_preview_e_bloqueia_exportar(dialog, tmp_path):
    # documentado: _on_qty_changed chama _invalidate() — o usuario NAO
    # consegue exportar um arranjo que nao reflete a quantidade nova.
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()
    assert dialog._layouts

    dialog._list.setCurrentRow(0)
    dialog._qty.setValue(5)

    assert dialog._layouts == ()
    with pytest.raises(ValidationError):
        dialog.export(str(tmp_path / "x.dxf"))


def test_remover_peca_apos_organizar_invalida_o_preview_e_bloqueia_exportar(dialog, tmp_path):
    # documentado: _remove_current tambem chama _invalidate() — a peca
    # removida nao pode "sobreviver" num DXF exportado depois sem reorganizar.
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20, "a.svg"))
    dialog.add_vector_file(_rect_svg(tmp_path, 30, 30, "b.svg"))
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()
    assert dialog._layouts

    dialog._list.setCurrentRow(0)
    dialog._remove_current()

    assert dialog._layouts == ()
    with pytest.raises(ValidationError):
        dialog.export(str(tmp_path / "x.dxf"))


# -- girar peca nao-quadrada perto da borda --------------------------------------


def test_girar_peca_retangular_no_canto_nao_vaza_a_chapa(dialog, tmp_path):
    gfx = _nest_one(dialog, tmp_path)  # 40x20, sem giro, chapa 200x100
    # empurra a peca pro canto: rotacionar 40x20 -> 20x40 nesse canto
    # estouraria a chapa sem um clamp POS-giro (so o clamp do arrasto nao basta).
    gfx.setPos(-99_999.0, -99_999.0)
    dialog._on_piece_moved(gfx)
    assert dialog._layouts[0].items[0].position.x == pytest.approx(0.0, abs=1e-3)
    assert dialog._layouts[0].items[0].position.y == pytest.approx(0.0, abs=1e-3)

    gfx.setSelected(True)
    dialog._rotate_selected()  # 40x20 -> 20x40 no mesmo canto

    shape = dialog._nested_shapes[0]
    item = dialog._layouts[0].items[0]
    outer = placed_cut_contours(shape, item)[0]
    bounds = gfx.bounds
    eps = 1e-3
    assert outer.origin.x >= bounds.left() - eps
    assert outer.origin.y >= bounds.top() - eps
    assert outer.origin.x + outer.size.width <= bounds.right() + eps
    assert outer.origin.y + outer.size.height <= bounds.bottom() + eps


# -- sobreposicao apos retoque manual --------------------------------------------


def test_sobreposicao_apos_retoque_manual_nao_bloqueia_exportar_documenta_comportamento(
    dialog, tmp_path
):
    # o retoque manual permite sobrepor pecas de proposito (docstring de
    # _CutPieceItem._clamped): e escolha do operador, o motor nao julga.
    # Este teste documenta que o DXF sai com as duas pecas, sobrepostas.
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    piece.quantity = 2
    dialog._width.setValue(200.0)
    dialog._rotate_mode.setCurrentIndex(0)
    dialog.nest()
    assert dialog._layouts[0].item_count == 2

    a = dialog._layouts[0].items[0]
    b_pos = dialog._layouts[0].items[1].position
    gfx_a = dialog._gfx_by_index[0]
    gfx_a.setPos(QPointF(b_pos.x - a.position.x, b_pos.y - a.position.y))
    dialog._on_piece_moved(gfx_a)

    moved_a = dialog._layouts[0].items[0]
    assert (moved_a.position.x, moved_a.position.y) == pytest.approx((b_pos.x, b_pos.y))

    out = str(tmp_path / "sobreposto.dxf")
    result = dialog.export(out)  # nao levanta: exportar nao julga o retoque
    assert result.dxf_paths == (out,)
    polys = ezdxf.readfile(out).modelspace().query("LWPOLYLINE")
    assert len(polys) == 2  # as duas pecas saem gravadas, sobrepostas
