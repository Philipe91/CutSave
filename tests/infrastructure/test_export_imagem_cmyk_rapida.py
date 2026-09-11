"""Exportacao em IMAGEM de arte CMYK nao pode levar minutos.

Relato de producao (11/09/2026): chapa de 1120x1750mm com 40 copias de um
JPEG CMYK (5512x2205, perfil ICC embutido) exportada em JPEG a 300 DPI
deixou o programa "Nao respondendo" por mais de 10 minutos. Medido no
pdfium, numa faixa de 8 pecas a 150 DPI:

  - imagem embutida como /ICCBased CMYK + /Decode invertido (1.2.0): 61,9s
  - a mesma imagem embutida em RGB (comportamento da 1.1.x):          1,1s

O pdfium converte imagem ICCBased de 4 canais pixel a pixel com o
LittleCMS, sem cache, e refaz isso para CADA copia em CADA faixa. Na
exportacao em PDF esse XObject CMYK e o certo (o RIP recebe as tintas
originais); na exportacao em IMAGEM ele so serve para o pdfium converter
para RGB do jeito mais caro possivel.

Contrato: no documento que vai ser RASTERIZADO, a imagem CMYK entra ja em
RGB, convertida UMA vez com gerenciamento de cor (o mesmo perfil e o mesmo
resultado que o pdfium daria) — e a cor da chapa exportada nao muda.
"""

import io

import pikepdf
import pypdfium2 as pdfium
from PIL import Image

from app.application.dto.print_placement import PrintPlacement, PrintSheet
from app.domain.geometry import Point2D, Size
from app.infrastructure.exporters.pdf_writer import PdfWriter
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter


def _jpeg_cmyk(tmp_path, nome="cmyk.jpg"):
    """JPEG CMYK como sai de grafica (Adobe APP14): ciano 100% | magenta 100%."""
    im = Image.new("CMYK", (200, 100))
    for x in range(200):
        for y in range(100):
            im.putpixel((x, y), (255, 0, 0, 0) if x < 100 else (0, 255, 0, 0))
    path = tmp_path / nome
    im.save(path, quality=95)
    return str(path)


def _imagens_do_pdf(data: bytes):
    with pikepdf.open(io.BytesIO(data)) as pdf:
        return [
            dict(xo.stream_dict)
            for xo in pdf.pages[0].Resources.XObject.values()
            if str(xo.stream_dict.get("/Subtype")) == "/Image"
        ]


def test_writer_para_raster_embute_cmyk_ja_em_rgb(tmp_path):
    """No documento que vai ser rasterizado, CMYK entra como RGB de 3 canais,
    sem /Decode: e isso que tira o pdfium do caminho lento."""
    w = PdfWriter(imagens_em_rgb=True)
    w.new_page(50, 25)
    w.place_image(_jpeg_cmyk(tmp_path), 0, 0, 50, 25)
    data = w.save_bytes()
    w.close()
    (img,) = _imagens_do_pdf(data)
    assert str(img["/ColorSpace"]) == "/DeviceRGB", (
        f"documento para raster ainda carrega {img['/ColorSpace']}"
    )
    assert "/Decode" not in img


def test_writer_padrao_continua_preservando_cmyk(tmp_path):
    """Sem regressao: o PDF de impressao (para o RIP) segue com as tintas."""
    w = PdfWriter()
    w.new_page(50, 25)
    w.place_image(_jpeg_cmyk(tmp_path), 0, 0, 50, 25)
    data = w.save_bytes()
    w.close()
    (img,) = _imagens_do_pdf(data)
    assert str(img["/ColorSpace"]) == "/DeviceCMYK"
    assert [int(v) for v in img["/Decode"]] == [1, 0, 1, 0, 1, 0, 1, 0]


def test_conversao_unica_da_a_mesma_cor_que_o_pdfium_dava(tmp_path):
    """A prova visual: ciano 100% continua ciano de QUADRICROMIA (~0,174,239)
    na chapa exportada — nao o (0,255,255) da conversao ingenua."""
    src = _jpeg_cmyk(tmp_path)
    folha = PrintSheet(
        (PrintPlacement(src, 0, Point2D(0, 0), Size(50, 25)),), Size(50, 25)
    )
    alvo = str(tmp_path / "chapa.png")
    (gerado,) = PikePdfPrintExporter().export_image(
        [folha], alvo, dpi=72, image_format="png"
    )
    with Image.open(gerado) as im:
        r, g, b = im.convert("RGB").getpixel((im.width // 4, im.height // 2))
    assert r < 60 and 130 < g < 215 and b > 190, f"ciano 100% saiu como {(r, g, b)}"
    with Image.open(gerado) as im:
        r, g, b = im.convert("RGB").getpixel((3 * im.width // 4, im.height // 2))
    # magenta de quadricromia (~236,0,140): vermelho alto, verde baixo
    assert r > 180 and g < 80 and b > 90, f"magenta 100% saiu como {(r, g, b)}"
