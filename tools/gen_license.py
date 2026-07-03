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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.issuer import issue_license  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Emite uma licenca do PrintNest.")
    ap.add_argument("--machine-id", required=True, help="ID da Maquina do cliente")
    ap.add_argument("--customer", required=True, help="Nome/e-mail do cliente")
    ap.add_argument("--edition", default="pro")
    ap.add_argument("--expires", default="", help="Validade ISO (AAAA-MM-DD) ou vazio")
    args = ap.parse_args()

    key = issue_license(
        args.machine_id, args.customer, edition=args.edition, expires=args.expires
    )

    print("\n=== LICENCA (envie ao cliente) ===")
    print(key)
    print("==================================")
    print(f"cliente : {args.customer.strip()}")
    print(f"maquina : {args.machine_id.strip()}")
    print(f"validade: {args.expires.strip() or 'perpetua'}")


if __name__ == "__main__":
    main()
