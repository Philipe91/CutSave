"""Emissao de licencas (lado do VENDEDOR) — usa a chave PRIVADA.

Logica compartilhada por: tools/gen_license.py (CLI), tools/license_studio.py
(GUI) e um futuro backend do site (self-service). Mantida FORA de app/ porque
lida com o segredo (a chave privada); o app so verifica (app/licensing).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# permite importar app.licensing.License rodando a partir da pasta tools/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.licensing.license import License  # noqa: E402
from cryptography.hazmat.primitives import serialization as ser  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

DEFAULT_PRIVATE_PEM = Path(__file__).with_name("license_private_key.pem")


def load_private_key(path: Path | None = None) -> Ed25519PrivateKey:
    """Carrega a chave privada Ed25519 (PEM). Levanta se ausente/invalida."""
    pem_path = path or DEFAULT_PRIVATE_PEM
    if not pem_path.exists():
        raise FileNotFoundError(
            f"Chave privada nao encontrada: {pem_path}. "
            "Rode tools/gen_keypair.py uma vez para cria-la."
        )
    key = ser.load_pem_private_key(pem_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("O PEM nao e uma chave Ed25519.")
    return key


def issue_license(
    machine_id: str,
    customer: str,
    *,
    edition: str = "pro",
    expires: str = "",
    private_key: Ed25519PrivateKey | None = None,
    today: date | None = None,
) -> str:
    """Emite a string da licenca (PNEST1...) presa a 'machine_id'.

    'expires' vazio = perpetua. Levanta ValueError se os dados forem invalidos.
    """
    machine_id = machine_id.strip()
    customer = customer.strip()
    if not machine_id:
        raise ValueError("ID da Maquina vazio.")
    if not customer:
        raise ValueError("Cliente vazio.")
    if expires:
        date.fromisoformat(expires)  # valida o formato (levanta se errado)
    key = private_key or load_private_key()
    lic = License(
        customer=customer,
        machine_id=machine_id,
        edition=edition.strip() or "pro",
        issued=(today or date.today()).isoformat(),
        expires=expires.strip(),
    )
    return lic.encode(key.sign(lic.payload_bytes()))
