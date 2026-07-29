"""Codigos de compra (vouchers) — a "prova de compra" da ativacao automatica.

O robo de ativacao (tools/license_robot.py) so emite licenca para quem
apresenta um codigo valido e nao usado. O dono gera codigos em lote
(tools/gen_vouchers.py) e entrega UM por venda (WhatsApp/e-mail, vale ate do
celular). Cada codigo e de uso unico e fica preso ao primeiro PC que ativar
(reenvio da mesma chave se o mesmo PC pedir de novo — cliente perdeu o e-mail).

Armazenamento: JSON em tools/licenses_emitidas/vouchers.json (gitignored).
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime
from pathlib import Path

# mesmo alfabeto do ID da maquina: sem 0/O/1/I (evita confusao ao digitar)
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEFAULT_STORE = Path(__file__).with_name("licenses_emitidas") / "vouchers.json"

_CODE_BODY = re.compile(r"^[A-Z0-9]{8}$")


def new_code() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"PNC-{body[:4]}-{body[4:]}"


def normalize(code: str) -> str:
    """Aceita variacoes do cliente (minusculas, espacos, sem tracos)."""
    raw = re.sub(r"[^A-Z0-9]", "", code.upper())
    if raw.startswith("PNC"):
        raw = raw[3:]
    if not _CODE_BODY.match(raw):
        return ""
    return f"PNC-{raw[:4]}-{raw[4:]}"


class VoucherStore:
    """Guarda os codigos e o estado de uso (JSON, escrita atomica)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else DEFAULT_STORE
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        tmp.replace(self._path)

    def generate(self, count: int = 1, note: str = "") -> list[str]:
        """Cria 'count' codigos novos (nao usados) e persiste."""
        codes: list[str] = []
        for _ in range(max(1, count)):
            code = new_code()
            while code in self._data:  # colisao e improvavel, mas barata de tratar
                code = new_code()
            self._data[code] = {
                "created": datetime.now().isoformat(timespec="seconds"),
                "note": note,
                "used": False,
                "machine_id": "",
                "customer": "",
                "key": "",
                "used_at": "",
            }
            codes.append(code)
        self._save()
        return codes

    def find(self, code: str) -> dict | None:
        """Registro do codigo (normalizado) ou None se nao existir.

        RELE o arquivo antes de procurar: o robo fica dias no ar e os codigos
        de uma venda nova sao gerados DEPOIS que ele subiu. Sem esta releitura
        ele so conhecia os codigos que existiam quando iniciou, e recusava
        cliente pagante com "codigo nao reconhecido"."""
        self._load()
        return self._data.get(normalize(code))

    def redeem(self, code: str, machine_id: str, customer: str, key: str) -> None:
        """Marca o codigo como usado por 'machine_id' e guarda a chave emitida.

        Rele antes de gravar porque o _save escreve o dicionario INTEIRO: com a
        copia velha em memoria, a primeira ativacao apagaria do disco todo
        codigo gerado depois que o robo subiu."""
        self._load()
        rec = self._data[normalize(code)]
        rec.update(
            used=True,
            machine_id=machine_id,
            customer=customer,
            key=key,
            used_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._save()
