"""Emissor de licencas do PrintNest — USO DO DONO DO PRODUTO (voce).

Le a chave PRIVADA (tools/license_private_key.pem, gitignored) e assina uma
licenca presa ao PC do cliente. NUNCA distribua a chave privada nem este PEM.

Fluxo:
  1. O cliente abre o PrintNest -> Ajuda -> Licenca, copia o "ID da Maquina".
  2. Ele te envia esse ID (apos pagar).
  3. Voce roda:

     python tools/gen_license.py --machine-id PN-XXXX-XXXX-XXXX-XXXX \\
         --customer "Grafica Fulano <email>" [--expires 2027-12-31]

  4. Copie a chave impressa e envie ao cliente; ele cola em "Ativar".

Sem --expires, a licenca e PERPETUA.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# roda a partir da raiz do repo (para importar app.licensing)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.licensing.license import License  # noqa: E402
from cryptography.hazmat.primitives import serialization as ser  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

PRIVATE_PEM = Path(__file__).with_name("license_private_key.pem")


def _load_private() -> Ed25519PrivateKey:
    if not PRIVATE_PEM.exists():
        raise SystemExit(
            f"Chave privada nao encontrada: {PRIVATE_PEM}\n"
            "Rode tools/gen_keypair.py uma vez para cria-la."
        )
    key = ser.load_pem_private_key(PRIVATE_PEM.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("O PEM nao e uma chave Ed25519.")
    return key


def main() -> None:
    ap = argparse.ArgumentParser(description="Emite uma licenca do PrintNest.")
    ap.add_argument("--machine-id", required=True, help="ID da Maquina do cliente")
    ap.add_argument("--customer", required=True, help="Nome/e-mail do cliente")
    ap.add_argument("--edition", default="pro")
    ap.add_argument("--expires", default="", help="Validade ISO (AAAA-MM-DD) ou vazio")
    args = ap.parse_args()

    if args.expires:
        date.fromisoformat(args.expires)  # valida o formato (levanta se errado)

    lic = License(
        customer=args.customer.strip(),
        machine_id=args.machine_id.strip(),
        edition=args.edition.strip(),
        issued=date.today().isoformat(),
        expires=args.expires.strip(),
    )
    signature = _load_private().sign(lic.payload_bytes())
    key = lic.encode(signature)

    print("\n=== LICENCA (envie ao cliente) ===")
    print(key)
    print("==================================")
    print(f"cliente : {lic.customer}")
    print(f"maquina : {lic.machine_id}")
    print(f"validade: {lic.expires or 'perpetua'}")


if __name__ == "__main__":
    main()
