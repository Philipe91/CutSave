"""Aviso de atualizacao: consulta um manifesto publicado e diz se ha versao nova.

O app NAO se atualiza sozinho: ele avisa e abre o link. A troca do executavel
continua na mao do cliente, de proposito — atualizacao automatica exigiria
verificar a assinatura do .exe baixado, e sem essa verificacao qualquer um que
comprometesse o servidor rodaria codigo na maquina de todo cliente.

O manifesto e um JSON publicado por voce:

    {
      "versao": "1.1.0",
      "url": "https://.../PrintNest.exe",
      "notas": "Faca do cliente mais rapida; correcao no DXF."
    }

Regras que valem para tudo aqui:
- NUNCA levanta excecao. Sem internet, servidor fora, 404, JSON quebrado ou
  campo faltando: devolve None e o app segue como se nada fosse. Aviso de
  atualizacao nao pode atrapalhar quem so quer trabalhar.
- So aceita link http/https. Um manifesto adulterado nao pode fazer o app
  abrir "file:///..." nem outro esquema no sistema do cliente.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

# ENDERECO DO MANIFESTO QUE VAI DENTRO DO EXECUTAVEL.
#
# Preencha AQUI, uma vez, antes de rodar o build.bat: todo cliente que instalar
# ja sai sabendo onde conferir. Deixar isso para o config.json de cada maquina
# nao funciona — o config vive em %APPDATA% do cliente, que e exatamente onde
# voce nao alcanca, e ninguem edita JSON para receber aviso de atualizacao.
#
# Vazio = recurso desligado, o app nao faz requisicao nenhuma.
# O config.json AINDA pode sobrescrever (update_url), para atender um cliente
# especifico sem gerar outra build.
URL_MANIFESTO_PADRAO = ""

# tempo curto: isto roda na abertura do app; servidor lento nao pode virar
# espera para o usuario (a consulta ainda por cima roda fora da thread da UI)
TIMEOUT_PADRAO = 5.0
_TAMANHO_MAXIMO = 64 * 1024  # manifesto e texto curto; corta resposta gigante


@dataclass(frozen=True)
class Novidade:
    """Uma versao mais nova que a instalada."""

    versao: str
    url: str
    notas: str = ""


def versao_tupla(texto: str) -> tuple[int, ...]:
    """'1.10.2' -> (1, 10, 2). Compara por NUMERO, nao por texto.

    Sem isto, "1.10" < "1.9" (comparacao de string), e o cliente com a versao
    mais nova receberia aviso para "atualizar" para uma antiga."""
    numeros = re.findall(r"\d+", str(texto or ""))
    return tuple(int(n) for n in numeros) or (0,)


def _mais_nova(candidata: str, atual: str) -> bool:
    a, b = versao_tupla(candidata), versao_tupla(atual)
    tamanho = max(len(a), len(b))  # (1, 1) vs (1, 1, 0): completa com zeros
    a += (0,) * (tamanho - len(a))
    b += (0,) * (tamanho - len(b))
    return a > b


def url_segura(url: str) -> bool:
    """So http/https. Barra file://, e qualquer outro esquema que o sistema
    poderia abrir com um programa a partir de um manifesto adulterado."""
    return isinstance(url, str) and url.lower().startswith(("http://", "https://"))


def buscar_manifesto(url: str, timeout: float = TIMEOUT_PADRAO) -> dict | None:
    """Baixa e decodifica o manifesto. None em QUALQUER problema."""
    if not url_segura(url):
        return None
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": "PrintNest"})
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:  # noqa: S310
            dados = resposta.read(_TAMANHO_MAXIMO)
        conteudo = json.loads(dados.decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, UnicodeDecodeError):
        return None
    return conteudo if isinstance(conteudo, dict) else None


def novidade_do_manifesto(manifesto: dict | None, versao_atual: str) -> Novidade | None:
    """Novidade se o manifesto anuncia versao maior E com link utilizavel."""
    if not isinstance(manifesto, dict):
        return None
    versao = str(manifesto.get("versao") or "").strip()
    url = str(manifesto.get("url") or "").strip()
    if not versao or not url_segura(url) or not _mais_nova(versao, versao_atual):
        return None
    return Novidade(versao=versao, url=url, notas=str(manifesto.get("notas") or "").strip())


def url_efetiva(url_config: str = "") -> str:
    """Endereco que o app vai consultar.

    O config.json do cliente tem prioridade (permite apontar UM cliente para
    outro lugar sem gerar build nova); sem ele, vale o que foi embutido no
    executavel. Vazio nos dois = recurso desligado."""
    return (url_config or "").strip() or URL_MANIFESTO_PADRAO


def checar(url: str, versao_atual: str, timeout: float = TIMEOUT_PADRAO) -> Novidade | None:
    """Consulta o manifesto e devolve a novidade, ou None (inclusive em erro).

    Faz rede: chame FORA da thread da interface."""
    return novidade_do_manifesto(buscar_manifesto(url, timeout), versao_atual)
