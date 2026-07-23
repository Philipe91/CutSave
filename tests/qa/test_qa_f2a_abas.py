"""FASE 2A (QA) — abas de trabalho (multi-projeto) ponta-a-ponta: criar
varias, alternar rapido, trabalho diferente em cada, clipboard por aba,
fechar aba com trabalho NAO salvo (prompt real, nao so o bypass do pytest)
e reabrir um projeto numa aba nova.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz  # noqa: E402
import pytest  # noqa: E402
from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase  # noqa: E402
from app.application.use_cases.import_image import ImportImageUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    RunProductionPipelineUseCase,
)
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter  # noqa: E402
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter  # noqa: E402
from app.infrastructure.importers.pdfium_importer import PdfiumImporter  # noqa: E402
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer  # noqa: E402
from app.presentation.main_window import MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _window(tmp_path, name="w"):
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    store = SettingsStore(folder / "config.json")
    settings = store.load_or_create()
    pipeline = RunProductionPipelineUseCase(
        ImportPdfUseCase(PdfiumImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(cache_dir=folder / "imgcache")),
    )
    return MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PikePdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PdfiumPageRenderer(),
        store,
        settings,
    )


def _n_page_pdf(tmp_path, n, w=120.0, h=120.0, name="multi"):
    doc = fitz.open()
    for _ in range(n):
        pg = doc.new_page(width=w, height=h)
        pg.draw_rect(pg.rect, color=(0, 0, 0), fill=(0, 0, 0))
    src = tmp_path / f"{name}.pdf"
    doc.save(str(src))
    doc.close()
    return str(src)


def test_tres_abas_alternadas_rapido_preservam_o_trabalho_de_cada(qapp, tmp_path):
    p1 = _n_page_pdf(tmp_path, 1, name="p1")
    p2 = _n_page_pdf(tmp_path, 2, name="p2")
    p3 = _n_page_pdf(tmp_path, 3, name="p3")
    w = _window(tmp_path)
    w._width.setValue(3000)
    w._height.setValue(3000)

    w.add_paths([p1])
    w.generate(blocking=True)

    w._new_tab()
    w.add_paths([p2])
    w.generate(blocking=True)

    w._new_tab()
    w.add_paths([p3])
    w.generate(blocking=True)

    assert w._tabbar.count() == 3
    expected = {0: (p1, 1), 1: (p2, 2), 2: (p3, 3)}

    # alterna rapido, em ordem nao sequencial, varias vezes seguidas
    order = [0, 2, 1, 0, 1, 2, 0, 2, 1, 0]
    for idx in order:
        w._tabbar.setCurrentIndex(idx)
        path, qty = expected[idx]
        assert w._paths == [path], f"aba {idx} perdeu o arquivo apos alternar"
        assert sum(s.item_count for s in w._result.sheets) == qty, (
            f"aba {idx} perdeu a producao apos alternar"
        )


def test_clipboard_nao_atravessa_aba_e_colar_na_outra_nao_faz_nada(qapp, tmp_path):
    p1 = _n_page_pdf(tmp_path, 2, name="p1")
    p2 = _n_page_pdf(tmp_path, 2, name="p2")
    w = _window(tmp_path)
    w.add_paths([p1])
    w.generate(blocking=True)
    w._piece_items[0].setSelected(True)
    w._copy_selected()
    assert len(w._piece_clipboard) == 1

    w._new_tab()
    w.add_paths([p2])
    w.generate(blocking=True)
    n0 = sum(s.item_count for s in w._result.sheets)
    assert w._piece_clipboard == []  # nao atravessou

    # colar sem clipboard nesta aba: documentado como no-op (nao adiciona nada)
    w._paste_clipboard()
    assert sum(s.item_count for s in w._result.sheets) == n0


def test_fechar_aba_com_trabalho_nao_salvo_pede_confirmacao_de_verdade(qapp, tmp_path, monkeypatch):
    # Buraco de cobertura (Fase 1, item 6): ate agora so havia teste de
    # fechar aba LIMPA. Aqui o fluxo interativo de verdade e exercido:
    # tira o bypass do pytest, torna a janela "visivel" e intercepta o
    # QMessageBox para simular cada clique.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    w = _window(tmp_path)
    w.show()
    assert w.isVisible()

    def _make_hooks(role):
        def _exec(self):
            self._qa_clicked = next(
                (b for b in self.buttons() if self.buttonRole(b) == role), None
            )
            return 0

        def _clicked(self):
            return getattr(self, "_qa_clicked", None)

        return _exec, _clicked

    p1 = _n_page_pdf(tmp_path, 1, name="p1")
    w.add_paths([p1])
    w.generate(blocking=True)
    w._new_tab()
    p2 = _n_page_pdf(tmp_path, 1, name="p2")
    w.add_paths([p2])
    assert w._dirty is True  # trabalho novo, ainda nao salvo

    # 1) CANCELAR: a aba continua aberta, nada se perde
    _exec, _clicked = _make_hooks(QMessageBox.RejectRole)
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", _clicked)
    w._close_tab(1)
    assert w._tabbar.count() == 2, "Cancelar deveria manter a aba aberta"
    assert w._paths == [p2]

    # 2) DESCARTAR: a aba fecha e o trabalho nao salvo some
    _exec, _clicked = _make_hooks(QMessageBox.DestructiveRole)
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", _clicked)
    w._close_tab(1)
    assert w._tabbar.count() == 1
    assert w._paths == [p1]  # volta pra aba 1 (unica restante)
    w.close()


def test_reabrir_projeto_numa_aba_nova(qapp, tmp_path):
    src = _n_page_pdf(tmp_path, 2, name="proj")
    w1 = _window(tmp_path, "w1")
    w1.add_paths([src])
    w1._width.setValue(1500)
    proj = tmp_path / "trabalho.printnest"
    assert w1.save_project(str(proj)) is True

    w2 = _window(tmp_path, "w2")
    w2._new_tab()  # aba em branco extra antes de abrir
    assert w2.open_project(str(proj)) is True
    assert w2._paths == [src]
    assert w2._width.value() == 1500
    assert w2._loaded is False and w2._result is None  # regra: nao gera sozinho
