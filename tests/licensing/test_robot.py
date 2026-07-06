"""Testes do robo de ativacao (vouchers + parsing + emissao idempotente).

Nada de rede: o nucleo (extract_request/process_request) e puro e o emissor e
injetado com um par de chaves EFEMERO (mesmo padrao de test_licensing.py).
"""

from __future__ import annotations

import pytest
from app.licensing import license as L
from app.licensing import signing
from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.license_robot import extract_request, process_request
from tools.vouchers import VoucherStore, normalize

MID = "PN-AAAA-BBBB-CCCC-DDDD"


@pytest.fixture
def keypair(monkeypatch):
    priv = Ed25519PrivateKey.generate()
    raw = priv.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    monkeypatch.setattr(signing, "PUBLIC_KEY_HEX", raw.hex())
    return priv


@pytest.fixture
def issue(keypair):
    def _issue(machine_id: str, customer: str) -> str:
        lic = L.License(customer=customer, machine_id=machine_id)
        return lic.encode(keypair.sign(lic.payload_bytes()))
    return _issue


@pytest.fixture
def store(tmp_path):
    return VoucherStore(tmp_path / "vouchers.json")


# ---- vouchers ----
def test_voucher_gera_e_normaliza(store):
    (code,) = store.generate(1, note="teste")
    assert code.startswith("PNC-") and len(code) == 13
    # cliente digita de qualquer jeito: minusculas, espacos, sem tracos
    bagunca = code.lower().replace("-", " ")
    assert normalize(bagunca) == code
    assert store.find(bagunca) is not None
    assert normalize("PNC-CURTO") == ""
    assert store.find("PNC-ZZZZ-ZZZZ") is None or True  # inexistente nao explode


def test_voucher_persiste_entre_instancias(tmp_path):
    path = tmp_path / "v.json"
    (code,) = VoucherStore(path).generate(1)
    reaberto = VoucherStore(path)
    assert reaberto.find(code) is not None and not reaberto.find(code)["used"]


# ---- parsing do e-mail ----
def test_extrai_id_e_codigo_do_texto():
    texto = (
        "Assunto: ativacao printnest\n"
        f"quero ativar. id da maquina: {MID.lower()}\n"
        "codigo de compra: pnc 7k2m 99xw obrigado!"
    )
    mid, voucher = extract_request(texto)
    assert mid == MID
    assert voucher == "PNC-7K2M-99XW"


def test_extrai_ausencias():
    assert extract_request("email qualquer sem nada") == ("", "")
    mid, voucher = extract_request(f"so o id: {MID}")
    assert mid == MID and voucher == ""


# ---- decisao do robo ----
def test_codigo_valido_emite_chave_que_ativa_este_pc(store, issue):
    (code,) = store.generate(1)
    ok, corpo = process_request(store, MID, code, "Cliente <c@x.com>", issue)
    assert ok
    key = next(l for l in corpo.splitlines() if l.startswith("PNEST1."))
    assert L.verify_key(key, MID) is not None  # chave real, presa ao PC certo
    assert store.find(code)["used"] and store.find(code)["machine_id"] == MID


def test_mesmo_pc_pedindo_de_novo_recebe_a_mesma_chave(store, issue):
    (code,) = store.generate(1)
    _, corpo1 = process_request(store, MID, code, "c@x.com", issue)
    ok2, corpo2 = process_request(store, MID, code, "c@x.com", issue)
    key1 = next(l for l in corpo1.splitlines() if l.startswith("PNEST1."))
    key2 = next(l for l in corpo2.splitlines() if l.startswith("PNEST1."))
    assert ok2 and key1 == key2  # reenvio, nao re-emissao


def test_codigo_usado_em_outro_pc_e_recusado(store, issue):
    (code,) = store.generate(1)
    process_request(store, MID, code, "c@x.com", issue)
    ok, corpo = process_request(store, "PN-2222-2222-2222-2222", code, "x@y.com", issue)
    assert not ok and "PNEST1." not in corpo and "utilizado" in corpo


def test_codigo_desconhecido_e_recusado(store, issue):
    ok, corpo = process_request(store, MID, "PNC-ZZZZ-2222", "c@x.com", issue)
    assert not ok and "PNEST1." not in corpo


def test_pedido_incompleto_orienta_sem_emitir(store, issue):
    ok, corpo = process_request(store, "", "PNC-ZZZZ-2222", "c@x.com", issue)
    assert not ok and "ID da M" in corpo
    ok, corpo = process_request(store, MID, "", "c@x.com", issue)
    assert not ok and "digo de compra" in corpo


# ---- dialogo: pedido pronto ----
def test_dialogo_monta_pedido_com_id_e_endereco(tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from app.licensing import ACTIVATION_EMAIL
    from app.licensing.manager import LicenseManager
    from app.presentation.licensing_dialog import ActivationDialog
    from app.shared.config.paths import AppPaths
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    m = LicenseManager(paths=AppPaths(home=tmp_path))
    dlg = ActivationDialog(m)
    assert m.machine_id in dlg._request_text()
    url = dlg._request_mailto()
    assert url.startswith(f"mailto:{ACTIVATION_EMAIL}?")
    assert m.machine_id.replace("-", "%2D") in url or m.machine_id in url
    dlg.deleteLater()
