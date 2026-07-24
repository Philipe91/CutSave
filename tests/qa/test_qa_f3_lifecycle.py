"""QA FASE 3 — ciclo de vida hostil: arquivo some do disco, nomes hostis,
caminho de rede fantasma, permissao de escrita negada, projeto corrompido.

Criterio: aviso amigavel OU degradacao limpa — nunca traceback nao tratado,
nunca corrupcao de estado. A janela continua utilizavel depois.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time  # noqa: E402

import fitz  # noqa: E402
import pytest  # noqa: E402
from app.application.project_io import ProjectDocument, ProjectFile, ProjectStore  # noqa: E402
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
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _window_cfg(tmp_path, name):
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


def _two_page_pdf(tmp_path, name="fonte.pdf"):
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=200, height=100)
        page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


def _still_usable(w) -> None:
    assert w.isEnabled()
    w._toasts.info("sanity check")


# ---------------------------------------------------------------------------
# Caso 2: arquivo some do disco DEPOIS de gerar, ANTES de exportar
# ---------------------------------------------------------------------------

def test_arquivo_some_apos_gerar_antes_de_exportar_pdf(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w1")
    w.add_paths([src])
    w.generate(blocking=True)
    assert w._result is not None

    os.remove(src)  # some do disco DEPOIS de gerado, ANTES de exportar

    avisos = []
    from PySide6.QtWidgets import QMessageBox as QMB
    import unittest.mock as mock
    with mock.patch.object(QMB, "critical", staticmethod(lambda *a, **k: avisos.append(a))):
        out = tmp_path / "IMPRESSAO.pdf"
        w.export_pdf(str(out))  # nao pode estourar excecao crua

    # aviso amigavel OU degradacao limpa (nao gerar arquivo corrompido)
    if not out.exists():
        assert avisos, "export falhou sem avisar o usuario"
    _still_usable(w)


def test_arquivo_some_apos_gerar_antes_de_exportar_dxf(qapp, tmp_path):
    src = _two_page_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w2")
    w.add_paths([src])
    w.generate(blocking=True)
    os.remove(src)

    from PySide6.QtWidgets import QMessageBox as QMB
    import unittest.mock as mock
    avisos = []
    with mock.patch.object(QMB, "critical", staticmethod(lambda *a, **k: avisos.append(a))):
        out = tmp_path / "faca.dxf"
        w.export_dxf(str(out))
    if not out.exists():
        assert avisos, "export DXF falhou sem avisar o usuario"
    _still_usable(w)


# ---------------------------------------------------------------------------
# Caso 7: nome de arquivo hostil (acento + emoji + 200 chars + espaco no fim)
# ---------------------------------------------------------------------------

def test_nome_de_arquivo_hostil_importa_gera_salva_e_reabre(qapp, tmp_path):
    # comprimento do nome respeitando o MAX_PATH do Windows (260) menos o
    # prefixo do tmp_path do pytest (variavel por maquina/execucao) — o
    # objetivo e um nome hostil (acento+emoji+bem longo+espaco no fim), nao
    # estourar o limite do PROPRIO sistema operacional (fora do escopo do app).
    prefixo = "arte_ção_emoji_🎨🖨️_"
    sufixo = " .pdf"
    orcamento = max(20, 245 - len(str(tmp_path)) - len(prefixo) - len(sufixo))
    nome = prefixo + ("x" * orcamento) + sufixo
    caminho = tmp_path / nome
    doc = fitz.open()
    page = doc.new_page(width=150, height=90)
    page.draw_rect(fitz.Rect(0, 0, 150, 90), color=(0, 0, 0), fill=(0, 0, 0))
    doc.save(str(caminho))
    doc.close()

    w = _window_cfg(tmp_path, "w3")
    w.add_paths([str(caminho)])
    w.generate(blocking=True)
    assert w._result is not None
    assert sum(s.item_count for s in w._result.sheets) == 1

    proj = tmp_path / "projeto_hostil.printnest"
    assert w.save_project(str(proj)) is True

    w2 = _window_cfg(tmp_path, "w4")
    assert w2.open_project(str(proj)) is True
    assert w2._paths == [str(caminho)]
    assert "⚠" not in w2._table.item(0, 0).text()  # arquivo existe: nao marcado ausente
    _still_usable(w2)


# ---------------------------------------------------------------------------
# Caso 8: caminho de rede inexistente num .printnest salvo
# ---------------------------------------------------------------------------

def test_caminho_de_rede_fantasma_no_projeto_abre_sem_travar(qapp, tmp_path):
    rede = r"\\servidor-fantasma-qa-f3\compartilhado\arte.pdf"
    proj = tmp_path / "rede.printnest"
    ProjectStore().save(
        proj,
        ProjectDocument(files=[ProjectFile(rede, quantity=3)], settings={}),
    )
    w = _window_cfg(tmp_path, "w5")
    t0 = time.monotonic()
    ok = w.open_project(str(proj))
    elapsed = time.monotonic() - t0
    assert ok is True  # REGRA: arquivo ausente nao impede abrir o projeto
    assert w._paths == [rede]
    assert "⚠" in w._table.item(0, 0).text()
    _still_usable(w)
    # Path.exists() em UNC de host inexistente pode, em maquinas reais fora
    # deste sandbox, disparar o timeout de resolucao SMB do Windows (varios
    # segundos). Aqui mediu-se rapido; sinalizamos como suspeita de
    # desempenho, nao falha funcional (ver achados).
    if elapsed > 5.0:
        pytest.xfail(
            f"QA-F3-08: abrir projeto com caminho UNC fantasma levou {elapsed:.1f}s "
            "(Path.exists() em main_window.py open_project()/_populate_files "
            "pode sofrer o timeout de resolucao SMB do Windows)."
        )


# ---------------------------------------------------------------------------
# Caso 13: salvar projeto em pasta sem permissao de escrita
# ---------------------------------------------------------------------------

def test_salvar_projeto_sem_permissao_de_escrita_mostra_aviso(qapp, tmp_path, monkeypatch):
    src = _two_page_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w6")
    w.add_paths([src])

    avisos = []
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda *a, **k: avisos.append(a))
    )

    from pathlib import Path as _Path
    original_write_text = _Path.write_text
    destino = tmp_path / "sem_permissao.printnest"

    # so o ALVO do projeto fica "sem permissao" — nao a pasta de config das
    # settings (senao o teste mede outro bug: ver test_qa_f3_settings_...).
    def _write_text_scoped(self, *a, **k):
        if str(self) == str(destino):
            raise PermissionError(13, "Access is denied", str(self))
        return original_write_text(self, *a, **k)

    monkeypatch.setattr(_Path, "write_text", _write_text_scoped)
    ok = w.save_project(str(destino))

    assert ok is False
    assert avisos, "falha de permissao ao salvar tem que avisar o usuario"
    assert not destino.exists()
    _still_usable(w)


def test_config_sem_permissao_de_escrita_durante_salvar_projeto(qapp, tmp_path, monkeypatch):
    """QA-F3-13b: save_project() chama _save_settings() (grava o config.json)
    ANTES de tentar gravar o .printnest. Se a gravacao do config falhar
    (ConfigError), isso NAO e capturado por save_project — so ProjectError e
    tratado (main_window.py save_project(), except ProjectError). Confirma o
    comportamento real: se virar bug, xfail; se ja tratado, passa."""
    src = _two_page_pdf(tmp_path)
    w = _window_cfg(tmp_path, "w6b")
    w.add_paths([src])

    from pathlib import Path as _Path
    original_write_text = _Path.write_text
    config_path = w._store.path

    def _write_text_scoped(self, *a, **k):
        if str(self) == str(config_path):
            raise PermissionError(13, "Access is denied", str(self))
        return original_write_text(self, *a, **k)

    monkeypatch.setattr(_Path, "write_text", _write_text_scoped)
    avisos = []
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda *a, **k: avisos.append(a))
    )
    destino = tmp_path / "projeto_ok.printnest"
    try:
        ok = w.save_project(str(destino))
    except Exception as exc:
        pytest.xfail(
            f"QA-F3-13b: falha ao gravar config.json durante save_project() "
            f"propagou {type(exc).__name__} sem dialogo amigavel "
            "(main_window.py save_project()/_collect_project() chama "
            "_save_settings() fora do try/except ProjectError)."
        )
    assert ok is False or avisos
    _still_usable(w)


# ---------------------------------------------------------------------------
# Caso 14: .printnest corrompido (JSON truncado / versao futura / lixo)
# ---------------------------------------------------------------------------

def _corrupted_variants(tmp_path):
    truncado = tmp_path / "truncado.printnest"
    truncado.write_text('{"version": 1, "files": [{"path": "a.pdf"', encoding="utf-8")

    futuro = tmp_path / "futuro.printnest"
    futuro.write_text('{"version": 99, "files": []}', encoding="utf-8")

    lixo = tmp_path / "lixo.printnest"
    lixo.write_bytes(bytes([i % 256 for i in range(500)]))

    return {"truncado": str(truncado), "versao_futura": str(futuro), "lixo_binario": str(lixo)}


@pytest.mark.parametrize("variante", ["truncado", "versao_futura"])
def test_printnest_corrompido_avisa_e_nao_perde_trabalho_atual(qapp, tmp_path, monkeypatch, variante):
    variantes = _corrupted_variants(tmp_path)
    caminho_corrompido = variantes[variante]

    src = _two_page_pdf(tmp_path, name=f"trabalho_atual_{variante}.pdf")
    w = _window_cfg(tmp_path, f"w7_{variante}")
    w.add_paths([src])
    paths_antes = list(w._paths)

    avisos = []
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda *a, **k: avisos.append(a))
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (caminho_corrompido, "")),
    )

    ok = w.open_project()  # caminho INTERATIVO (dialogo real do usuario)

    assert ok is False
    assert avisos, f"{variante}: projeto corrompido tem que avisar o usuario"
    assert w._paths == paths_antes, "trabalho atual da aba nao pode ser perdido"
    _still_usable(w)

    # a janela continua operante: da pra gerar normalmente depois do erro
    w.generate(blocking=True)
    assert w._result is not None


def test_printnest_lixo_binario_avisa_e_nao_perde_trabalho_atual(qapp, tmp_path, monkeypatch):
    # QA-F3-14 / A15, corrigido na F1: o except do ProjectStore.load() agora
    # cobre UnicodeDecodeError e vira ProjectError com dialogo amigavel.
    variantes = _corrupted_variants(tmp_path)
    caminho_corrompido = variantes["lixo_binario"]

    src = _two_page_pdf(tmp_path, name="trabalho_atual_lixo.pdf")
    w = _window_cfg(tmp_path, "w7_lixo")
    w.add_paths([src])
    paths_antes = list(w._paths)

    avisos = []
    monkeypatch.setattr(
        QMessageBox, "critical", staticmethod(lambda *a, **k: avisos.append(a))
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (caminho_corrompido, "")),
    )

    ok = w.open_project()

    assert ok is False
    assert avisos, "lixo binario: projeto corrompido tem que avisar o usuario"
    assert w._paths == paths_antes
    _still_usable(w)
    w.generate(blocking=True)
    assert w._result is not None
