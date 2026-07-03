"""Impressao digital do PC (machine id): identificador estavel e unico que
'prende' a licenca ao computador. No Windows usa o MachineGuid do registro
(unico por instalacao do Windows, muito estavel); fora do Windows cai para o
MAC + nome da maquina. O valor e um hash — nao expoe dado real do usuario.
"""

from __future__ import annotations

import hashlib
import platform
import sys
import uuid

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # base32 sem 0/O/1/I (legivel)


def _raw_source() -> str:
    """Coleta a fonte estavel do fingerprint (antes do hash)."""
    parts: list[str] = [platform.machine()]
    if sys.platform == "win32":
        try:
            import winreg  # so no Windows

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            parts.append(str(guid))
        except OSError:
            parts.append(platform.node())
    else:
        parts.append(platform.node())
    # MAC como reforco (uuid.getnode e estavel na maioria dos casos)
    parts.append(format(uuid.getnode(), "x"))
    return "|".join(parts)


def _b32(data: bytes, length: int) -> str:
    """Codifica bytes num alfabeto base32 legivel (sem caracteres ambiguos)."""
    num = int.from_bytes(data, "big")
    out = []
    for _ in range(length):
        out.append(_ALPHABET[num & 31])
        num >>= 5
    return "".join(reversed(out))


def machine_id(source: str | None = None) -> str:
    """ID legivel e DETERMINISTICO do PC, ex.: 'PN-XXXX-XXXX-XXXX-XXXX'.

    O MESMO valor e calculado pelo app (mostra ao cliente) e conferido contra a
    licenca. 'source' e injetavel para testes.
    """
    src = source if source is not None else _raw_source()
    digest = hashlib.sha256(src.encode("utf-8")).digest()
    code = _b32(digest[:10], 16)  # 16 chars base32
    groups = [code[i:i + 4] for i in range(0, 16, 4)]
    return "PN-" + "-".join(groups)
