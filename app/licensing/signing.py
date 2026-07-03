"""Verificacao de assinatura das licencas (Ed25519).

O app tem SO a chave PUBLICA — verifica, mas nao assina. A chave privada fica
com o dono do produto (tools/license_private_key.pem) e assina as licencas em
tools/gen_license.py. Sem a privada, ninguem forja uma licenca valida.
"""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Chave publica de licenciamento (bytes crus, hex). A PRIVADA correspondente
# esta em tools/license_private_key.pem (gitignored). Para trocar o par:
# rode tools/gen_keypair.py e cole aqui o novo hex.
PUBLIC_KEY_HEX = "767b233334016f262e2e491b01192313e7542b770aa381a5a39682a9c16a1e40"


def _public_key() -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX))


def verify(message: bytes, signature: bytes) -> bool:
    """True se 'signature' e uma assinatura valida de 'message' pela chave."""
    try:
        _public_key().verify(signature, message)
        return True
    except (InvalidSignature, ValueError):
        return False
