import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.presentation.__main__ import _cut_mode_arg  # noqa: E402


def test_flag_com_arquivo_devolve_o_caminho():
    assert _cut_mode_arg(["exe", "--modo-corte", "x.pdf"]) == "x.pdf"


def test_flag_sem_arquivo_abre_o_dialogo_vazio():
    assert _cut_mode_arg(["exe", "--modo-corte"]) == ""


def test_sem_flag_segue_o_fluxo_normal():
    assert _cut_mode_arg(["exe", "arquivo.pdf"]) is None
