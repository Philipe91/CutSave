"""Gera codigos de compra (vouchers) em lote — um por venda.

Uso:
    .venv\\Scripts\\python.exe tools/gen_vouchers.py -n 10 --note "lote julho"

Os codigos ficam em tools/licenses_emitidas/vouchers.json (gitignored). Entregue
UM codigo por cliente na venda; o robo (license_robot.py) troca o codigo pela
licenca automaticamente.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.vouchers import VoucherStore  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera codigos de compra do PrintNest")
    ap.add_argument("-n", "--count", type=int, default=1, help="quantos codigos")
    ap.add_argument("--note", default="", help="anotacao do lote (ex.: 'lote julho')")
    args = ap.parse_args()

    store = VoucherStore()
    codes = store.generate(args.count, note=args.note)
    print(f"{len(codes)} codigo(s) gerado(s) — entregue UM por venda:\n")
    for c in codes:
        print(f"  {c}")
    print("\nGuardados em tools/licenses_emitidas/vouchers.json")


if __name__ == "__main__":
    main()
