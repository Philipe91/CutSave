from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_DIRNAME = "PrintNest"
ENV_HOME = "PRINTNEST_HOME"


@dataclass(frozen=True)
class AppPaths:
    """Diretorios da aplicacao, derivados de um unico diretorio base (home)."""

    home: Path

    @property
    def config_file(self) -> Path:
        return self.home / "config.json"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def cache_dir(self) -> Path:
        return self.home / "cache"

    def ensure(self) -> AppPaths:
        for directory in (self.home, self.logs_dir, self.data_dir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def default(cls) -> AppPaths:
        override = os.environ.get(ENV_HOME)
        if override:
            return cls(home=Path(override))
        base = os.environ.get("APPDATA") or str(Path.home())
        return cls(home=Path(base) / APP_DIRNAME)
