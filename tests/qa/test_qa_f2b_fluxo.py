"""FASE 2B (QA) — fluxo E2E do Modo Corte: importar (SVG + PDF + Texto...),
organizar, retocar manualmente (arrastar de VERDADE via mouse na view, girar
pelo atalho de teclado R de VERDADE) e exportar DXF.

Contrato sob teste: depois do retoque manual, self._layouts (fonte da
verdade) precisa bater tanto com o que a CENA do preview mostra quanto com o
que sai gravado no DXF. Ver docstring de cut_mode_dialog.py e
tests/presentation/test_cut_mode_manip.py.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.run_true_shape_nesting import placed_cut_contours  # noqa: E402
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.presentation.cut_mode_dialog import CutModeDialog  # noqa: E402
from PySide6.QtCore import Qt, QPointF  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

try:
    import fitz  # PyMuPDF: dev-only, so para gerar o PDF fixture do teste
except ImportError:  # pragma: no cover
    fitz = None

_XMLNS = 'xmlns="http://www.w3.org/2000/svg"'
_ARIAL = "C:/Windows/Fonts/arial.ttf"


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp):
    dlg = CutModeDialog(export_dxf=ExportDxfUseCase(DxfExporter()))
    dlg._seconds.setValue(0.5)  # tempo minimo: o teste valida o FLUXO
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


def _two_shapes_svg(tmp_path) -> str:
    path = tmp_path / "duas_formas.svg"
    path.write_text(
        f'<svg {_XMLNS} width="100mm" height="100mm" viewBox="0 0 100 100">'
        '<rect x="0" y="0" width="30" height="20"/>'
        '<rect x="60" y="0" width="20" height="20"/>'
        "</svg>",
        encoding="utf-8",
    )
    return str(path)


def _rect_pdf(tmp_path) -> str:
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.draw_rect(fitz.Rect(20, 20, 60, 50), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "peca.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _drag_via_mouse(dialog, qapp, gfx, dx: float, dy: float) -> None:
    """Arrasto de VERDADE: eventos de mouse na viewport da view, nao
    setPos() direto — prova que a cadeia mousePress/Move/Release da
    _ZoomView + _CutPieceItem chega ate _on_piece_moved."""
    dialog.resize(900, 600)
    dialog.show()
    qapp.processEvents()
    view = dialog._view
    view.fit()
    start_scene = gfx.sceneBoundingRect().center()
    end_scene = start_scene + QPointF(dx, dy)
    start = view.mapFromScene(start_scene)
    end = view.mapFromScene(end_scene)
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
    qapp.processEvents()
    QTest.mouseMove(view.viewport(), end)
    qapp.processEvents()
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, end)
    qapp.processEvents()


def _bbox(points):
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _expected_bboxes(dialog, layout):
    """A verdade: reconstrucao do contorno a partir de self._layouts (mesma
    receita do DXF e do preview, placed_cut_contours)."""
    by_id = {s.artwork_id: s for s in dialog._nested_shapes}
    return [
        _bbox(placed_cut_contours(by_id[item.artwork_id], item)[0].points)
        for item in layout.items
    ]


def _scene_bboxes(dialog):
    boxes = []
    for i in range(len(dialog._gfx_by_index)):
        gfx = dialog._gfx_by_index[i]
        r = gfx.path().boundingRect().translated(gfx.pos())
        boxes.append((r.left(), r.top(), r.right(), r.bottom()))
    return boxes


def _dxf_bboxes(path):
    boxes = []
    for poly in ezdxf.readfile(path).modelspace().query("LWPOLYLINE"):
        pts = poly.get_points()
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    return boxes


def _assert_dxf_matches_layout(dialog, layout, dxf_path) -> None:
    """DXF gravado bate com self._layouts, respeitando o espelhamento Y do
    DxfExporter (y' = altura_da_folha_no_dxf - y; ver dxf_exporter.py)."""
    expected = _expected_bboxes(dialog, layout)
    dxf_boxes = _dxf_bboxes(dxf_path)
    assert len(dxf_boxes) == len(expected)
    flip_h = max(b[3] for b in expected)
    for ex, dx in zip(expected, dxf_boxes):
        assert dx[0] == pytest.approx(ex[0], abs=1e-2)
        assert dx[2] == pytest.approx(ex[2], abs=1e-2)
        assert dx[1] == pytest.approx(flip_h - ex[3], abs=1e-2)
        assert dx[3] == pytest.approx(flip_h - ex[1], abs=1e-2)


@pytest.mark.skipif(fitz is None, reason="PyMuPDF indisponivel (dev-only, so para o teste)")
@pytest.mark.skipif(not os.path.exists(_ARIAL), reason="arial.ttf indisponivel neste ambiente")
def test_fluxo_completo_svg_pdf_texto_arrastar_girar_exportar(dialog, tmp_path, qapp):
    # 1) importar SVG com 2 formas
    dialog.add_vector_file(_two_shapes_svg(tmp_path))
    # 2) importar PDF vetorial
    dialog.add_vector_file(_rect_pdf(tmp_path))
    # 3) "Texto...": mesmo caminho que _pick_text chama depois do dialogo
    # modal aceitar (add_text), sem abrir o QDialog de verdade.
    dialog.add_text("LT", _ARIAL, 15.0)

    # quantidade 3 na peca do PDF, pela propria caixa de quantidade da UI
    dialog._list.setCurrentRow(1)
    dialog._qty.setValue(3)
    assert dialog._pieces[1].quantity == 3

    dialog._width.setValue(400.0)
    dialog._sheet_len.setValue(0.0)  # bobina: 1 folha so
    dialog.nest()

    total_bodies = sum(p.body_count for p in dialog._pieces)
    assert total_bodies == 2 + 3 + 2  # 2 svg + 3 pdf + 2 letras
    assert len(dialog._layouts) == 1
    assert not dialog._unplaced, f"nao deveria sobrar peca fora: {dialog._unplaced}"
    assert dialog._layouts[0].item_count == total_bodies

    # arrastar UMA peca via eventos de mouse de verdade na view
    gfx_drag = dialog._gfx_by_index[0]
    antes = dialog._layouts[0].items[0]
    _drag_via_mouse(dialog, qapp, gfx_drag, 15.0, 5.0)
    depois = dialog._layouts[0].items[0]
    assert (depois.position.x, depois.position.y) != (antes.position.x, antes.position.y)

    # girar OUTRA peca pelo atalho de teclado de verdade (R via QShortcut)
    gfx_rotate = dialog._gfx_by_index[1]
    gfx_rotate.setSelected(True)
    rot_antes = float(dialog._layouts[0].items[1].rotation)
    QTest.keyClick(dialog, Qt.Key_R)
    qapp.processEvents()
    rot_depois = float(dialog._layouts[0].items[1].rotation)
    assert rot_depois != pytest.approx(rot_antes)
    dialog.hide()

    out = str(tmp_path / "corte.dxf")
    result = dialog.export(out)
    assert result.dxf_paths == (out,)

    # o DXF bate com self._layouts (fonte da verdade) e com a cena do preview
    _assert_dxf_matches_layout(dialog, dialog._layouts[0], out)
    expected = _expected_bboxes(dialog, dialog._layouts[0])
    scene = _scene_bboxes(dialog)
    assert len(scene) == len(expected)
    for ex, sc in zip(expected, scene):
        assert sc == pytest.approx(ex, abs=1e-2)


def test_varias_folhas_cada_dxf_bate_com_a_sua_propria_folha(dialog, tmp_path, qapp):
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    piece.quantity = 4
    dialog._width.setValue(60.0)
    dialog._margin.setValue(0.0)
    dialog._gap.setValue(0.0)
    dialog._sheet_len.setValue(25.0)  # cabe 1 peca por folha
    dialog._rotate_mode.setCurrentIndex(0)  # sem giro: cenario previsivel
    dialog.nest()
    assert len(dialog._layouts) == 4

    # arrasta a peca da folha 1 (a exibida por padrao apos organizar)
    gfx0 = dialog._gfx_by_index[0]
    gfx0.setPos(5.0, 0.0)
    dialog._on_piece_moved(gfx0)

    # troca para a folha 2 e gira a peca de la pelo atalho R de verdade
    dialog._sheet_pick.setCurrentIndex(1)
    dialog.show()
    qapp.processEvents()
    gfx1 = dialog._gfx_by_index[0]  # mesmo indice local, folha diferente
    gfx1.setSelected(True)
    QTest.keyClick(dialog, Qt.Key_R)
    qapp.processEvents()
    dialog.hide()

    assert float(dialog._layouts[1].items[0].rotation) == pytest.approx(90.0)
    assert float(dialog._layouts[0].items[0].rotation) == pytest.approx(0.0)  # folha 1 intacta

    result = dialog.export(str(tmp_path / "nest.dxf"))
    assert len(result.dxf_paths) == 4
    for i, path in enumerate(result.dxf_paths):
        _assert_dxf_matches_layout(dialog, dialog._layouts[i], path)
