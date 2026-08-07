"""O motor do Modo Impressao nao pode piorar sem alguem perceber.

O Philipe autorizou mexer no `MaxRectsPacker` (economia de chapa e rotacao
automatica) com a condicao de haver um ponto de volta. Tag no Git e o botao de
voltar; ISTO aqui e o que responde a pergunta que importa: ficou melhor?

O baseline em `docs/qa/BASELINE-NESTING-IMPRESSAO.json` guarda o aproveitamento
medido ANTES de mexer. Este teste refaz a medicao a cada rodada da suite e
reprova se qualquer caso piorou — nao a media, QUALQUER caso. Motor que melhora
a media piorando um cenario real so troca um desperdicio por outro.

Melhorou? Rode `python scripts/nesting_baseline.py --gravar` e commite o JSON
novo JUNTO com a mudanca do motor: o numero novo passa a ser o piso.
"""

from __future__ import annotations

import pytest

from scripts.nesting_baseline import (
    CASOS,
    carregar_baseline,
    comparar,
    medir,
    medir_todos,
)


def test_baseline_existe_e_cobre_todos_os_casos():
    baseline = carregar_baseline()
    assert set(baseline) == {c.nome for c in CASOS}, (
        "baseline fora de sincronia com os casos — rode "
        "scripts/nesting_baseline.py --gravar"
    )


def test_o_motor_nao_piorou_em_nenhum_caso():
    problemas = comparar(medir_todos(), carregar_baseline())
    assert not problemas, "aproveitamento piorou:\n  - " + "\n  - ".join(problemas)


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.nome)
def test_toda_peca_pedida_e_colocada(caso):
    """Aproveitamento alto deixando peça de fora não é ganho, é peça perdida."""
    m = medir(caso)
    assert m["pecas"] == m["pecas_pedidas"]


def test_medicao_e_estavel():
    """Mesma entrada, mesmo resultado: sem isso o baseline não vale nada."""
    assert medir_todos() == medir_todos()
