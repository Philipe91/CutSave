"""Codigos criados DEPOIS que o robo subiu tem de ser reconhecidos.

O robo fica dias no ar; os codigos de uma venda nova sao gerados no meio disso.
Antes, ele carregava a lista uma unica vez no __init__ e recusava cliente
pagante com "codigo nao reconhecido" (visto em 29/07/2026 no teste da loja).
"""

from __future__ import annotations

import json

from tools.vouchers import VoucherStore


def test_codigo_criado_depois_do_robo_subir_e_reconhecido(tmp_path):
    arquivo = tmp_path / "vouchers.json"
    robo = VoucherStore(arquivo)          # robo sobe (lista vazia)
    vendas = VoucherStore(arquivo)        # outro processo gera o codigo da venda
    codigo = vendas.generate(1, note="venda nova")[0]

    assert robo.find(codigo) is not None, "o robo nao enxergou o codigo novo"


def test_ativacao_nao_apaga_codigos_gerados_depois(tmp_path):
    # _save grava o dicionario INTEIRO: com a copia velha em memoria, a primeira
    # ativacao apagaria do disco os codigos criados depois que o robo subiu
    arquivo = tmp_path / "vouchers.json"
    vendas = VoucherStore(arquivo)
    antigo = vendas.generate(1, note="lote antigo")[0]

    robo = VoucherStore(arquivo)  # sobe conhecendo so o antigo
    novos = VoucherStore(arquivo).generate(3, note="lote novo")

    robo.redeem(antigo, "PN-AAAA-BBBB-CCCC-DDDD", "cliente", "CHAVE")

    disco = json.loads(arquivo.read_text(encoding="utf-8"))
    for codigo in novos:
        assert codigo in disco, f"{codigo} sumiu do disco depois de uma ativacao"
    assert disco[antigo]["used"] is True


def test_codigo_usado_continua_recusado(tmp_path):
    # a releitura nao pode afrouxar a regra de uso unico
    arquivo = tmp_path / "vouchers.json"
    loja = VoucherStore(arquivo)
    codigo = loja.generate(1)[0]
    loja.redeem(codigo, "PN-1111-2222-3333-4444", "primeiro", "CHAVE1")

    outro = VoucherStore(arquivo)
    assert outro.find(codigo)["used"] is True
