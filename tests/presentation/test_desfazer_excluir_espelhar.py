"""Delete e Ctrl+Z misturados com girar e espelhar.

O dono relatou defeitos no DELETE e no CTRL+Z logo depois que o espelho entrou
(03/08/2026). Esta e a area onde o estado se acumula: cada operacao empilha um
snapshot, e ate 03/08 o historico circulava com DOIS formatos de tupla —
operacoes de arranjo (mover, excluir, duplicar) gravavam 4 campos enquanto
girar/espelhar gravavam 6. Desfazer na ordem errada aplicava um formato sobre o
outro.

O que a suite de 1024 testes nao pegava: estes defeitos so aparecem na SEQUENCIA
certa de cliques, nao numa operacao isolada.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(tmp_path, qapp):
    import tests.presentation.test_main_window as t

    w = t._window(tmp_path)
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    w.add_paths([t._two_page_pdf(tmp_path)])
    w.generate(blocking=True)
    qapp.processEvents()
    yield w
    w.close()


def _ids(janela) -> list[str]:
    return [a.id for a in janela._result.artworks]


def test_snapshot_tem_sempre_o_mesmo_formato(janela):
    """Arranjo e giro/espelho tem de gravar o MESMO numero de campos.

    Era a causa raiz: com formatos diferentes, desfazer um passo aplicava um
    estado curto por cima de um longo e os espelhos ficavam para tras."""
    completo = janela._state_snapshot()
    antes = janela._snapshot_sheets()
    arts = list(janela._result.artworks)
    # reproduz o que _commit_arrangement monta
    de_arranjo = (
        antes, arts,
        dict(janela._piece_rotations), dict(janela._faca_manual),
        dict(janela._piece_mirrors), dict(janela._piece_faca_mirrors),
    )
    assert len(de_arranjo) == len(completo), (
        f"formatos divergentes: arranjo={len(de_arranjo)} "
        f"completo={len(completo)}"
    )


def test_espelhar_e_desfazer_devolve_o_estado(janela, monkeypatch):
    art_id = _ids(janela)[0]
    monkeypatch.setattr(janela, "_perguntar_faca", lambda ids: True)
    monkeypatch.setattr(janela, "_expandir_por_paginas", lambda ids: ids)
    monkeypatch.setattr(janela, "_selected_pieces", lambda: [
        p for p in janela._piece_items if p.artwork_id == art_id
    ])

    assert janela._piece_mirrors.get(art_id, "") == ""
    janela._mirror_selected("h")
    assert janela._piece_mirrors.get(art_id) == "h"
    assert janela._piece_faca_mirrors.get(art_id) == "h", "a faca devia acompanhar"

    janela._undo.undo()
    assert janela._piece_mirrors.get(art_id, "") == "", "Ctrl+Z nao desfez o espelho"
    assert janela._piece_faca_mirrors.get(art_id, "") == ""


def test_espelhar_so_a_impressao_nao_move_a_faca(janela, monkeypatch):
    art_id = _ids(janela)[0]
    monkeypatch.setattr(janela, "_perguntar_faca", lambda ids: False)
    monkeypatch.setattr(janela, "_expandir_por_paginas", lambda ids: ids)
    monkeypatch.setattr(janela, "_selected_pieces", lambda: [
        p for p in janela._piece_items if p.artwork_id == art_id
    ])

    janela._mirror_selected("h")
    assert janela._piece_mirrors.get(art_id) == "h"
    assert janela._piece_faca_mirrors.get(art_id, "") == "", (
        "escolhi espelhar SO a impressao e a faca espelhou junto"
    )


def test_espelhar_alterna(janela, monkeypatch):
    art_id = _ids(janela)[0]
    monkeypatch.setattr(janela, "_perguntar_faca", lambda ids: True)
    monkeypatch.setattr(janela, "_expandir_por_paginas", lambda ids: ids)
    monkeypatch.setattr(janela, "_selected_pieces", lambda: [
        p for p in janela._piece_items if p.artwork_id == art_id
    ])
    janela._mirror_selected("h")
    janela._mirror_selected("h")
    assert janela._piece_mirrors.get(art_id, "") == "", "clicar de novo devia desfazer"


def test_excluir_depois_de_espelhar_e_desfazer_duas_vezes(janela, qapp, monkeypatch):
    """A sequencia que mistura os dois formatos de snapshot."""
    art_id = _ids(janela)[0]
    monkeypatch.setattr(janela, "_perguntar_faca", lambda ids: True)
    monkeypatch.setattr(janela, "_expandir_por_paginas", lambda ids: ids)
    monkeypatch.setattr(janela, "_selected_pieces", lambda: [
        p for p in janela._piece_items if p.artwork_id == art_id
    ])
    janela._mirror_selected("h")
    espelhado = dict(janela._piece_mirrors)
    pecas_antes = len(janela._piece_items)

    # excluir a peca espelhada
    for p in janela._piece_items:
        p.setSelected(p.artwork_id == art_id)
    qapp.processEvents()
    janela._delete_selected()
    qapp.processEvents()
    assert len(janela._piece_items) < pecas_antes, "o Delete nao excluiu nada"

    janela._undo.undo()   # desfaz a exclusao
    qapp.processEvents()
    assert janela._piece_mirrors == espelhado, (
        "desfazer a exclusao perdeu o espelho da peca"
    )

    janela._undo.undo()   # desfaz o espelho
    assert janela._piece_mirrors.get(art_id, "") == ""


# ---------------------------------------------------------------------------
# Relato do dono (03/08): com o arquivo multiplicado, apagar UMA copia apagava
# TODAS na tela; o clique seguinte trazia as outras de volta.
# ---------------------------------------------------------------------------

def test_excluir_uma_copia_nao_apaga_as_outras(janela, qapp):
    """Qtd 3: selecionar UMA peca e apagar tem de tirar exatamente uma.

    O 'volta no clique seguinte' do relato indica que o ESTADO estava certo e
    o desenho e que ficava desatualizado — por isso o teste olha as duas
    coisas: quantas pecas o resultado tem, e quantas a tela mostra."""
    janela._table.cellWidget(0, 1).setValue(3)   # 2 paginas x 3 = 6 pecas
    qapp.processEvents()
    total = sum(s.item_count for s in janela._result.sheets)
    assert total == 6, f"o cenario nao montou: {total} pecas"
    assert len(janela._piece_items) == 6, (
        f"a tela ja comecou divergente: {len(janela._piece_items)} itens"
    )

    alvo = janela._piece_items[0]
    for p in janela._piece_items:
        p.setSelected(p is alvo)
    qapp.processEvents()

    janela._delete_selected()
    qapp.processEvents()

    restante = sum(s.item_count for s in janela._result.sheets)
    assert restante == 5, f"apagou {6 - restante} peca(s) em vez de 1"
    assert len(janela._piece_items) == 5, (
        f"o ESTADO ficou com {restante} pecas mas a TELA mostra "
        f"{len(janela._piece_items)} — desenho desatualizado"
    )
