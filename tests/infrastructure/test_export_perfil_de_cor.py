"""A cor tem que sair do jeito que entrou.

Relato de producao (03/09/2026): chapa exportada imprimia com cor
COMPLETAMENTE diferente da arte original. Causa medida no pipeline:

  - arte VETORIAL em PDF: passava intacta (ops CMYK/ICCBased preservados);
  - arte RASTER (JPG/PNG): o exportador reescrevia TODA imagem como
    DeviceRGB. Um JPEG CMYK de grafica virava RGB pela conversao ingenua do
    Pillow (C100 -> 0,255,255 em vez de ~0,158,224) e o RIP re-separava esse
    RGB em tres tintas: ciano puro saia sujo. Um JPEG com perfil embutido
    (Adobe RGB, ProPhoto) perdia o perfil e era lido como sRGB.

Aqui esta o contrato: o espaco de cor da ORIGEM sobrevive ate o PDF.
"""

from pathlib import Path

import pikepdf
import pypdfium2 as pdfium
import pytest
from PIL import Image, ImageCms

from app.application.dto.print_placement import (
    PrintCircle,
    PrintPlacement,
    PrintSheet,
)
from app.domain.geometry import Point2D, Size
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter

MM2PT = 72.0 / 25.4


def _jpeg_cmyk(tmp_path, nome="cmyk.jpg"):
    """JPEG CMYK como sai de grafica (Adobe APP14): ciano 100% | magenta 100%."""
    im = Image.new("CMYK", (200, 100))
    for x in range(200):
        for y in range(100):
            im.putpixel((x, y), (255, 0, 0, 0) if x < 100 else (0, 255, 0, 0))
    path = tmp_path / nome
    im.save(path, quality=95)
    return str(path)


def _jpeg_com_perfil(tmp_path, nome="perfil.jpg"):
    """JPEG RGB com perfil ICC embutido (o caso 'Adobe RGB do cliente')."""
    perfil = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    path = tmp_path / nome
    Image.new("RGB", (60, 60), (200, 40, 40)).save(path, icc_profile=perfil)
    return str(path), perfil


def _folha(src, w_mm=50.0, h_mm=25.0, **kw):
    return PrintSheet(
        (PrintPlacement(src, 0, Point2D(0, 0), Size(w_mm, h_mm)),),
        Size(w_mm, h_mm),
        **kw,
    )


def _imagens_do_pdf(path):
    """Todos os XObject de imagem da 1a pagina."""
    with pikepdf.open(path) as pdf:
        return [
            dict(xo.stream_dict)
            for xo in pdf.pages[0].Resources.XObject.values()
            if str(xo.stream_dict.get("/Subtype")) == "/Image"
        ]


def test_jpeg_cmyk_sai_cmyk(tmp_path):
    """CMYK entrou, CMYK tem que sair — sem passar por RGB."""
    saida = str(tmp_path / "out.pdf")
    PikePdfPrintExporter().export([_folha(_jpeg_cmyk(tmp_path))], saida)
    (img,) = _imagens_do_pdf(saida)
    assert str(img["/ColorSpace"]) == "/DeviceCMYK", (
        f"imagem CMYK foi reescrita como {img['/ColorSpace']}"
    )
    # JPEG CMYK da Adobe e gravado INVERTIDO: sem /Decode a arte sai quase preta
    assert [int(v) for v in img["/Decode"]] == [1, 0, 1, 0, 1, 0, 1, 0]


def test_jpeg_cmyk_mantem_a_cor_na_pagina(tmp_path):
    """A prova visual: ciano 100% continua ciano depois de exportado."""
    saida = str(tmp_path / "out.pdf")
    PikePdfPrintExporter().export([_folha(_jpeg_cmyk(tmp_path))], saida)
    doc = pdfium.PdfDocument(saida)
    try:
        px = doc[0].render(scale=2).to_pil().convert("RGB")
        r, g, b = px.getpixel((px.width // 4, px.height // 2))
    finally:
        doc.close()
    # Ciano de QUADRICROMIA (~0,174,239), nao o ciano de monitor (0,255,255)
    # que a conversao ingenua produzia: e justamente o verde saturado demais
    # que denunciava o CMYK tendo virado RGB no meio do caminho.
    assert r < 60 and 130 < g < 215 and b > 190, f"ciano 100% saiu como {(r, g, b)}"


def test_jpeg_cmyk_nao_e_recomprimido(tmp_path):
    """Passthrough DCT: os bytes originais entram sem reencode."""
    src = _jpeg_cmyk(tmp_path)
    saida = str(tmp_path / "out.pdf")
    PikePdfPrintExporter().export([_folha(src)], saida)
    (img,) = _imagens_do_pdf(saida)
    assert str(img["/Filter"]) == "/DCTDecode"


def test_perfil_icc_embutido_sobrevive(tmp_path):
    """Perfil do cliente (Adobe RGB e afins) nao pode virar sRGB anonimo."""
    src, perfil = _jpeg_com_perfil(tmp_path)
    saida = str(tmp_path / "out.pdf")
    PikePdfPrintExporter().export([_folha(src)], saida)
    with pikepdf.open(saida) as pdf:
        (xo,) = [
            x for x in pdf.pages[0].Resources.XObject.values()
            if str(x.stream_dict.get("/Subtype")) == "/Image"
        ]
        cs = xo.stream_dict["/ColorSpace"]
        assert str(cs[0]) == "/ICCBased", f"perfil descartado: virou {cs}"
        assert int(cs[1].N) == 3
        assert bytes(cs[1].read_bytes()) == perfil


def test_png_rgb_continua_rgb(tmp_path):
    """Sem regressao: o caminho RGB de sempre nao muda."""
    src = tmp_path / "a.png"
    Image.new("RGB", (40, 40), (10, 200, 90)).save(src)
    saida = str(tmp_path / "out.pdf")
    PikePdfPrintExporter().export([_folha(str(src))], saida)
    (img,) = _imagens_do_pdf(saida)
    assert str(img["/ColorSpace"]) == "/DeviceRGB"


def test_png_com_transparencia_continua_com_smask(tmp_path):
    """Sem regressao: alpha continua virando SMask."""
    src = tmp_path / "t.png"
    Image.new("RGBA", (40, 40), (10, 200, 90, 128)).save(src)
    saida = str(tmp_path / "out.pdf")
    PikePdfPrintExporter().export([_folha(str(src))], saida)
    imgs = _imagens_do_pdf(saida)
    principal = [i for i in imgs if "/SMask" in i]
    assert principal, "a transparencia perdeu a SMask"


def test_exportacao_em_imagem_sai_com_perfil_declarado(tmp_path):
    """O pdfium so rasteriza em RGB — a imagem nao volta a ser CMYK. O que ela
    TEM que fazer e dizer que RGB e esse: sem perfil, cada RIP assume um
    espaco diferente e a mesma chapa imprime diferente em cada maquina."""
    src = tmp_path / "a.png"
    Image.new("RGB", (40, 40), (10, 200, 90)).save(src)
    alvo = str(tmp_path / "chapa.png")
    (gerado,) = PikePdfPrintExporter().export_image(
        [_folha(str(src))], alvo, dpi=72, image_format="png"
    )
    with Image.open(gerado) as im:
        assert im.info.get("icc_profile"), "imagem exportada saiu sem perfil de cor"


def _pdf_cmyk_com_output_intent(tmp_path):
    """PDF de grafica: DeviceCMYK + OutputIntent declarado."""
    pdf = pikepdf.new()
    pg = pdf.add_blank_page(page_size=(100, 100))
    pg.Contents = pdf.make_stream(b"1 0 0 0 k 0 0 100 100 re f\n")
    perfil = pikepdf.Stream(pdf, b"perfil-de-saida-falso")
    perfil.stream_dict = pikepdf.Dictionary(N=4)
    pdf.Root.OutputIntents = pikepdf.Array([
        pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.OutputIntent,
            S=pikepdf.Name("/GTS_PDFX"),
            OutputConditionIdentifier=pikepdf.String("Coated FOGRA39"),
            DestOutputProfile=perfil,
        ))
    ])
    path = tmp_path / "grafica.pdf"
    pdf.save(path)
    return str(path)


def test_output_intent_da_origem_e_preservado(tmp_path):
    """Sem OutputIntent o RIP adivinha qual CMYK e — e adivinha errado."""
    saida = str(tmp_path / "out.pdf")
    PikePdfPrintExporter().export(
        [_folha(_pdf_cmyk_com_output_intent(tmp_path))], saida
    )
    with pikepdf.open(saida) as pdf:
        assert "/OutputIntents" in pdf.Root, "OutputIntent da origem foi perdido"
        oi = pdf.Root.OutputIntents[0]
        assert str(oi.OutputConditionIdentifier) == "Coated FOGRA39"


def test_marcas_de_registro_saem_em_preto_puro_em_job_cmyk(tmp_path):
    """Marca de registro em RGB vira preto de 4 tintas no RIP: fora de registro
    e o sensor optico da mesa erra a leitura. Em job CMYK tem que ser K puro."""
    folha = PrintSheet(
        (PrintPlacement(_pdf_cmyk_com_output_intent(tmp_path), 0,
                        Point2D(0, 0), Size(50, 50)),),
        Size(80, 80),
        circles=(PrintCircle(Point2D(70, 70), 6.0),),
    )
    saida = str(tmp_path / "out.pdf")
    PikePdfPrintExporter().export([folha], saida)
    with pikepdf.open(saida) as pdf:
        contents = pdf.pages[0].Contents
        fluxos = contents if isinstance(contents, pikepdf.Array) else [contents]
        conteudo = b"\n".join(bytes(s.read_bytes()) for s in fluxos).decode("latin-1")
    assert " k" in conteudo or " K" in conteudo, (
        "marca desenhada em RGB dentro de um documento CMYK"
    )
    assert "0 0 0 rg" not in conteudo and "0 0 0 RG" not in conteudo
