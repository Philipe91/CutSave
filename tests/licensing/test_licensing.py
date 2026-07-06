"""Testes do motor de licenciamento (Ed25519, offline, node-locked).

Usa um par de chaves EFEMERO (gerado no teste) e injeta a publica em
signing.PUBLIC_KEY_HEX — nao depende do segredo real do produto.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from app.licensing import license as L
from app.licensing import signing
from app.licensing.fingerprint import machine_id
from app.licensing.manager import LicenseManager, LicenseState
from app.shared.config.paths import AppPaths
from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@pytest.fixture
def keypair(monkeypatch):
    """Par efemero; publica injetada no verificador."""
    priv = Ed25519PrivateKey.generate()
    raw = priv.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    monkeypatch.setattr(signing, "PUBLIC_KEY_HEX", raw.hex())
    return priv


def _issue(priv, machine, customer="Cliente", expires=""):
    lic = L.License(customer=customer, machine_id=machine, expires=expires)
    return lic.encode(priv.sign(lic.payload_bytes()))


def test_machine_id_deterministico_e_formatado():
    a = machine_id("fonte-fixa")
    b = machine_id("fonte-fixa")
    assert a == b  # mesmo PC -> mesmo id
    assert a.startswith("PN-") and len(a) == 22  # PN-XXXX-XXXX-XXXX-XXXX
    assert machine_id("outra-fonte") != a


def test_licenca_valida_para_este_pc(keypair):
    mid = "PN-AAAA-BBBB-CCCC-DDDD"
    key = _issue(keypair, mid, customer="Grafica X")
    lic = L.verify_key(key, mid)
    assert lic is not None and lic.customer == "Grafica X"


def test_licenca_de_outro_pc_rejeitada(keypair):
    key = _issue(keypair, "PN-1111-1111-1111-1111")
    assert L.verify_key(key, "PN-2222-2222-2222-2222") is None


def test_licenca_adulterada_rejeitada(keypair):
    mid = "PN-AAAA-BBBB-CCCC-DDDD"
    key = _issue(keypair, mid)
    ruim = key[:-4] + ("AAAA" if not key.endswith("AAAA") else "BBBB")
    assert L.verify_key(ruim, mid) is None


def test_licenca_expirada_rejeitada(keypair):
    mid = "PN-AAAA-BBBB-CCCC-DDDD"
    ontem = (date.today() - timedelta(days=1)).isoformat()
    key = _issue(keypair, mid, expires=ontem)
    assert L.verify_key(key, mid) is None


def test_licenca_forjada_sem_a_privada_certa_rejeitada(keypair):
    # assina com OUTRA privada (atacante) -> assinatura nao confere com a publica
    mid = "PN-AAAA-BBBB-CCCC-DDDD"
    atacante = Ed25519PrivateKey.generate()
    key = _issue(atacante, mid)
    assert L.verify_key(key, mid) is None


def test_manager_sem_licenca_nao_liberado(tmp_path):
    paths = AppPaths(home=tmp_path)
    m = LicenseManager(paths=paths, today=date(2026, 1, 1))
    assert m.state() is LicenseState.UNLICENSED
    assert not m.is_licensed()


def test_manager_ativar_licencia_e_persiste(tmp_path, keypair):
    paths = AppPaths(home=tmp_path)
    hoje = date(2026, 1, 1)
    m = LicenseManager(paths=paths, today=hoje)
    assert not m.is_licensed()

    key = _issue(keypair, m.machine_id, customer="Grafica Y")
    ok, msg = m.activate(key)
    assert ok and "Grafica Y" in msg
    assert m.state() is LicenseState.LICENSED

    # persistiu: um novo manager (mesmo PC) ja abre licenciado
    m2 = LicenseManager(paths=paths, today=hoje + timedelta(days=60))
    assert m2.is_licensed()

    m2.deactivate()
    assert not paths.license_file.exists()
    m3 = LicenseManager(paths=paths, today=hoje)
    assert not m3.is_licensed()


def test_manager_ativar_licenca_de_outro_pc_falha(tmp_path, keypair):
    paths = AppPaths(home=tmp_path)
    m = LicenseManager(paths=paths, today=date(2026, 1, 1))
    key = _issue(keypair, "PN-OUTR-OPCP-OUTR-OPCP")
    ok, msg = m.activate(key)
    assert not ok and "outro computador" in msg.lower()


def test_desativar_no_exe_fecha_o_app(tmp_path, keypair, monkeypatch):
    # No executavel (sys.frozen), desativar encerra o app na hora — a checagem
    # de licenca so roda no startup e nao alcancaria a sessao ja aberta.
    import os
    import sys as _sys
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from app.presentation.licensing_dialog import ActivationDialog
    from PySide6.QtWidgets import QApplication, QMessageBox

    QApplication.instance() or QApplication([])
    paths = AppPaths(home=tmp_path)
    m = LicenseManager(paths=paths, today=date(2026, 1, 1))
    m.activate(_issue(keypair, m.machine_id))
    assert m.is_licensed()

    dlg = ActivationDialog(m)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes)
    )
    monkeypatch.setattr(_sys, "frozen", True, raising=False)
    fechou = []
    monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: fechou.append(1)))
    dlg._deactivate()
    assert not m.is_licensed()
    assert fechou  # app encerrado junto com a desativacao
    dlg.deleteLater()


def test_dialogo_ativacao_ativa_com_chave_boa(tmp_path, keypair, monkeypatch):
    # Exercita o dialogo de ativacao (offscreen) com uma chave valida.
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from app.presentation.licensing_dialog import ActivationDialog
    from PySide6.QtWidgets import QApplication, QMessageBox

    QApplication.instance() or QApplication([])
    paths = AppPaths(home=tmp_path)
    m = LicenseManager(paths=paths, today=date(2026, 1, 1))
    dlg = ActivationDialog(m, blocking=True)
    assert not m.is_licensed()

    key = _issue(keypair, m.machine_id, customer="Cliente Z")
    dlg._key_field.setPlainText(key)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    dlg._activate()
    assert m.is_licensed()
    dlg.deleteLater()
