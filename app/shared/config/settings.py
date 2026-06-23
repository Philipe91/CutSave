from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.shared.errors import ConfigError

DEFAULT_LANGUAGE = "pt-BR"
DEFAULT_LOG_LEVEL = "INFO"


@dataclass
class AppSettings:
    """Preferencias persistidas da aplicacao."""

    language: str = DEFAULT_LANGUAGE
    log_level: str = DEFAULT_LOG_LEVEL
    last_dir: str = ""
    material_width: float = 1300.0
    material_height: float = 1500.0
    spacing: float = 5.0
    offset: float = 3.0
    safety_inset: float = 0.0
    crop: float = 0.0
    rotation: int = 0
    shared_faca: bool = False
    reg_type: str = "none"  # none | circles | mimaki
    reg_margin: float = 15.0
    reg_diameter: float = 6.0
    mimaki_distance: float = 15.0
    mimaki_size: float = 15.0
    mimaki_thickness: float = 1.0
    show_rulers: bool = True
    view_mode: str = "both"  # both | print | cut | split

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


class SettingsStore:
    """Le e grava AppSettings em um arquivo JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load_or_create(self) -> AppSettings:
        if self.path.exists():
            return self.load()
        settings = AppSettings()
        self.save(settings)
        return settings

    def load(self) -> AppSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Falha ao ler configuracao: {self.path}") from exc
        return AppSettings.from_dict(data)

    def save(self, settings: AppSettings) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(settings.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise ConfigError(f"Falha ao salvar configuracao: {self.path}") from exc
