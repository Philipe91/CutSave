"""Exportacao que nao termina nao estraga arquivo do cliente (13/10/2026).

- Cancelar ANTES da primeira chapa levantava UnboundLocalError (a limpeza
  usava uma variavel que ainda nao existia) em vez do aviso de cancelado.
- A limpeza apagava o caminho-alvo da chapa da vez mesmo que ESTA exportacao
  ainda nao o tivesse regravado: o IMPRESSAO_02.png de uma exportacao
  anterior sumia sem ninguem pedir.
- Falha no meio da gravacao deixava arquivo truncado — por cima do arquivo
  bom que ja estava la. Agora grava ao lado e troca no fim (os.replace).
"""

from __future__ import annotations

import pytest
from app.application.dto.print_placement import PrintPlacement, PrintSheet
from app.domain.geometry import Point2D, Size
from app.infrastructure.exporters import pikepdf_print_exporter as mod
from app.infrastructure.exporters.pdf_writer import PdfWriter
from app.infrastructure.exporters.pikepdf_print_exporter import (
    ExportacaoCancelada,
    PikePdfPrintExporter,
)
from app.shared.errors import PrintExportError
from PIL import Image


def _folha(tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGB", (40, 40), (10, 200, 90)).save(src)
    return PrintSheet(
        (PrintPlacement(str(src), 0, Point2D(0, 0), Size(50, 25)),), Size(50, 25)
    )


def _sobras(pasta):
    return sorted(p.name for p in pasta.iterdir() if p.name != "a.png")


def test_cancelar_antes_da_primeira_chapa_e_aviso_de_cancelado(tmp_path):
    antigo = tmp_path / "chapa.png"
    antigo.write_bytes(b"exportacao de ontem")
    with pytest.raises(ExportacaoCancelada):
        PikePdfPrintExporter().export_image(
            [_folha(tmp_path)], str(antigo), dpi=72, cancelado=lambda: True,
        )
    # nada desta exportacao foi gravado: o arquivo de ontem continua la
    assert antigo.read_bytes() == b"exportacao de ontem"


def test_cancelar_no_meio_da_serie_nao_apaga_chapa_de_exportacao_anterior(tmp_path):
    folha = _folha(tmp_path)
    alvo = tmp_path / "IMPRESSAO.png"
    anterior = tmp_path / "IMPRESSAO_02.png"
    anterior.write_bytes(b"chapa 2 de ontem")
    with pytest.raises(ExportacaoCancelada):
        PikePdfPrintExporter().export_image(
            [folha, folha], str(alvo), dpi=72,
            cancelado=lambda: (tmp_path / "IMPRESSAO_01.png").exists(),
        )
    assert not (tmp_path / "IMPRESSAO_01.png").exists()  # desta exportacao: sai
    assert anterior.read_bytes() == b"chapa 2 de ontem"   # nao regravada: fica
    assert _sobras(tmp_path) == ["IMPRESSAO_02.png"]


def test_falha_ao_gravar_preserva_o_arquivo_anterior(tmp_path, monkeypatch):
    folha = _folha(tmp_path)
    alvo = tmp_path / "chapa.png"
    alvo.write_bytes(b"arquivo bom")
    original = Image.Image.save

    def save_que_quebra(self, fp, *a, **kw):
        original(self, fp, *a, **kw)  # grava um pedaco...
        raise OSError("disco cheio")  # ...e falha

    monkeypatch.setattr(Image.Image, "save", save_que_quebra)
    with pytest.raises(PrintExportError):
        PikePdfPrintExporter().export_image([folha], str(alvo), dpi=72)
    assert alvo.read_bytes() == b"arquivo bom"
    assert _sobras(tmp_path) == ["chapa.png"]  # nenhum temporario esquecido


def test_falha_na_segunda_chapa_remove_a_primeira_desta_exportacao(tmp_path, monkeypatch):
    folha = _folha(tmp_path)
    chamadas = []
    original = mod.PikePdfPrintExporter._rasterizar_pagina

    def rasteriza(page, *a, **kw):
        chamadas.append(1)
        if len(chamadas) == 2:
            raise PrintExportError("sem memoria")
        return original(page, *a, **kw)

    monkeypatch.setattr(mod.PikePdfPrintExporter, "_rasterizar_pagina", staticmethod(rasteriza))
    with pytest.raises(PrintExportError):
        PikePdfPrintExporter().export_image(
            [folha, folha], str(tmp_path / "chapa.png"), dpi=72)
    assert _sobras(tmp_path) == []  # meia serie nao fica na pasta


def test_falha_ao_gravar_pdf_preserva_o_arquivo_anterior(tmp_path, monkeypatch):
    alvo = tmp_path / "impressao.pdf"
    alvo.write_bytes(b"%PDF de ontem")

    def save_que_quebra(self, path):
        with open(path, "wb") as fh:
            fh.write(b"%PDF-1.7 trunc")
        raise OSError("disco cheio")

    monkeypatch.setattr(PdfWriter, "save", save_que_quebra)
    with pytest.raises(PrintExportError):
        PikePdfPrintExporter().export([_folha(tmp_path)], str(alvo))
    assert alvo.read_bytes() == b"%PDF de ontem"
    assert _sobras(tmp_path) == ["impressao.pdf"]
