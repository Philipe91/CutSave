"""Localizacao de recursos empacotados (icone, assets).

Funciona tanto rodando do codigo-fonte quanto a partir do executavel gerado
pelo PyInstaller, que extrai os dados em ``sys._MEIPASS`` em tempo de execucao.
"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Caminho absoluto de um recurso, no dev e no executavel (PyInstaller)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    # raiz do projeto: dois niveis acima de app/shared/
    return Path(__file__).resolve().parents[2] / relative
