"""Exportacao em imagem: cancelar no meio e acompanhar cada etapa.

A janela de acompanhamento (11/09/2026) precisa de duas coisas do
exportador: um jeito de parar entre faixas sem deixar arquivo pela metade na
pasta do cliente, e rotulos para os ~20s finais (conversao CMYK + gravacao)
que antes ficavam mudos em 97%.
"""

import pytest
from PIL import Image

from app.application.dto.print_placement import PrintPlacement, PrintSheet
from app.domain.geometry import Point2D, Size
from app.infrastructure.exporters import pikepdf_print_exporter as mod
from app.infrastructure.exporters.pikepdf_print_exporter import (
    ExportacaoCancelada,
    PikePdfPrintExporter,
)


def _folha(tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGB", (40, 40), (10, 200, 90)).save(src)
    return PrintSheet(
        (PrintPlacement(str(src), 0, Point2D(0, 0), Size(50, 25)),), Size(50, 25)
    )


def _em_varias_faixas(monkeypatch):
    """Forca a rasterizacao em varias faixas mesmo numa chapa minuscula."""
    monkeypatch.setattr(mod, "_FAIXA_LIMIAR_PX", 1)
    monkeypatch.setattr(mod, "_FAIXA_ALVO_PX", 142 * 10)  # ~10 linhas por faixa


def test_cancelar_entre_faixas_nao_deixa_arquivo(tmp_path, monkeypatch):
    _em_varias_faixas(monkeypatch)
    passos = []
    alvo = tmp_path / "chapa.png"
    with pytest.raises(ExportacaoCancelada):
        PikePdfPrintExporter().export_image(
            [_folha(tmp_path)], str(alvo), dpi=72, image_format="png",
            progresso=lambda fr, txt: passos.append(fr),
            cancelado=lambda: len(passos) >= 2,  # cancela depois da 1a faixa
        )
    assert not alvo.exists(), "cancelou e o arquivo parcial ficou na pasta"
    assert 0 < len(passos) < 8, "cancelou tarde demais: rasterizou tudo"


def test_cancelar_entre_chapas_apaga_a_chapa_ja_gravada(tmp_path):
    folha = _folha(tmp_path)
    alvo = tmp_path / "chapa.png"
    with pytest.raises(ExportacaoCancelada):
        PikePdfPrintExporter().export_image(
            [folha, folha], str(alvo), dpi=72, image_format="png",
            cancelado=lambda: (tmp_path / "chapa_01.png").exists(),
        )
    assert not list(tmp_path.glob("chapa*")), "exportacao cancelada deixou arquivo"


def test_sem_cancelar_exporta_normal(tmp_path, monkeypatch):
    _em_varias_faixas(monkeypatch)
    alvo = tmp_path / "chapa.png"
    (gerado,) = PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], str(alvo), dpi=72, image_format="png",
        cancelado=lambda: False,
    )
    assert gerado == str(alvo) and alvo.exists()


def test_rotulos_das_etapas_finais(tmp_path):
    textos = []
    PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], str(tmp_path / "chapa.jpg"), dpi=72,
        image_format="jpeg", color_space="cmyk",
        progresso=lambda fr, txt: textos.append(txt),
    )
    assert "Convertendo para CMYK…" in textos
    assert "Gravando arquivo…" in textos
    assert textos.index("Convertendo para CMYK…") < textos.index("Gravando arquivo…")


def test_rotulo_de_conversao_so_em_cmyk(tmp_path):
    textos = []
    PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], str(tmp_path / "chapa.png"), dpi=72,
        image_format="png", progresso=lambda fr, txt: textos.append(txt),
    )
    assert "Convertendo para CMYK…" not in textos
    assert "Gravando arquivo…" in textos
