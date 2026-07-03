"""Modelo de licenca + serializacao da 'chave de licenca' que o cliente cola.

A chave e uma string: "PNEST1." + base64url(payload_json) + "." + base64url(sig).
O payload identifica o cliente, prende ao PC (machine_id) e (opcional) expira.
A assinatura garante que so o dono do produto pode emitir (ver signing.py).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date

from app.licensing import signing

_PREFIX = "PNEST1"


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


@dataclass(frozen=True)
class License:
    """Dados de uma licenca (o que vai assinado dentro da chave)."""

    customer: str          # nome/e-mail do cliente (identificacao)
    machine_id: str        # PC ao qual a licenca esta presa
    edition: str = "pro"   # edicao (pro, etc.)
    issued: str = ""       # data de emissao (ISO: AAAA-MM-DD)
    expires: str = ""      # validade (ISO) ou "" = perpetua

    def payload_bytes(self) -> bytes:
        """Bytes canonicos assinados (ordem de chaves estavel)."""
        data = {
            "customer": self.customer,
            "machine_id": self.machine_id,
            "edition": self.edition,
            "issued": self.issued,
            "expires": self.expires,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def is_expired(self, today: date | None = None) -> bool:
        if not self.expires:
            return False
        today = today or date.today()
        try:
            return date.fromisoformat(self.expires) < today
        except ValueError:
            return True  # data corrompida -> trata como expirada

    def encode(self, signature: bytes) -> str:
        """Monta a string da licenca a partir do payload + assinatura."""
        return f"{_PREFIX}.{_b64e(self.payload_bytes())}.{_b64e(signature)}"


def parse(key: str) -> tuple[License, bytes] | None:
    """Decodifica a string da licenca em (License, assinatura). None se malformada.

    NAO valida a assinatura aqui — quem valida e o verifier (verify_key).
    """
    key = "".join(key.split())  # remove espacos/quebras de linha coladas
    parts = key.split(".")
    if len(parts) != 3 or parts[0] != _PREFIX:
        return None
    try:
        payload = _b64d(parts[1])
        signature = _b64d(parts[2])
        data = json.loads(payload)
        lic = License(
            customer=str(data["customer"]),
            machine_id=str(data["machine_id"]),
            edition=str(data.get("edition", "pro")),
            issued=str(data.get("issued", "")),
            expires=str(data.get("expires", "")),
        )
    except (ValueError, KeyError, TypeError):
        return None
    return lic, signature


def verify_key(key: str, machine_id: str, today: date | None = None) -> License | None:
    """Valida uma chave de licenca para ESTE PC. Retorna a License se:
    assinatura confere + machine_id bate + nao expirou. Senao, None.
    """
    parsed = parse(key)
    if parsed is None:
        return None
    lic, signature = parsed
    if not signing.verify(lic.payload_bytes(), signature):
        return None  # assinatura invalida (forjada/adulterada)
    if lic.machine_id != machine_id:
        return None  # licenca de outro PC
    if lic.is_expired(today):
        return None
    return lic
