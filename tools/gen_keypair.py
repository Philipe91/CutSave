"""Gera um NOVO par de chaves Ed25519 de licenciamento — rode UMA vez.

Salva a privada em tools/license_private_key.pem (gitignored, seu segredo) e
imprime a PUBLICA em hex para colar em app/licensing/signing.py (PUBLIC_KEY_HEX).
Ja existe um par gerado; so rode de novo se quiser trocar o segredo (invalida
todas as licencas ja emitidas).
"""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

OUT = Path(__file__).with_name("license_private_key.pem")


def main() -> None:
    if OUT.exists():
        resp = input(f"{OUT.name} ja existe. Sobrescrever e INVALIDAR licencas? [s/N] ")
        if resp.strip().lower() != "s":
            print("cancelado.")
            return
    priv = Ed25519PrivateKey.generate()
    OUT.write_bytes(
        priv.private_bytes(
            ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption()
        )
    )
    raw = priv.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    print("privada salva em:", OUT)
    print("cole no signing.py -> PUBLIC_KEY_HEX =", raw.hex())


if __name__ == "__main__":
    main()
