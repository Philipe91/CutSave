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
    "spacing_v",
    "offset",
    "safety_inset",
    "crop",
    "rotation",
    "shared_faca",
    "reg_type",
    "reg_margin",
    "reg_diameter",
    "reg_thickness",
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
    "auto_smooth",
    "faca_mode",
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
    # paginas escolhidas do PDF (0-based). Vazio/None = TODAS — projetos
    # antigos, que nao tem o campo, continuam abrindo com o PDF inteiro.
    pages: list[int] | None = None

    def to_dict(self) -> dict:
        data = {
            "path": self.path,
            "quantity": int(self.quantity),
            "rotation": int(self.rotation),
        }
        if self.pages:
            data["pages"] = [int(p) for p in self.pages]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> ProjectFile:
        cru = data.get("pages")
        pages = None
        if isinstance(cru, (list, tuple)) and cru:
            pages = sorted({int(p) for p in cru if isinstance(p, (int, float))})
        return cls(
            path=str(data.get("path", "")),
            quantity=int(data.get("quantity", 1) or 1),
            rotation=int(data.get("rotation", 0) or 0),
            pages=pages,
        )


@dataclass
class ProjectDocument:
    """Estado persistido de um projeto .printnest (independente da UI).

    Campos ADITIVOS (projetos antigos abrem normalmente; versões antigas do
    app ignoram os campos novos):
    - ``file_overrides``: ajustes de faca POR ARQUIVO (tipo, sangria, raio...),
      caminho -> dict esparso de parametros.
    - ``faca_manual``: facas editadas a mão (ferramenta Pontos),
      caminho -> {"contours": [[[x, y], ...], ...], "w", "h", "rotation"}.
    - ``arranjo`` (QA A0): o arranjo MANUAL da chapa (duplicatas, peças
      movidas e giro por peça), exceção à regra "não guarda a produção":
      {"assinatura": [[path, qty], ...],
       "giros": {artwork_id: graus},
       "chapas": [{"comprimento": mm, "itens": [{"id", "x", "y"}, ...]}]}.
      A produção continua sendo regenerada ao abrir; o arranjo só é
      reaplicado se a assinatura (arquivos+quantidades) ainda bater.
    Sem eles, salvar/reabrir PERDIA esses ajustes (varredura 09/07; A0 24/07)."""

    files: list[ProjectFile] = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    file_overrides: dict = field(default_factory=dict)
    faca_manual: dict = field(default_factory=dict)
    arranjo: dict = field(default_factory=dict)
    version: int = PROJECT_VERSION

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "files": [f.to_dict() for f in self.files],
            "settings": dict(self.settings),
            "file_overrides": dict(self.file_overrides),
            "faca_manual": dict(self.faca_manual),
            "arranjo": dict(self.arranjo),
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
        overrides = data.get("file_overrides")
        if not isinstance(overrides, dict):
            overrides = {}
        manual = data.get("faca_manual")
        if not isinstance(manual, dict):
            manual = {}
        arranjo = data.get("arranjo")  # aditivo: projeto antigo nao tem
        if not isinstance(arranjo, dict):
            arranjo = {}
        return cls(
            files=files, settings=settings,
            file_overrides={k: v for k, v in overrides.items() if isinstance(v, dict)},
            faca_manual={k: v for k, v in manual.items() if isinstance(v, dict)},
            arranjo=arranjo,
            version=version,
        )


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
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProjectError(f"Falha ao ler o projeto: {target}") from exc
        return ProjectDocument.from_dict(data)
