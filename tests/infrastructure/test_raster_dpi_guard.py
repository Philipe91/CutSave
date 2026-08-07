"""Rasterizacao em DPI alto: peso da exportacao e limites reais.

Historico (06-07/08/2026), porque explica o que estes testes NAO testam:

Chapa pesada em JPEG a 500 DPI saia com pecas faltando, calada — o pdfium
desiste do objeto que nao consegue alocar. Tentamos duas defesas que foram
descartadas pelo Philipe, com razao:

  1. RECUSAR exportar acima de um teto — tirava do dono do arquivo a decisao
     sobre o proprio arquivo;
  2. CONFERIR o resultado e avisar que podia ter saido errado — a heuristica
     acusou falha num arquivo INTEIRO (290 DPI), e aviso que erra queima a
     confianca em todos os outros avisos do programa.

O que sobrou e so o que e fato: a rasterizacao em faixas (que reduz o problema
na raiz), um indicador de QUANTO VAI DEMORAR antes de comecar, e o limite do
formato. Nao existe, de proposito, nenhuma mensagem dizendo que o arquivo pode
sair errado.
"""

from pathlib import Path

import fitz
import pytest
from PIL import Image

from app.application.dto.print_placement import PrintPlacement, PrintSheet
from app.domain.geometry import Point2D, Size
from app.infrastructure.exporters import pikepdf_print_exporter as mod
from app.infrastructure.exporters.pikepdf_print_exporter import (
    PikePdfPrintExporter,
    peso_exportacao,
)
from app.shared.errors import PrintExportError

MM2PT = 72.0 / 25.4


def _source_pdf(tmp_path, w_pt=200.0, h_pt=140.0):
    """Origem com conteudo espalhado (blocos pretos em grade)."""
    doc = fitz.open()
    page = doc.new_page(width=w_pt, height=h_pt)
    for y in range(10, int(h_pt) - 20, 30):
        for x in range(10, int(w_pt) - 20, 30):
            page.draw_rect(fitz.Rect(x, y, x + 18, y + 18), color=(0, 0, 0),
                           fill=(0, 0, 0))
    path = tmp_path / "src.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _sheet(src, w_mm=200.0, h_mm=140.0):
    art = Size(w_mm, h_mm)
    return PrintSheet((PrintPlacement(src, 0, Point2D(0, 0), art),), Size(w_mm, h_mm))


# ---- 1. o indicador de peso --------------------------------------------

def test_peso_sobe_conforme_o_dpi(monkeypatch):
    monkeypatch.setattr(mod, "_orcamento_px", lambda: 100_000_000)
    niveis = [peso_exportacao(1000.0, 700.0, d, "png")[0] for d in (50, 200, 250, 400)]
    assert niveis == ["rapido", "normal", "demorado", "muito_demorado"]


def test_peso_sempre_diz_o_tamanho_em_pixels():
    _nivel, _rotulo, tamanho = peso_exportacao(300.0, 200.0, 300, "png")
    assert tamanho == "3.543 × 2.362 px"


@pytest.mark.parametrize("dpi", [50, 300, 600, 1200])
def test_o_indicador_nunca_fala_em_arquivo_errado(dpi, monkeypatch):
    """A regra que nasceu do relato de 06/08: o programa não promete defeito.

    Prometer erro que talvez não aconteça custa a confiança do cliente em todo
    o resto que o PrintNest diz."""
    monkeypatch.setattr(mod, "_orcamento_px", lambda: 10_000_000)
    _nivel, rotulo, tamanho = peso_exportacao(2000.0, 1000.0, dpi, "png")
    proibido = ("errad", "falta", "falha", "perde", "defeito", "corromp", "risco")
    junto = f"{rotulo} {tamanho}".lower()
    assert not any(p in junto for p in proibido), junto


def test_lado_maior_que_o_jpeg_guarda_e_impossivel(monkeypatch):
    monkeypatch.setattr(mod, "_orcamento_px", lambda: 10_000_000_000)
    assert peso_exportacao(3000.0, 200.0, 1200, "jpeg")[0] == "impossivel"
    # o mesmo tamanho em PNG passa: o limite e do formato, nao da chapa
    assert peso_exportacao(3000.0, 200.0, 1200, "png")[0] != "impossivel"


# ---- 2. exportar nunca e bloqueado por peso ----------------------------

def test_peso_alto_nao_impede_a_exportacao(tmp_path, monkeypatch):
    """Quem decide exportar e o dono do arquivo."""
    monkeypatch.setattr(mod, "_orcamento_px", lambda: 1_000_000)
    src = _source_pdf(tmp_path)
    destino = tmp_path / "IMPRESSAO.jpg"
    assert peso_exportacao(200.0, 140.0, 200, "jpeg")[0] == "muito_demorado"
    gerados = PikePdfPrintExporter().export_image(
        [_sheet(src)], str(destino), dpi=200, image_format="jpeg"
    )
    assert gerados == [str(destino)]
    assert destino.exists(), "bloqueou a exportacao do cliente"


def test_lado_maior_que_o_formato_aguenta_recusa(tmp_path, monkeypatch):
    """Unico caso sem saida: sem arquivo possivel, recusar e o certo — e a
    mensagem tem de dizer o porque e a saida (PNG)."""
    monkeypatch.setattr(mod, "_JPEG_LADO_MAX_PX", 500)
    src = _source_pdf(tmp_path)
    destino = tmp_path / "IMPRESSAO.jpg"
    with pytest.raises(PrintExportError) as erro:
        PikePdfPrintExporter().export_image(
            [_sheet(src)], str(destino), dpi=300, image_format="jpeg"
        )
    assert "JPEG" in str(erro.value) and "PNG" in str(erro.value)
    assert not destino.exists()


def test_dentro_do_normal_grava_com_o_dpi_no_arquivo(tmp_path):
    src = _source_pdf(tmp_path)
    destino = tmp_path / "IMPRESSAO.jpg"
    gerados = PikePdfPrintExporter().export_image(
        [_sheet(src)], str(destino), dpi=150, image_format="jpeg"
    )
    assert gerados == [str(destino)]
    with Image.open(destino) as img:
        assert img.info.get("dpi", (0, 0))[0] == pytest.approx(150, abs=1)


# ---- 3. faixas == tacada unica -----------------------------------------

def test_faixas_dao_o_mesmo_pixel_que_a_tacada_unica(tmp_path, monkeypatch):
    """A correcao de raiz: rasterizar em faixas derruba o pico de memoria do
    pdfium sem mudar UM pixel do resultado."""
    from PIL import ImageChops

    src = _source_pdf(tmp_path)
    inteiro = tmp_path / "inteiro.png"
    picado = tmp_path / "picado.png"
    exp = PikePdfPrintExporter()
    exp.export_image([_sheet(src)], str(inteiro), dpi=200, image_format="png")
    # forca o caminho em faixas com o MESMO conteudo e o MESMO DPI
    monkeypatch.setattr(mod, "_FAIXA_LIMIAR_PX", 1)
    monkeypatch.setattr(mod, "_FAIXA_ALVO_PX", 400_000)
    exp.export_image([_sheet(src)], str(picado), dpi=200, image_format="png")
    with Image.open(inteiro) as a, Image.open(picado) as b:
        assert a.size == b.size
        dif = ImageChops.difference(a.convert("L"), b.convert("L"))
        # nenhuma emenda, nenhum deslocamento de faixa
        assert dif.point(lambda v: 255 if v > 12 else 0).getbbox() is None


# ---- 4. progresso ------------------------------------------------------

def test_progresso_vai_do_comeco_ao_fim(tmp_path):
    src = _source_pdf(tmp_path)
    vistos = []
    PikePdfPrintExporter().export_image(
        [_sheet(src)], str(tmp_path / "a.png"), dpi=120, image_format="png",
        progresso=lambda fr, txt: vistos.append((fr, txt)),
    )
    fracoes = [fr for fr, _ in vistos]
    assert fracoes[0] == 0.0 and fracoes[-1] == pytest.approx(1.0)
    assert fracoes == sorted(fracoes), "progresso andou para tras"
    assert all(isinstance(t, str) for _, t in vistos)


def test_varias_chapas_numeram_e_reportam_cada_uma(tmp_path):
    src = _source_pdf(tmp_path)
    textos = set()
    gerados = PikePdfPrintExporter().export_image(
        [_sheet(src), _sheet(src)], str(tmp_path / "IMPRESSAO.png"),
        dpi=100, image_format="png",
        progresso=lambda fr, txt: textos.add(txt),
    )
    assert [Path(p).name for p in gerados] == ["IMPRESSAO_01.png", "IMPRESSAO_02.png"]
    assert "Chapa 1 de 2" in textos and "Chapa 2 de 2" in textos
