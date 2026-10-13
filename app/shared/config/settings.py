from __future__ import annotations

import contextlib
import json
import math
import os
from dataclasses import MISSING, asdict, dataclass, fields
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
    # Giro automatico do encaixe (Modo Impressao). Campo ADITIVO: config
    # antigo abre com False. Desligado por padrao de proposito — material
    # direcional (tecido, vinil com veio) nao pode ter peca girada.
    auto_rotate: bool = False
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
    export_color_space: str = "rgb"  # espaco da exportacao em imagem: rgb | cmyk
    export_icc: str = ""  # perfil CMYK de destino (vazio = padrao da maquina)
    export_quality: int = 95  # qualidade do JPEG exportado (1-100)
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
        """Monta as preferencias aceitando SO valores do tipo do padrao.

        Campo com tipo errado (config editado a mao, versao antiga, outra
        ferramenta) volta ao padrao DELE — o resto da configuracao do
        operador fica. Antes passava direto: material_width = "abc" so
        estourava depois, no meio da tela (auditoria de 13/10/2026)."""
        if not isinstance(data, dict):
            raise TypeError("configuracao precisa ser um objeto JSON")
        valores = {}
        for campo in fields(cls):
            if campo.name not in data or campo.default is MISSING:
                continue
            valor = _coagir(data[campo.name], campo.default)
            if valor is not None:
                valores[campo.name] = valor
        return cls(**valores)


def _coagir(valor, padrao):
    """`valor` no tipo de `padrao`, ou None quando nao da para confiar nele.

    bool NAO vale como numero (True viraria 1 grau de rotacao) e numero nao
    vale como bool; int aceita float inteiro (90.0); float aceita int; numero
    nao finito (1e999 vira infinito no json) nunca e medida."""
    if isinstance(padrao, bool):
        return valor if isinstance(valor, bool) else None
    if isinstance(valor, bool):
        return None
    if isinstance(padrao, int):
        if isinstance(valor, int):
            return valor
        if isinstance(valor, float) and math.isfinite(valor) and valor.is_integer():
            return int(valor)
        return None
    if isinstance(padrao, float):
        if isinstance(valor, (int, float)) and math.isfinite(valor):
            return float(valor)
        return None
    if isinstance(padrao, str):
        return valor if isinstance(valor, str) else None
    return None


def _texto_do_config(bruto: bytes) -> str:
    """UTF-8 (com ou sem BOM — o Bloco de Notas grava BOM); se nao for UTF-8,
    o ANSI do Windows (cp1252), que e como o Bloco de Notas antigo salva.
    Perder a configuracao inteira por causa de um acento no caminho da pasta
    seria pior do que ler o arquivo do jeito que ele foi gravado."""
    try:
        return bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        return bruto.decode("cp1252")


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
        # Tudo que der errado aqui vira ConfigError: o load_or_create roda
        # ANTES do log de crash, e qualquer outra excecao fazia o .exe abrir e
        # fechar para sempre. Ja visto: [] / null no arquivo (AttributeError),
        # config salvo em ANSI pelo Bloco de Notas (UnicodeDecodeError).
        try:
            data = json.loads(_texto_do_config(self.path.read_bytes()))
            return AppSettings.from_dict(data)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            # ValueError cobre JSONDecodeError e UnicodeDecodeError
            raise ConfigError(f"Falha ao ler configuracao: {self.path}") from exc

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
