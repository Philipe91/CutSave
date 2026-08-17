"""QA do defeito relatado em 2026-08-17: letras de acrilico saindo facetadas.

Medicao no arquivo do cliente ANTES da correcao: 720 nos e 365 curvas Bezier
entravam; 2.089 vertices e ZERO curvas saiam. Este teste trava o numero.

A arte do cliente NAO e versionada: o teste a procura em tests/fixtures/ e
depois em ~/Pictures, e pula se nao achar. Assim a suite roda em qualquer
maquina e continua valendo como prova na maquina do Philipe.

Ver docs/especificacoes/CURVAS-ORIGINAIS-MODO-CORTE.md
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import ezdxf
import pytest

from app.application.use_cases.run_true_shape_nesting import (
    placed_cut_contours,
    to_nesting_shapes,
)
from app.domain.geometry import Point2D
from app.domain.model.placement import PlacedItem
from app.infrastructure.exporters.dxf_exporter import DxfExporter
from app.infrastructure.exporters.svg_layout_exporter import write_layout_svg
from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter

_NOME = "Logo Hospital Santa Lucia for printnest.pdf"
_CANDIDATOS = (
    Path(__file__).resolve().parents[1] / "fixtures" / _NOME,
    Path(os.path.expanduser("~")) / "Pictures" / _NOME,
)
# medido no arquivo do cliente: 365 curvas + 318 retas = 683 trechos, 720 nos
_CURVAS_DO_ORIGINAL = 365
_NOS_DO_ORIGINAL = 720


def _arquivo() -> Path:
    for p in _CANDIDATOS:
        if p.is_file():
            return p
    pytest.skip(f"arte do cliente ausente (procurei em: {', '.join(map(str, _CANDIDATOS))})")


def _pecas_posicionadas():
    """Cada peca posta numa posicao fixa — o alvo aqui e a GRAVACAO, nao o
    encaixe, entao nao roda o packer (mais rapido e deterministico)."""
    shapes = to_nesting_shapes(PdfVectorImporter().load(str(_arquivo())))
    return [
        placed_cut_contours(s, PlacedItem(s.artwork_id, Point2D(400.0 * i, 10.0), 0.0))
        for i, s in enumerate(shapes)
    ]


def test_letras_do_cliente_entram_e_saem_com_curva():
    """As 365 curvas do PDF do Corel chegam ao contorno importado."""
    shapes = PdfVectorImporter().load(str(_arquivo()))

    curvos = sum(
        sum(1 for s in ring.curves if not s.is_line())
        for shape in shapes
        for ring in (shape.outer, *shape.holes)
    )
    assert curvos == _CURVAS_DO_ORIGINAL, (
        f"esperava as {_CURVAS_DO_ORIGINAL} curvas do original, veio {curvos}"
    )


def test_svg_para_o_corel_sai_com_curva_e_sem_explosao_de_nos():
    """O SVG do 'Enviar para o Corel' grava C, e a contagem de nos fica na
    ordem do original (720), nao dos 2.089 vertices achatados."""
    pieces = _pecas_posicionadas()

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "layout.svg")
        write_layout_svg(pieces, 12000.0, 3000.0, out)
        d = Path(out).read_text(encoding="utf-8")

    assert " C " in d, "o SVG do Corel voltou a sair sem curva"
    nos = d.count(" C ") + d.count(" L ")
    assert nos < _NOS_DO_ORIGINAL * 1.5, (
        f"explosao de nos: {nos} (o original tem ~{_NOS_DO_ORIGINAL})"
    )


def test_dxf_sai_com_spline():
    contours = [c for piece in _pecas_posicionadas() for c in piece]

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "corte.dxf")
        DxfExporter().export(contours, out)
        doc = ezdxf.readfile(out)

    assert list(doc.modelspace().query("SPLINE")), "nenhum spline no DXF"
