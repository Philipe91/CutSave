"""PDF de origem com a caixa invertida NÃO pode sair espelhado na impressão.

Relato real de produção (31/07/2026, teste com um arquivo de cliente): ao
exportar, a arte saía de cabeça para baixo e as marcas de registro ficavam do
lado errado — mas só com *alguns* arquivos. A faca saía correta, porque não
passa pela matriz de encaixe do PDF.

Causa: o PDF **não exige** que as caixas venham ordenadas. Escrever a MediaBox
como `[0 297 210 0]` é legal e todo visualizador normaliza sozinho, então o
arquivo abre certo em qualquer lugar e ninguém desconfia da origem. A matriz de
encaixe calculava a largura como `x1-x0`: com a caixa invertida isso dá
negativo, a escala fica negativa e a arte entra espelhada.

Por que dói: o operador só descobre depois de imprimir e cortar — a mesa lê as
marcas e corta no lugar errado. É chapa inteira perdida.
"""

from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest
from app.application.dto.print_placement import PrintPlacement, PrintSheet
from app.domain.geometry import Point2D, Size
from app.infrastructure.exporters.pdf_writer import PdfWriter, bbox_normalizada
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter


def _arte_assimetrica(destino) -> str:
    """100x100mm com um retângulo preto SÓ no topo-esquerdo.

    Assimétrica de propósito: com arte simétrica o espelhamento não aparece."""
    w = PdfWriter()
    w.new_page(100, 100)
    w.draw_rect_filled(5, 5, 30, 20)
    w.save(str(destino))
    w.close()
    return str(destino)


def _com_caixa_invertida(origem: str, destino) -> str:
    with pikepdf.open(origem) as pdf:
        x0, y0, x1, y1 = (float(v) for v in pdf.pages[0].MediaBox)
        pdf.pages[0].MediaBox = pikepdf.Array([x0, y1, x1, y0])
        pdf.save(str(destino))
    return str(destino)


def _exportar(origem: str, destino) -> str:
    sheet = PrintSheet(
        placements=(
            PrintPlacement(
                source_path=origem, source_page=0,
                position=Point2D(0, 0), size=Size(100, 100),
            ),
        ),
        size=Size(100, 100),
    )
    PikePdfPrintExporter().export([sheet], str(destino))
    return str(destino)


def _centro_da_tinta(pdf_path: str) -> tuple[float, float]:
    """(x, y) do centro do que foi pintado, em fração da página."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf_path)
    try:
        img = doc[0].render(scale=1.5).to_pil().convert("L")
    finally:
        doc.close()
    largura, altura = img.size
    px = img.load()
    xs = [
        (x, y)
        for y in range(altura)
        for x in range(largura)
        if px[x, y] < 128
    ]
    assert xs, "a página saiu em branco"
    return (
        sum(p[0] for p in xs) / len(xs) / largura,
        sum(p[1] for p in xs) / len(xs) / altura,
    )


def test_caixa_invertida_nao_espelha_a_impressao(tmp_path):
    normal = _arte_assimetrica(tmp_path / "fonte.pdf")
    invertida = _com_caixa_invertida(normal, tmp_path / "fonte_invertida.pdf")

    centro_ok = _centro_da_tinta(_exportar(normal, tmp_path / "saida_ok.pdf"))
    centro_inv = _centro_da_tinta(_exportar(invertida, tmp_path / "saida_inv.pdf"))

    assert centro_ok[1] < 0.5, "a fonte normal ja saiu errada — o teste nao vale"
    assert centro_inv[1] == pytest.approx(centro_ok[1], abs=0.02), (
        f"arte ESPELHADA: a marca deveria ficar em y={centro_ok[1]:.2f} e "
        f"saiu em y={centro_inv[1]:.2f}"
    )
    assert centro_inv[0] == pytest.approx(centro_ok[0], abs=0.02)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ((0, 0, 210, 297), (0, 0, 210, 297)),      # ja ordenada: nao mexe
        ((0, 297, 210, 0), (0, 0, 210, 297)),      # invertida em Y
        ((210, 0, 0, 297), (0, 0, 210, 297)),      # invertida em X
        ((210, 297, 0, 0), (0, 0, 210, 297)),      # invertida nos dois
        ((10, 20, 30, 40), (10, 20, 30, 40)),      # deslocada da origem
    ],
)
def test_normalizacao_da_caixa(entrada, esperado):
    assert bbox_normalizada(entrada) == pytest.approx(esperado)


def test_caixa_invertida_nao_engole_o_recorte_de_borda(tmp_path):
    """Efeito colateral da mesma causa: com a caixa invertida, a checagem
    `(x1-x0) > 2*crop` dava negativo e o recorte de borda era ignorado em
    silêncio — a arte saía com a sangria que o operador mandou tirar."""
    normal = _arte_assimetrica(tmp_path / "fonte.pdf")
    invertida = _com_caixa_invertida(normal, tmp_path / "fonte_inv.pdf")

    recorte = PikePdfPrintExporter._source_clip(invertida, 0, "media", 5.0)
    x0, y0, x1, y1 = recorte
    assert x1 > x0 and y1 > y0, "recorte saiu com as coordenadas trocadas"
    inteira = PikePdfPrintExporter._source_clip(invertida, 0, "media", 0.0)
    assert (x1 - x0) < (inteira[2] - inteira[0]), "o recorte de borda foi ignorado"


# ---------------------------------------------------------------------------
# Sentido do giro: a impressao tem de girar para o MESMO lado que a tela.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("rot", "quadrante"),
    [
        (0, ("TOPO", "ESQUERDA")),
        (90, ("TOPO", "DIREITA")),
        (180, ("FUNDO", "DIREITA")),
        (270, ("FUNDO", "ESQUERDA")),
    ],
)
def test_giro_da_impressao_acompanha_o_da_tela(tmp_path, rot, quadrante):
    """Uma marca no topo-esquerdo, girada em sentido HORARIO.

    O canvas gira a arte com `QTransform().rotate(+angulo)`, que e horario.
    Ate 31/07/2026 a exportacao girava ao contrario: a peca caia no lugar e no
    tamanho certos (o retangulo destino e o mesmo nos dois sentidos), mas a
    ARTE saia 180 graus virada em relacao ao que o operador via — so nas pecas
    com 90 ou 270. Como a faca nao passa por essa matriz, ela saia certa, e o
    material era impresso de cabeca para baixo em relacao as marcas de
    registro. So se descobre depois de cortar: e chapa inteira perdida.
    """
    origem = _arte_assimetrica(tmp_path / "fonte.pdf")
    sheet = PrintSheet(
        placements=(
            PrintPlacement(
                source_path=origem, source_page=0,
                position=Point2D(0, 0), size=Size(100, 100), rotate=rot,
            ),
        ),
        size=Size(100, 100),
    )
    destino = tmp_path / f"rot{rot}.pdf"
    PikePdfPrintExporter().export([sheet], str(destino))

    x, y = _centro_da_tinta(str(destino))
    obtido = ("TOPO" if y < 0.5 else "FUNDO", "ESQUERDA" if x < 0.5 else "DIREITA")
    assert obtido == quadrante, (
        f"giro de {rot} graus levou a arte para {obtido[0]}-{obtido[1]}; "
        f"a tela mostra {quadrante[0]}-{quadrante[1]}"
    )


# ---------------------------------------------------------------------------
# Espelho (1.1) na impressao. Ordem canonica: espelhar PRIMEIRO, girar depois.
# ---------------------------------------------------------------------------

def _quadrante_esperado(mirror: str, rot: int) -> tuple[str, str]:
    """Para onde vai uma marca que comeca no TOPO-ESQUERDO.

    Calculado pela regra, nao decorado: espelha e depois gira em sentido
    horario. Se o codigo e o teste discordarem, um dos dois esta errado — e e
    exatamente essa divergencia que queremos ver."""
    v, h = "TOPO", "ESQUERDA"
    if "h" in mirror:
        h = "DIREITA" if h == "ESQUERDA" else "ESQUERDA"
    if "v" in mirror:
        v = "FUNDO" if v == "TOPO" else "TOPO"
    for _ in range((rot // 90) % 4):  # cada passo = 90 graus horario
        v, h = ("TOPO", "DIREITA") if (v, h) == ("TOPO", "ESQUERDA") else \
               ("FUNDO", "DIREITA") if (v, h) == ("TOPO", "DIREITA") else \
               ("FUNDO", "ESQUERDA") if (v, h) == ("FUNDO", "DIREITA") else \
               ("TOPO", "ESQUERDA")
    return v, h


@pytest.mark.parametrize("mirror", ["", "h", "v", "hv"])
@pytest.mark.parametrize("rot", [0, 90, 180, 270])
def test_espelho_e_giro_na_impressao(tmp_path, mirror, rot):
    origem = _arte_assimetrica(tmp_path / "fonte.pdf")
    sheet = PrintSheet(
        placements=(
            PrintPlacement(
                source_path=origem, source_page=0,
                position=Point2D(0, 0), size=Size(100, 100),
                rotate=rot, mirror=mirror,
            ),
        ),
        size=Size(100, 100),
    )
    destino = tmp_path / f"m{mirror or 'nada'}_r{rot}.pdf"
    PikePdfPrintExporter().export([sheet], str(destino))

    x, y = _centro_da_tinta(str(destino))
    obtido = ("TOPO" if y < 0.5 else "FUNDO", "ESQUERDA" if x < 0.5 else "DIREITA")
    assert obtido == _quadrante_esperado(mirror, rot), (
        f"espelho={mirror or 'nenhum'} giro={rot}: arte foi para "
        f"{obtido[0]}-{obtido[1]}"
    )


@pytest.mark.parametrize("mirror", ["h", "v", "hv"])
def test_espelho_pedido_nao_e_desfeito_pela_normalizacao_da_caixa(tmp_path, mirror):
    """A invariante que protege o defeito de 31/07 nos DOIS sentidos.

    `bbox_normalizada` existe para impedir que uma caixa de pagina mal ordenada
    vire espelho acidental. Ela NAO pode, no caminho contrario, engolir um
    espelho que o operador pediu — inclusive quando o arquivo de origem e
    justamente um dos que vem com a caixa invertida."""
    normal = _arte_assimetrica(tmp_path / "fonte.pdf")
    invertida = _com_caixa_invertida(normal, tmp_path / "fonte_inv.pdf")

    quadrantes = []
    for origem in (normal, invertida):
        sheet = PrintSheet(
            placements=(
                PrintPlacement(
                    source_path=origem, source_page=0,
                    position=Point2D(0, 0), size=Size(100, 100), mirror=mirror,
                ),
            ),
            size=Size(100, 100),
        )
        destino = tmp_path / f"{Path(origem).stem}_{mirror}.pdf"
        PikePdfPrintExporter().export([sheet], str(destino))
        x, y = _centro_da_tinta(str(destino))
        quadrantes.append(
            ("TOPO" if y < 0.5 else "FUNDO", "ESQUERDA" if x < 0.5 else "DIREITA")
        )

    assert quadrantes[0] == _quadrante_esperado(mirror, 0)
    assert quadrantes[1] == quadrantes[0], (
        "a caixa invertida mudou o resultado do espelho — as duas coisas se "
        "misturaram, que e exatamente o que a normalizacao existe para impedir"
    )
