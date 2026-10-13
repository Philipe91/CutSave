"""Persistencia de projeto (.printnest).

Um projeto guarda *o estado de trabalho* (arquivos, quantidades, rotacoes e
parametros) de forma independente da interface, para que o usuario possa fechar
o programa e voltar exatamente ao ponto onde estava. NAO guarda a producao
gerada (faca/nesting/preview): isso e recalculado sob demanda.

Formato: JSON versionado. O campo ``version`` permite abrir projetos antigos
quando o software evoluir, sem quebrar os arquivos dos clientes.
"""

from __future__ import annotations

import contextlib
import json
import os
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
            pages = sorted({
                n for n in (_inteiro(p, -1) for p in cru
                            if isinstance(p, (int, float)) and p == p)
                if n >= 0
            }) or None
        return cls(
            path=str(data.get("path", "")),
            # projeto editado à mão / corrompido com "quantity": "abc" estourava
            # ValueError cru na abertura (auditoria 13/10/2026): cai no padrão
            quantity=max(1, _inteiro(data.get("quantity"), 1)),
            rotation=_inteiro(data.get("rotation"), 0),
            pages=pages,
        )


def _inteiro(valor, padrao: int) -> int:
    """int tolerante: número (ou texto numérico) vira int; o resto, padrão."""
    if isinstance(valor, bool) or valor is None:
        return padrao
    try:
        return int(float(valor))
    except (TypeError, ValueError, OverflowError):
        return padrao


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
    - ``page_crops``: recorte de página POR ARQUIVO,
      caminho -> {página (0-based): (esq, cima, dir, baixo) mm}.
    - ``file_sizes``: tamanho personalizado POR ARQUIVO,
      caminho -> (largura, altura) mm.
    Sem eles, salvar/reabrir PERDIA esses ajustes (varredura 09/07; A0 24/07).
    Recorte e tamanho entraram na auditoria de 13/10/2026: sem eles o arranjo
    salvo era reaplicado em peças de OUTRO tamanho (arte recortada voltava
    inteira e as posições gravadas sobrepunham as vizinhas)."""

    files: list[ProjectFile] = field(default_factory=list)
    settings: dict = field(default_factory=dict)
    file_overrides: dict = field(default_factory=dict)
    faca_manual: dict = field(default_factory=dict)
    arranjo: dict = field(default_factory=dict)
    page_crops: dict = field(default_factory=dict)
    file_sizes: dict = field(default_factory=dict)
    version: int = PROJECT_VERSION

    def to_dict(self) -> dict:
        data = {
            "version": self.version,
            "files": [f.to_dict() for f in self.files],
            "settings": dict(self.settings),
            "file_overrides": dict(self.file_overrides),
            "faca_manual": dict(self.faca_manual),
            "arranjo": dict(self.arranjo),
        }
        # chaves aditivas só quando há conteúdo: projeto sem recorte/tamanho
        # sai byte a byte igual ao de antes
        if self.page_crops:
            data["page_crops"] = {
                path: {str(int(pg)): [float(v) for v in box] for pg, box in pages.items()}
                for path, pages in self.page_crops.items()
            }
        if self.file_sizes:
            data["file_sizes"] = {
                path: [float(w), float(h)] for path, (w, h) in self.file_sizes.items()
            }
        return data

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
            page_crops=_page_crops_from_json(data.get("page_crops")),
            file_sizes=_file_sizes_from_json(data.get("file_sizes")),
            version=version,
        )


def _numeros(valores, n: int) -> tuple[float, ...] | None:
    """n números finitos (lista/tupla do JSON) ou None se vier corrompido."""
    if not isinstance(valores, (list, tuple)) or len(valores) != n:
        return None
    out = []
    for v in valores:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        out.append(f)
    return tuple(out)


def _page_crops_from_json(raw) -> dict:
    """Recortes de página; entrada corrompida é ignorada item a item (nunca
    impede a abertura do projeto, mesma regra das facas manuais)."""
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    for path, pages in raw.items():
        if not isinstance(pages, dict):
            continue
        boas: dict = {}
        for pg, box in pages.items():
            try:
                idx = int(pg)
            except (TypeError, ValueError):
                continue
            nums = _numeros(box, 4)
            if idx >= 0 and nums is not None and all(v >= 0 for v in nums):
                boas[idx] = nums
        if boas:
            out[str(path)] = boas
    return out


def _file_sizes_from_json(raw) -> dict:
    """Tamanhos por arquivo (largura, altura) mm; só valores positivos."""
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    for path, wh in raw.items():
        nums = _numeros(wh, 2)
        if nums is not None and nums[0] > 0 and nums[1] > 0:
            out[str(path)] = nums
    return out


class ProjectStore:
    """Le e grava ProjectDocument em arquivos .printnest (JSON)."""

    def save(self, path: str | Path, doc: ProjectDocument) -> None:
        # Escrita ATOMICA: grava num .tmp ao lado e troca com os.replace.
        # Escrever direto no destino truncava o arquivo — queda de energia ou
        # crash no meio do Ctrl+S destruia o projeto novo E o anterior.
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(doc.to_dict(), indent=2, ensure_ascii=False))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, target)  # atomico no NTFS (mesmo diretorio)
        except OSError as exc:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
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
