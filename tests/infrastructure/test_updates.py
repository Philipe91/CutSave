"""Aviso de atualizacao: comparacao de versao, link seguro e falha silenciosa."""

from __future__ import annotations

import json

import pytest
from app.infrastructure import updates


# ---- comparacao de versao ----
def test_compara_por_numero_nao_por_texto():
    # "1.10" < "1.9" como TEXTO. Se comparasse assim, quem ja esta na 1.10
    # receberia aviso para "atualizar" para a 1.9.
    assert updates.versao_tupla("1.10.2") == (1, 10, 2)
    m = {"versao": "1.10.0", "url": "https://x/y.exe"}
    assert updates.novidade_do_manifesto(m, "1.9.0") is not None


@pytest.mark.parametrize(
    ("publicada", "instalada", "avisa"),
    [
        ("1.1.0", "1.0.0", True),
        ("1.0.1", "1.0.0", True),
        ("1.0.0", "1.0.0", False),   # igual: nao perturba
        ("0.9.0", "1.0.0", False),   # mais velha: nunca avisa
        ("1.1", "1.1.0", False),     # 1.1 == 1.1.0 (completa com zeros)
        ("1.1.1", "1.1", True),
    ],
)
def test_so_avisa_quando_e_realmente_mais_nova(publicada, instalada, avisa):
    m = {"versao": publicada, "url": "https://x/y.exe"}
    assert (updates.novidade_do_manifesto(m, instalada) is not None) is avisa


# ---- link seguro ----
@pytest.mark.parametrize(
    "url",
    ["file:///C:/Windows/System32/calc.exe", "javascript:alert(1)",
     "ftp://x/y", "", "  ", "C:\\Windows\\calc.exe"],
)
def test_link_fora_de_http_e_recusado(url):
    # o aviso ABRE o link no sistema do cliente: um manifesto adulterado nao
    # pode fazer o app disparar outro esquema
    assert not updates.url_segura(url)
    assert updates.novidade_do_manifesto({"versao": "9.9.9", "url": url}, "1.0.0") is None


def test_link_http_e_https_passam():
    assert updates.url_segura("http://x/y.exe")
    assert updates.url_segura("https://x/y.exe")


# ---- manifesto ruim nunca quebra ----
@pytest.mark.parametrize(
    "manifesto",
    [None, {}, {"versao": "1.1.0"}, {"url": "https://x/y.exe"},
     {"versao": "", "url": "https://x/y.exe"}, [], "texto", 42],
)
def test_manifesto_incompleto_ou_torto_devolve_none(manifesto):
    assert updates.novidade_do_manifesto(manifesto, "1.0.0") is None


def test_notas_sao_opcionais():
    m = {"versao": "1.1.0", "url": "https://x/y.exe"}
    assert updates.novidade_do_manifesto(m, "1.0.0").notas == ""
    m["notas"] = "Correcao no DXF"
    assert updates.novidade_do_manifesto(m, "1.0.0").notas == "Correcao no DXF"


# ---- de onde vem o endereco ----
def test_endereco_embutido_vale_para_todo_cliente(monkeypatch):
    # o config.json vive em %APPDATA% da maquina do CLIENTE, que e onde o dono
    # do produto nao alcanca: o endereco tem de sair dentro do executavel
    monkeypatch.setattr(updates, "URL_MANIFESTO_PADRAO", "https://site/versao.json")
    assert updates.url_efetiva("") == "https://site/versao.json"
    assert updates.url_efetiva("   ") == "https://site/versao.json"


def test_config_do_cliente_sobrescreve_o_embutido(monkeypatch):
    # atender UM cliente em outro endereco sem gerar build nova
    monkeypatch.setattr(updates, "URL_MANIFESTO_PADRAO", "https://site/versao.json")
    assert updates.url_efetiva("https://outro/v.json") == "https://outro/v.json"


def test_sem_nenhum_dos_dois_fica_desligado(monkeypatch):
    monkeypatch.setattr(updates, "URL_MANIFESTO_PADRAO", "")
    assert updates.url_efetiva("") == ""


# ---- rede: falha SEMPRE em silencio ----
def test_url_invalida_nao_faz_requisicao_nem_levanta():
    assert updates.buscar_manifesto("file:///etc/passwd") is None
    assert updates.checar("", "1.0.0") is None


def test_erro_de_rede_devolve_none(monkeypatch):
    # sem internet, servidor fora, DNS quebrado: o app nao pode nem piscar
    def explode(*_a, **_k):
        raise OSError("sem rede")

    monkeypatch.setattr(updates.urllib.request, "urlopen", explode)
    assert updates.buscar_manifesto("https://x/versao.json") is None
    assert updates.checar("https://x/versao.json", "1.0.0") is None


def test_json_invalido_devolve_none(monkeypatch):
    _falso_urlopen(monkeypatch, b"isto nao e json")
    assert updates.buscar_manifesto("https://x/versao.json") is None


def test_manifesto_valido_vira_novidade(monkeypatch):
    corpo = json.dumps(
        {"versao": "2.0.0", "url": "https://x/PrintNest.exe", "notas": "Novidades"}
    ).encode()
    _falso_urlopen(monkeypatch, corpo)
    n = updates.checar("https://x/versao.json", "1.0.0")
    assert n.versao == "2.0.0"
    assert n.url == "https://x/PrintNest.exe"
    assert n.notas == "Novidades"


def test_resposta_gigante_e_cortada(monkeypatch):
    # servidor devolvendo um arquivo enorme nao pode encher a memoria do cliente
    lido = {}

    class _Resposta:
        def read(self, n=None):
            lido["limite"] = n
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda *a, **k: _Resposta())
    updates.buscar_manifesto("https://x/versao.json")
    assert lido["limite"] == updates._TAMANHO_MAXIMO


def _falso_urlopen(monkeypatch, corpo: bytes) -> None:
    class _Resposta:
        def read(self, _n=None):
            return corpo

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda *a, **k: _Resposta())
