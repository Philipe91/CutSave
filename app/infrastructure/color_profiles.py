"""Perfis ICC de saida disponiveis na maquina.

A exportacao em imagem oferece CMYK (estilo Corel) e, para converter, precisa
de um perfil de DESTINO. Em vez de embutir um perfil no instalador — que
seria um chute sobre a grafica do cliente, alem de questao de licenca — o
PrintNest LISTA os perfis ja instalados no Windows e deixa o operador apontar
o .icc da propria grafica.

Isso nunca fica vazio: o Windows ja acompanha o RSWOP (U.S. Web Coated), que
serve de padrao quando o cliente nao tem perfil proprio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# pasta de perfis de cor do Windows
_PASTA_SISTEMA = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
    r"System32\spool\drivers\color"
)
_EXTENSOES = (".icc", ".icm")
# preferencia de padrao: o primeiro que existir manda
_PREFERIDOS = ("rswop", "coated", "fogra", "swop")

_cache: list[PerfilCor] | None = None


@dataclass(frozen=True, slots=True)
class PerfilCor:
    """Um perfil ICC utilizavel como destino: nome legivel + arquivo."""

    nome: str
    caminho: str


def perfis_cmyk_do_sistema() -> list[PerfilCor]:
    """Perfis CMYK instalados na maquina, em ordem alfabetica. Lista vazia
    quando nao ha nenhum (ou o Pillow veio sem littleCMS)."""
    global _cache
    if _cache is None:
        _cache = sorted(_varrer_cmyk(), key=lambda p: p.nome.lower())
    return list(_cache)


def _varrer_cmyk() -> list[PerfilCor]:
    achados: list[PerfilCor] = []
    try:
        arquivos = sorted(_PASTA_SISTEMA.iterdir())
    except OSError:
        return achados
    for arquivo in arquivos:
        if arquivo.suffix.lower() not in _EXTENSOES:
            continue
        info = _info_do_perfil(str(arquivo))
        if info is None:
            continue
        espaco, descricao = info
        if espaco.strip().upper() == "CMYK":
            achados.append(PerfilCor(descricao, str(arquivo)))
    return achados


def caminho_do_perfil_padrao() -> str | None:
    """Perfil CMYK sugerido quando o operador nao escolheu nenhum.

    Prefere um nome conhecido de artes graficas (SWOP/Coated/FOGRA); nao
    achando, usa o primeiro CMYK da maquina. None quando nao ha nenhum — e
    entao a opcao CMYK simplesmente nao fica disponivel."""
    perfis = perfis_cmyk_do_sistema()
    if not perfis:
        return None
    for termo in _PREFERIDOS:
        for perfil in perfis:
            alvo = f"{Path(perfil.caminho).stem} {perfil.nome}".lower()
            if termo in alvo:
                return perfil.caminho
    return perfis[0].caminho


def descricao_do_perfil(caminho: str | None) -> str | None:
    """Nome legivel gravado dentro do .icc, ou None se o arquivo nao for um
    perfil valido (o arquivo apontado pelo cliente pode estar corrompido)."""
    if not caminho:
        return None
    info = _info_do_perfil(caminho)
    return info[1] if info else None


def perfil_e_cmyk(caminho: str | None) -> bool:
    """O perfil apontado serve como destino CMYK?"""
    if not caminho:
        return False
    info = _info_do_perfil(caminho)
    return bool(info) and info[0].strip().upper() == "CMYK"


def _info_do_perfil(caminho: str) -> tuple[str, str] | None:
    """(espaco de cor, descricao) do perfil; None se ilegivel."""
    try:
        from PIL import ImageCms

        perfil = ImageCms.getOpenProfile(caminho).profile
        descricao = perfil.profile_description or Path(caminho).stem
        return str(perfil.xcolor_space), str(descricao)
    except Exception:
        return None
