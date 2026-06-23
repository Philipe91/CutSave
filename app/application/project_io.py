"""Persistencia de projeto (.printnest).

Um projeto guarda *o estado de trabalho* (arquivos, quantidades, rotacoes e
parametros) de forma independente da interface, para que o usuario possa fechar
o programa e voltar exatamente ao ponto onde estava. NAO guarda a producao
gerada (faca/nesting/preview): isso e recalculado sob demanda.

Formato: JSON versionado. O campo ``version`` permite abrir projetos antigos
quando o software evoluir, sem quebrar os arquivos dos clientes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.shared.errors import ProjectError

PROJECT_VERSION = 1
PROJECT_EXTENSION = ".printnest"

# Parametros do projeto que espelham campos de AppSettings. Sao salvos por
# projeto para que cada trabalho carregue com as proprias configuracoes.
PROJECT_SETTING_KEYS = (
    "material_width",
    "material_height",
    "spacing",
    "offset",
    "safety_inset",
    "crop",
    "rotation",
    "shared_faca",
    "reg_type",
    "reg_margin",
    "reg_diameter",
    "mimaki_distance",
    "mimaki_size",
    "mimaki_thickness",
    "show_rulers",
    "view_mode",
    "import_box",
    "snap_enabled",
    "export_dpi",
    "auto_sensitivity",
    "auto_ignore_white",
    "auto_offset_external",
    "auto_offset_internal",
)


@dataclass
class ProjectFile:
    """Um arquivo do projeto: caminho, quantidade e rotacao individual.

    A rotacao individual e guardada para compatibilidade futura; o motor atual
    aplica rotacao global, entao na abertura prevalece o parametro global.
    """

    path: str
    quantity: int = 1
    rotation: int = 0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "quantity": int(self.quantity),
            "rotation": int(self.rotation),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectFile:
        return cls(
            path=str(data.get("path", "")),
            quantity=int(data.get("quantity", 1) or 1),
            rotation=int(data.get("rotation", 0) or 0),
        )


@dataclass
class ProjectDocument:
    """Estado persistido de um projeto .printnest (independente da UI)."""

    files: list[ProjectFile] = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    version: int = PROJECT_VERSION

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "files": [f.to_dict() for f in self.files],
            "settings": dict(self.settings),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectDocument:
        if not isinstance(data, dict):
            raise ProjectError("Arquivo de projeto invalido.")
        version = data.get("version")
        if not isinstance(version, int):
            raise ProjectError("Projeto sem versao valida.")
        if version > PROJECT_VERSION:
            raise ProjectError(
                f"Projeto criado em uma versao mais nova ({version}). "
                "Atualize o PrintNest para abri-lo."
            )
        raw_files = data.get("files") or []
        files = [ProjectFile.from_dict(f) for f in raw_files if isinstance(f, dict)]
        settings = data.get("settings")
        if not isinstance(settings, dict):
            settings = {}
        return cls(files=files, settings=settings, version=version)


class ProjectStore:
    """Le e grava ProjectDocument em arquivos .printnest (JSON)."""

    def save(self, path: str | Path, doc: ProjectDocument) -> None:
        target = Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(doc.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise ProjectError(f"Falha ao salvar o projeto: {target}") from exc

    def load(self, path: str | Path) -> ProjectDocument:
        target = Path(path)
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProjectError(f"Projeto nao encontrado: {target}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectError(f"Falha ao ler o projeto: {target}") from exc
        return ProjectDocument.from_dict(data)
