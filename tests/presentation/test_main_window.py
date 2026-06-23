import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ezdxf  # noqa: E402
import fitz  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    RunProductionPipelineUseCase,
)
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pymupdf_print_exporter import PyMuPdfPrintExporter  # noqa: E402
from app.infrastructure.importers.pymupdf_importer import PyMuPdfImporter  # noqa: E402
from app.infrastructure.rendering.pymupdf_renderer import PyMuPdfPageRenderer  # noqa: E402
from app.presentation.main_window import MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _two_page_pdf(tmp_path):
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=200, height=100)  # ~70.5 x 35.3 mm
        page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "fonte.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _window(tmp_path):
    store = SettingsStore(tmp_path / "config.json")
    settings = store.load_or_create()
    pipeline = RunProductionPipelineUseCase(ImportPdfUseCase(PyMuPdfImporter()))
    return MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PyMuPdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PyMuPdfPageRenderer(),
        store,
        settings,
    )


def test_fluxo_completo_da_ui(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])

    window.generate(blocking=True)  # roda o pipeline sincronamente

    assert window._result is not None
    assert sum(s.item_count for s in window._result.sheets) == 2
    # preview: material + 2 imagens (arte) + 2 facas
    assert len(window._scene.items()) >= 5
    # a arte foi rasterizada e cacheada (2 paginas distintas)
    assert len(window._pixmaps) == 2

    pdf_out = tmp_path / "IMPRESSAO.pdf"
    window.export_pdf(str(pdf_out))
    assert pdf_out.exists()
    assert fitz.open(str(pdf_out)).page_count == 1

    dxf_out = tmp_path / "CORTE.dxf"
    window.export_dxf(str(dxf_out))
    assert dxf_out.exists()
    doc = ezdxf.readfile(str(dxf_out))
    assert len(doc.modelspace().query("LWPOLYLINE")) == 2


def test_clique_do_botao_nao_usa_o_argumento_checked(qapp, tmp_path):
    # O sinal clicked envia um bool; export_pdf(False)/export_dxf(False) NAO
    # deve tratar False como caminho. Sem result, deve apenas retornar.
    window = _window(tmp_path)
    window.export_pdf(False)  # nao deve levantar nem tentar salvar em "False"
    window.export_dxf(False)
    assert window._result is None


def test_remover_pdf_da_lista(qapp, tmp_path):
    window = _window(tmp_path)
    window.add_paths(["a.pdf", "b.pdf"])
    assert window._list.count() == 2
    window._list.setCurrentRow(0)
    window.remove_selected()
    assert window._list.count() == 1
    assert window._paths == ["b.pdf"]


def test_relayout_em_tempo_real_ao_mudar_offset(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window.generate(blocking=True)

    faca_antes = window._result.artworks[0].cut_contour.size.width
    window._offset.setValue(window._offset.value() + 5)  # dispara _relayout
    faca_depois = window._result.artworks[0].cut_contour.size.width
    assert faca_depois == faca_antes + 10  # +5mm em cada lado


def test_recuo_de_seguranca_deixa_faca_menor_que_a_arte(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._offset.setValue(0)
    window._safety.setValue(0)
    window.generate(blocking=True)

    art = window._result.artworks[0]
    # com recuo 5 e offset 0, a faca fica menor que a arte
    window._safety.setValue(5)
    faca = window._result.artworks[0].cut_contour
    assert faca.size.width == art.size.width - 10
    assert faca.size.height == art.size.height - 10


def test_recorte_reduz_tamanho_da_arte(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    window = _window(tmp_path)
    window.add_paths([src])
    window._crop.setValue(0)
    window.generate(blocking=True)
    largura_cheia = window._result.artworks[0].size.width

    window._crop.setValue(3)  # corta 3mm de cada borda -> -6mm na largura
    assert window._result.artworks[0].size.width == largura_cheia - 6


def test_persiste_configuracoes(qapp, tmp_path):
    window = _window(tmp_path)
    window._width.setValue(1500)
    window._height.setValue(1000)
    window._spacing.setValue(8)
    window._offset.setValue(2)
    window._safety.setValue(1)
    window._save_settings()

    recarregado = SettingsStore(tmp_path / "config.json").load()
    assert recarregado.material_width == 1500
    assert recarregado.material_height == 1000
    assert recarregado.spacing == 8
    assert recarregado.offset == 2
    assert recarregado.safety_inset == 1
