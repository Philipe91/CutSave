import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.presentation.cut_mode_dialog import CutModeDialog  # noqa: E402
from app.shared.errors import ValidationError  # noqa: E402
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


def _svg(tmp_path, body: str, name: str = "peca.svg") -> str:
    path = tmp_path / name
    path.write_text(
        f'<svg {_XMLNS} width="100mm" height="100mm" viewBox="0 0 100 100">{body}</svg>',
        encoding="utf-8",
    )
    return str(path)


def _rect_svg(tmp_path, w: float, h: float, name: str = "peca.svg") -> str:
    return _svg(tmp_path, f'<rect x="0" y="0" width="{w}" height="{h}"/>', name)


def test_importa_svg_e_lista_a_peca(dialog, tmp_path):
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    assert piece.name == "peca.svg"
    assert len(piece.shapes) == 1
    assert dialog._list.count() == 1
    # sem Organizar nao da para exportar
    assert not dialog._btn_export.isEnabled()


def test_svg_sem_forma_fechada_avisa(dialog, tmp_path):
    with pytest.raises(ValidationError):
        dialog.add_vector_file(_svg(tmp_path, "<!-- vazio -->"))


def test_quantidade_multiplica_os_corpos(dialog, tmp_path):
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    piece.quantity = 3
    assert piece.body_count == 3
    assert len(dialog._all_shapes()) == 3


def test_ids_nao_colidem_entre_arquivos(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20, "a.svg"))
    dialog.add_vector_file(_rect_svg(tmp_path, 30, 30, "b.svg"))
    ids = [s.artwork_id for s in dialog._all_shapes()]
    assert ids == sorted(set(ids)) and len(ids) == 2


def test_sem_rotacao_so_zero_grau(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._rotate_mode.setCurrentIndex(0)  # Sem giro
    assert dialog._all_shapes()[0].rotations == (0.0,)


def test_giro_fino_gera_angulos_de_45(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._rotate_mode.setCurrentIndex(2)  # Fino (45°)
    assert dialog._all_shapes()[0].rotations == tuple(float(a) for a in range(0, 360, 45))


def test_status_mostra_aproveitamento_da_chapa(dialog, tmp_path):
    # estilo eCut: tamanho do bloco ocupado, % da chapa e aproveitamento
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._width.setValue(100.0)
    dialog.nest()
    text = dialog._status.text()
    assert "Bloco" in text
    assert "aproveitamento" in text
    assert "%" in text


def test_organizar_sem_peca_e_erro(dialog):
    with pytest.raises(ValidationError):
        dialog.nest()


def test_exportar_sem_organizar_e_erro(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    with pytest.raises(ValidationError):
        dialog.export(str(tmp_path / "x.dxf"))


def test_organizar_desenha_preview_e_exporta_o_mesmo_layout(dialog, tmp_path):
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    piece.quantity = 2
    dialog._width.setValue(200.0)
    dialog.nest()

    assert dialog._layouts and dialog._layouts[0].item_count == 2
    assert dialog._btn_export.isEnabled()
    assert dialog._scene.items()  # chapa + pecas desenhadas

    out = str(tmp_path / "corte.dxf")
    layouts_antes = dialog._layouts
    result = dialog.export(out)
    # exportar NAO pode recalcular: e o mesmo objeto de layout do preview
    assert dialog._layouts is layouts_antes
    assert result.dxf_paths == (out,)
    assert len(ezdxf.readfile(out).modelspace().query("LWPOLYLINE")) == 2


def test_mudar_parametro_invalida_o_preview(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog.nest()
    assert dialog._layouts
    dialog._gap.setValue(9.0)
    assert dialog._layouts == ()
    assert not dialog._btn_export.isEnabled()
    assert not dialog._scene.items()


def test_peca_maior_que_a_chapa_aparece_em_nao_coube(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 90, 90))
    dialog._width.setValue(30.0)
    dialog._rotate_mode.setCurrentIndex(0)  # Sem giro
    dialog.nest()
    assert dialog._unplaced
    assert "não coube" in dialog._status.text()


def test_previa_da_biblioteca_mostra_a_peca_selecionada(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    assert dialog._piece_scene.items()  # janelinha desenhou o corpo
    dialog._remove_current()
    assert not dialog._piece_scene.items()


def test_copias_compartilham_o_id_para_reusar_o_cache_de_nfp(dialog, tmp_path):
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    piece.quantity = 3
    ids = [s.artwork_id for s in dialog._all_shapes()]
    assert len(ids) == 3
    assert len(set(ids)) == 1  # mesmo id = NFP calculado uma vez so


def test_mensagens_rotativas_durante_o_carregamento(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._set_busy(True)
    assert dialog._tip_timer.isActive()
    first = dialog._status.text()
    dialog._next_tip()
    assert dialog._status.text() != first  # a mensagem roda
    dialog._set_busy(False)
    assert not dialog._tip_timer.isActive()


def test_botao_organizar_roda_em_thread_com_barra_de_carregamento(dialog, tmp_path, qapp):
    # O clique nao pode congelar a janela: a barra aparece, os controles
    # travam, e o resultado chega pelo sinal da thread.
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    dialog._on_nest()
    assert not dialog._progress.isHidden()
    assert not dialog._btn_nest.isEnabled()  # nao dispara duas vezes

    deadline = time.time() + 30
    while dialog._nest_thread is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)

    assert dialog._nest_thread is None, "thread do nesting nao terminou em 30s"
    assert dialog._layouts  # resultado aplicado na UI
    assert dialog._progress.isHidden()
    assert dialog._btn_export.isEnabled()


def test_enviar_para_corel_exige_organizar_e_gera_svg(dialog, tmp_path):
    dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    assert not dialog._btn_corel.isEnabled()  # sem Organizar nao envia
    with pytest.raises(ValidationError):
        dialog.export_svg(str(tmp_path / "x.svg"))
    dialog.nest()
    assert dialog._btn_corel.isEnabled()
    out = dialog.export_svg(str(tmp_path / "layout.svg"))
    svg = (tmp_path / "layout.svg").read_text(encoding="utf-8")
    assert out.endswith("layout.svg")
    assert svg.count("<path") == 1  # a peca organizada, em curva magenta
    assert 'stroke="#ff00ff"' in svg


def test_open_with_file_importa_e_ja_organiza(dialog, tmp_path, qapp):
    # fluxo da macro do Corel (--modo-corte): a janela abre ja trabalhando
    dialog.open_with_file(_rect_svg(tmp_path, 40, 20))
    assert dialog._list.count() == 1
    assert dialog._nest_thread is not None  # organizando sozinho

    deadline = time.time() + 30
    while dialog._nest_thread is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert dialog._layouts
    assert dialog._btn_export.isEnabled()


def test_varias_folhas_geram_um_dxf_por_folha(dialog, tmp_path):
    piece = dialog.add_vector_file(_rect_svg(tmp_path, 40, 20))
    piece.quantity = 2
    dialog._width.setValue(60.0)
    dialog._margin.setValue(0.0)
    dialog._gap.setValue(0.0)
    dialog._sheet_len.setValue(25.0)  # cabe uma peca por folha
    dialog._rotate_mode.setCurrentIndex(0)  # Sem giro
    dialog.nest()
    assert len(dialog._layouts) == 2

    result = dialog.export(str(tmp_path / "nest.dxf"))
    assert [os.path.basename(p) for p in result.dxf_paths] == [
        "nest_folha1.dxf",
        "nest_folha2.dxf",
    ]
