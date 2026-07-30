from __future__ import annotations

import contextlib
import json
import os
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
    last_project: str = ""  # ultimo .printnest aberto (reabre ao iniciar)
    material_width: float = 1300.0
    material_height: float = 1500.0
    spacing: float = 5.0      # espacamento horizontal (mm)
    spacing_v: float = 5.0    # espacamento vertical (mm) - pode ser negativo
    offset: float = 3.0
    safety_inset: float = 0.0
    crop: float = 0.0
    rotation: int = 0
    shared_faca: bool = False
    reg_type: str = "none"  # none | circles | mimaki | both | squares | crosses | corner_l
    reg_margin: float = 15.0
    reg_diameter: float = 6.0  # tamanho da marca: diametro/lado/comprimento (mm)
    reg_thickness: float = 0.8  # espessura do traco das cruzes e Ls de canto (mm)
    mimaki_distance: float = 15.0
    mimaki_size: float = 15.0
    mimaki_thickness: float = 1.0
    show_rulers: bool = True
    unit: str = "cm"  # unidade de exibicao/edicao: mm | cm (interno e sempre mm)
    view_mode: str = "both"  # both | print | cut | split
    import_box: str = "media"  # media (Caixa de Midia) | trim (Caixa de Apara)
    snap_enabled: bool = True  # encaixe (snap) ao arrastar pecas
    export_dpi: int = 150  # resolucao da exportacao em imagem (PNG/JPEG)
    auto_sensitivity: float = 50.0  # faca automatica de imagem: sensibilidade (0-100)
    auto_ignore_white: bool = True  # imagens opacas: recortar ignorando fundo branco
    auto_offset_external: float = 2.0  # faca de imagem: offset externo (sangria) mm
    auto_offset_internal: float = 0.0  # faca de imagem: offset interno (recuo) mm
    auto_smooth: int = 0  # faca de imagem: suavizacao das curvas (0 = reto, 1-5 = macio)
    # faca: "auto" (decide pelo tipo da arte) | "rect" | "contour" |
    # "contour_smooth" | "contour_simplify" | "vector" (faca do cliente)
    faca_mode: str = "auto"
    # Endereco do manifesto de versao (JSON com versao/url/notas). VAZIO =
    # recurso desligado, o app nao faz requisicao nenhuma. Preencha com a URL
    # onde voce publica o versao.json; veja docs/produto/ATUALIZACAO.md.
    update_url: str = ""
    update_check_on_start: bool = True  # avisa na abertura quando ha versao nova

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
            try:
                return self.load()
            except ConfigError:
                # Config truncado/ilegivel NAO pode impedir o app de abrir
                # (com console=False o .exe "abria e fechava" para sempre).
                # Guarda o arquivo quebrado ao lado e recomeca dos padroes.
                with contextlib.suppress(OSError):
                    os.replace(self.path, f"{self.path}.corrompido")
        settings = AppSettings()
        with contextlib.suppress(ConfigError):
            self.save(settings)  # disco somente-leitura: roda com defaults em memoria
        return settings

    def load(self) -> AppSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Falha ao ler configuracao: {self.path}") from exc
        return AppSettings.from_dict(data)

    def save(self, settings: AppSettings) -> None:
        # Escrita ATOMICA (tmp + os.replace): o save acontece a cada salvar
        # projeto/exportar; interrompido no meio, truncava o config.json e o
        # app nunca mais abria. Com o replace, ou grava inteiro ou fica o antigo.
        tmp = Path(f"{self.path}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(settings.to_dict(), indent=2, ensure_ascii=False))
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except OSError as exc:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            raise ConfigError(f"Falha ao salvar configuracao: {self.path}") from exc
