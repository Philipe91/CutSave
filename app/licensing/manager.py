"""LicenseManager: estado de licenciamento (ativacao node-locked, SEM trial).

Modelo do produto: o cliente compra, recebe uma chave presa ao PC dele e ativa
uma vez. Sem chave valida, o app nao libera (a garantia de 7 dias cobre o risco
do cliente — e comercial, nao vive no codigo). A chave e verificada offline
pela assinatura Ed25519 (o app tem so a chave publica; ver signing.py).
"""

from __future__ import annotations

import contextlib
from datetime import date
from enum import Enum

from app.licensing import license as lic_mod
from app.licensing.fingerprint import machine_id
from app.shared.config.paths import AppPaths


class LicenseState(Enum):
    LICENSED = "licensed"       # licenca valida ativa
    UNLICENSED = "unlicensed"   # sem licenca (precisa ativar)


class LicenseManager:
    """Le/valida a licenca em AppPaths.home e responde 'esta licenciado?'."""

    def __init__(self, paths: AppPaths | None = None, today: date | None = None) -> None:
        self._paths = paths or AppPaths.default()
        self._today = today or date.today()
        self.machine_id = machine_id()
        self._license = self._load_license()

    def _load_license(self):
        path = self._paths.license_file
        if not path.exists():
            return None
        with contextlib.suppress(OSError):
            return lic_mod.verify_key(
                path.read_text(encoding="utf-8"), self.machine_id, self._today
            )
        return None

    def activate(self, key: str) -> tuple[bool, str]:
        """Valida a chave para ESTE PC e, se ok, salva. Retorna (ok, mensagem)."""
        parsed = lic_mod.parse(key)
        if parsed is None:
            return False, "Chave de licença inválida (formato não reconhecido)."
        lic, _sig = parsed
        result = lic_mod.verify_key(key, self.machine_id, self._today)
        if result is None:
            if lic.machine_id != self.machine_id:
                return False, "Esta licença é de outro computador (ID não confere)."
            if lic.is_expired(self._today):
                return False, "Esta licença está expirada."
            return False, "Assinatura inválida (licença adulterada ou falsa)."
        try:
            self._paths.home.mkdir(parents=True, exist_ok=True)
            self._paths.license_file.write_text(key.strip(), encoding="utf-8")
        except OSError:
            # Sucesso sem gravar seria mentira: na proxima abertura o cliente
            # cairia de novo na tela de ativacao, sem entender o porque.
            return False, (
                "A chave é válida, mas não consegui salvá-la neste computador.\n"
                f"Verifique se o antivírus ou as permissões estão bloqueando a pasta:\n"
                f"{self._paths.home}"
            )
        self._license = result
        return True, f"Licença ativada para {result.customer}."

    def deactivate(self) -> None:
        """Remove a licenca deste PC (para transferir para outro)."""
        with contextlib.suppress(OSError):
            self._paths.license_file.unlink(missing_ok=True)
        self._license = None

    @property
    def customer(self) -> str:
        return self._license.customer if self._license else ""

    def state(self) -> LicenseState:
        return LicenseState.LICENSED if self._license else LicenseState.UNLICENSED

    def is_licensed(self) -> bool:
        return self._license is not None

    def status_text(self) -> str:
        if self._license is not None:
            exp = self._license.expires
            validade = f" · válida até {exp}" if exp else " · perpétua"
            return f"Licenciado — {self.customer}{validade}"
        return "Não licenciado — ative para usar"
