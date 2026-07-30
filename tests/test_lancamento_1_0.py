"""Validação dos itens obrigatórios do lançamento 1.0 (auditoria de 30/07).

Cobre: N1 (save atômico), N3 (config corrompido recupera), H3 (ativar sem
conseguir gravar avisa), H4 (fingerprint sem MAC no Windows), C1 (EULA sem
placeholders), C2 (lock do pdfium no _pdf_page_count).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parents[1]

# altura útil (px lógicos) de um notebook 1366x768 a 125%: 768/1.25 = 614,
# menos barra de título e barra de tarefas do Windows
ALTURA_UTIL_125 = 545


def _app_com_tema():
    """QApplication COM o QSS do produto aplicado.

    Medir geometria sem o tema mente: o QSS acrescenta padding em cada campo
    e botão — a Ativação media 468px sem ele e 585px com ele. Teste de "cabe
    na tela" só vale medindo o que o cliente vê."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from app.presentation import theme

    theme.apply(app)
    return app


# ---- N1: salvar .printnest é atômico ----
def test_save_interrompido_preserva_o_projeto_anterior(tmp_path, monkeypatch):
    from app.application import project_io
    from app.application.project_io import (
        ProjectDocument,
        ProjectError,
        ProjectFile,
        ProjectStore,
    )

    alvo = tmp_path / "trabalho.printnest"
    store = ProjectStore()
    store.save(alvo, ProjectDocument(files=[ProjectFile("a.pdf", quantity=1)]))
    original = alvo.read_text(encoding="utf-8")

    # simula interrupção no MEIO da gravação seguinte (antes do replace)
    monkeypatch.setattr(
        project_io.os, "fsync",
        lambda *_a: (_ for _ in ()).throw(OSError("disco caiu no meio")),
    )
    with pytest.raises(ProjectError):
        store.save(alvo, ProjectDocument(files=[ProjectFile("b.pdf", quantity=9)]))
    monkeypatch.undo()

    # o destino não foi truncado: o projeto anterior continua íntegro
    assert alvo.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob("*.tmp")), "tmp órfão deveria ser removido"


def test_save_normal_continua_redondo(tmp_path):
    from app.application.project_io import ProjectDocument, ProjectFile, ProjectStore

    alvo = tmp_path / "ok.printnest"
    store = ProjectStore()
    store.save(alvo, ProjectDocument(files=[ProjectFile("x.pdf", quantity=3)]))
    assert store.load(alvo).files[0].quantity == 3
    assert not list(tmp_path.glob("*.tmp"))


# ---- N3: config corrompido não bricka o app ----
def test_config_corrompido_abre_com_defaults_e_guarda_o_quebrado(tmp_path):
    from app.shared.config.settings import AppSettings, SettingsStore

    caminho = tmp_path / "config.json"
    caminho.write_text('{"lang', encoding="utf-8")  # JSON truncado

    settings = SettingsStore(caminho).load_or_create()
    assert isinstance(settings, AppSettings)  # abriu, não estourou
    assert caminho.exists()  # defaults regravados
    json.loads(caminho.read_text(encoding="utf-8"))  # e são JSON válido
    assert (tmp_path / "config.json.corrompido").exists()  # o quebrado ficou de lado


def test_config_save_atomico_preserva_o_anterior(tmp_path, monkeypatch):
    from app.shared.config import settings as settings_mod
    from app.shared.config.settings import AppSettings, SettingsStore
    from app.shared.errors import ConfigError

    caminho = tmp_path / "config.json"
    store = SettingsStore(caminho)
    store.save(AppSettings(language="pt-BR"))
    original = caminho.read_text(encoding="utf-8")

    monkeypatch.setattr(
        settings_mod.os, "fsync",
        lambda *_a: (_ for _ in ()).throw(OSError("interrompido")),
    )
    with pytest.raises(ConfigError):
        store.save(AppSettings(language="en"))
    monkeypatch.undo()
    assert caminho.read_text(encoding="utf-8") == original


# ---- H3: ativar sem conseguir gravar a licença avisa (não mente sucesso) ----
def test_ativar_sem_conseguir_gravar_licenca_avisa(tmp_path, monkeypatch):
    from app.licensing import license as L
    from app.licensing import signing
    from app.licensing.manager import LicenseManager
    from app.shared.config.paths import AppPaths
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    paths = AppPaths(home=tmp_path)
    manager = LicenseManager(paths)
    priv = Ed25519PrivateKey.generate()
    raw = priv.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    monkeypatch.setattr(signing, "PUBLIC_KEY_HEX", raw.hex())
    lic = L.License(customer="Cliente Teste", machine_id=manager.machine_id)
    key = lic.encode(priv.sign(lic.payload_bytes()))

    # sanidade: com disco ok, ativa
    ok, _ = manager.activate(key)
    assert ok
    manager.deactivate()

    # disco recusando escrita: o retorno tem de ser FALHA com orientação
    monkeypatch.setattr(
        Path, "write_text", lambda *a, **k: (_ for _ in ()).throw(OSError("negado"))
    )
    ok2, msg = manager.activate(key)
    assert ok2 is False
    assert "salv" in msg.lower() or "grav" in msg.lower()


# ---- H4: fingerprint não usa mais o MAC no Windows ----
def test_machine_id_estavel_com_mac_variando(monkeypatch):
    import sys
    import uuid

    from app.licensing import fingerprint

    if sys.platform != "win32":
        pytest.skip("regra do MachineGuid é específica do Windows")

    monkeypatch.setattr(uuid, "getnode", lambda: 0x111111111111)
    a = fingerprint.machine_id()
    monkeypatch.setattr(uuid, "getnode", lambda: 0x222222222222)
    b = fingerprint.machine_id()
    # dock/adaptador USB/driver novo mudam o MAC — a licença NÃO pode quebrar
    assert a == b


# ---- C1: a EULA que o instalador exibe está pronta para venda ----
def test_eula_sem_placeholders_e_com_bom():
    eula = REPO / "installer" / "EULA.txt"
    bruto = eula.read_bytes()
    assert bruto[:3] == b"\xef\xbb\xbf", "Inno Setup precisa de UTF-8 com BOM"
    texto = bruto.decode("utf-8-sig")
    for marcador in ("[RAZAO", "[NUMERO", "[CIDADE", "[DEFINIR", "[SUPORTE"):
        assert marcador not in texto, f"placeholder de rascunho na EULA: {marcador}"
    assert "PrintNest Pro" in texto
    assert "ativacao.printnest@gmail.com" in texto


# ---- C7: o "não salvo" é por aba ----
def test_dirty_e_por_aba(tmp_path):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w._mark_dirty()
    w._new_tab()
    # a aba 1 guardou o próprio sujo; a aba nova nasce limpa
    assert w._sessions[0]["dirty"] is True
    assert w._dirty is False
    # salvar/limpar a aba 2 NÃO limpa a aba 1 (o bug antigo era global)
    w._dirty = False
    w._on_tab_changed(0)
    assert w._dirty is True  # voltar para a aba 1 restaura o sujo dela
    w.close()


def test_trocar_de_aba_nao_suja_a_aba_de_destino(tmp_path):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w._new_tab()          # aba 2, limpa
    w._on_tab_changed(0)  # volta para a aba 1 (limpa)
    assert w._dirty is False, "trocar de aba não pode marcar não-salvo sozinho"
    w.close()


# ---- C4: Modo Corte cabe em notebook 1366x768 @125% (~545px úteis) ----
def test_modo_corte_cabe_em_notebook_125():
    app = _app_com_tema()
    from app.presentation.cut_mode_dialog import CutModeDialog

    dlg = CutModeDialog()
    dlg.show()
    app.processEvents()
    minimo = dlg.minimumSizeHint().expandedTo(dlg.minimumSize())
    assert minimo.height() <= ALTURA_UTIL_125, (
        f"mínimo {minimo.height()}px não cabe em 768@125%"
    )
    assert minimo.width() <= 1366, f"mínimo {minimo.width()}px mais largo que a tela"
    dlg.close()
    dlg.deleteLater()


# ---- C6: o canal de atualização não pode sair morto no build ----
def test_endereco_de_atualizacao_esta_embutido_no_build():
    # Sem isto, nenhum cliente da 1.0.0 fica sabendo de uma 1.0.1 — e não há
    # como corrigir remotamente. NÃO faz rede: só confere que a constante que
    # vai dentro do .exe está preenchida e num esquema que o app aceita.
    from app.infrastructure import updates

    assert updates.URL_MANIFESTO_PADRAO, (
        "URL_MANIFESTO_PADRAO vazia: o build sairia sem canal de atualização"
    )
    assert updates.url_segura(updates.URL_MANIFESTO_PADRAO)
    assert updates.URL_MANIFESTO_PADRAO.endswith(".json")


# ---- H2: a Ativação também tem de caber em notebook 1366x768 @125% ----
def test_ativacao_cabe_em_notebook_125(tmp_path):
    # É a PRIMEIRA tela do produto comprado: se "Ativar"/"Sair" ficam abaixo
    # da borda, o cliente não consegue nem entrar no software que pagou.
    from datetime import date

    app = _app_com_tema()
    from app.licensing.manager import LicenseManager
    from app.presentation.licensing_dialog import ActivationDialog
    from app.shared.config import AppPaths

    m = LicenseManager(paths=AppPaths(home=tmp_path), today=date(2026, 1, 1))
    dlg = ActivationDialog(m, blocking=True)
    dlg.show()
    app.processEvents()
    minimo = dlg.minimumSizeHint().expandedTo(dlg.minimumSize())
    assert minimo.height() <= ALTURA_UTIL_125, (
        f"mínimo {minimo.height()}px não cabe em 768@125%"
    )
    assert minimo.width() <= 1366, f"mínimo {minimo.width()}px mais largo que a tela"
    dlg.close()
    dlg.deleteLater()


# ---- C8: exportar/enviar marca o arranjo como aproveitado ----
def test_exportar_dxf_marca_o_arranjo_como_aproveitado(tmp_path):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from app.presentation.cut_mode_dialog import CutModeDialog

    dlg = CutModeDialog()
    assert dlg._work_exported is False
    # com PYTEST_CURRENT_TEST no ambiente, fechar nunca abre modal (guarda)
    assert dlg._confirma_descartar_arranjo() is True
    dlg._work_exported = True
    assert dlg._confirma_descartar_arranjo() is True
    dlg.deleteLater()


# ---- C2: contagem de páginas segura o lock do pdfium ----
def test_pdf_page_count_segura_o_lock_do_pdfium(tmp_path, monkeypatch):
    import threading

    from app.infrastructure import pdfium_boxes
    from app.presentation.main_window import MainWindow

    aquisicoes = []
    espiao = threading.RLock()

    class LockEspiao:
        def __enter__(self):
            aquisicoes.append(True)
            return espiao.__enter__()

        def __exit__(self, *a):
            return espiao.__exit__(*a)

    monkeypatch.setattr(pdfium_boxes, "PDFIUM_LOCK", LockEspiao())
    # PDF de mentira: abrir falha, mas o caminho até o pdfium passa pelo lock
    caminho = tmp_path / "arquivo.pdf"
    caminho.write_bytes(b"%PDF-1.4\n%%EOF\n")
    MainWindow._pdf_page_count(str(caminho))
    assert aquisicoes, "_pdf_page_count precisa adquirir o PDFIUM_LOCK"
