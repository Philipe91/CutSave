"""Preview, impressao e faca no MESMO referencial (auditoria de 13/10/2026).

Tres defeitos com a mesma raiz — cada modulo resolvia a "caixa" e a rotacao
da pagina do seu jeito:

- pagina com /Rotate 90 saia na impressao com metade da arte faltando e o
  resto esticado (o exportador girava duas vezes e encaixava a MediaBox nao
  girada no retangulo girado);
- CropBox menor que a MediaBox: tamanho, preview e recorte de impressao
  davam tres respostas diferentes;
- faca do cliente deslocada da arte quando a MediaBox nao comeca em (0,0),
  quando a CropBox e menor, ou quando o traco mora dentro de um Form XObject
  (35mm de erro nos tres casos medidos).

O teste de verdade e o que o operador ve: a cor que o preview mostra num
canto tem que sair impressa no MESMO canto, e a faca tem que cair sobre ela.
"""

from __future__ import annotations

import numpy as np
import pikepdf
import pypdfium2 as pdfium
import pytest
from app.application.dto.print_placement import PrintPlacement, PrintSheet
from app.domain.geometry import Point2D, Size
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter
from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter
from app.infrastructure.importers.pdfium_importer import PdfiumImporter
from app.infrastructure.importers.pdfium_vector_extractor import PdfiumVectorExtractor
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer

PT2MM = 25.4 / 72.0
VERMELHO = (255, 0, 0)
AZUL = (0, 0, 255)


def _pdf(path, conteudo: bytes, *, media=(0, 0, 200, 100), crop=None, trim=None,
         rotate=0, form_cm=None):
    pdf = pikepdf.new()
    pg = pdf.add_blank_page(page_size=(media[2] - media[0], media[3] - media[1]))
    pg.MediaBox = pikepdf.Array(list(media))
    if form_cm is not None:
        f = pdf.make_stream(conteudo)
        f.Type = pikepdf.Name.XObject
        f.Subtype = pikepdf.Name.Form
        f.BBox = pikepdf.Array([-1000, -1000, 1000, 1000])
        pg.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Fm0=f))
        pg.Contents = pdf.make_stream(f"q {form_cm} cm /Fm0 Do Q".encode())
    else:
        pg.Contents = pdf.make_stream(conteudo)
    if crop is not None:
        pg.CropBox = pikepdf.Array(list(crop))
    if trim is not None:
        pg.TrimBox = pikepdf.Array(list(trim))
    if rotate:
        pg.Rotate = rotate
    pdf.save(str(path))
    return str(path)


def _onde(img: np.ndarray, cor) -> tuple[int, int, int, int] | None:
    m = np.all(np.abs(img[:, :, :3].astype(int) - cor) < 60, axis=2)
    ys, xs = np.nonzero(m)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _preview(path, box) -> np.ndarray:
    data, w, h = PdfiumPageRenderer().render_raw(path, 0, dpi=72, box=box)
    return np.frombuffer(data, dtype=np.uint8).reshape(h, w, 4)[:, :, :3]


def _impresso(tmp_path, path, box, size: Size, rotate=0) -> np.ndarray:
    w, h = (size.height, size.width) if rotate in (90, 270) else (size.width, size.height)
    sheet = PrintSheet(
        (PrintPlacement(path, 0, Point2D(0, 0), Size(w, h), rotate=rotate, box=box),),
        Size(w, h),
    )
    out = tmp_path / f"saida_{box}_{rotate}.pdf"
    PikePdfPrintExporter().export([sheet], str(out))
    doc = pdfium.PdfDocument(str(out))
    try:
        return np.array(doc[0].render(scale=1).to_pil().convert("RGB"))
    finally:
        doc.close()


def _confere(img_a, img_b, cores=(VERMELHO, AZUL), tol=2):
    for cor in cores:
        a, b = _onde(img_a, cor), _onde(img_b, cor)
        assert a is not None and b is not None, f"cor {cor} sumiu: {a} x {b}"
        assert all(abs(p - q) <= tol for p, q in zip(a, b, strict=True)), f"cor {cor}: {a} x {b}"


# vermelho no canto de baixo-esquerda (coords PDF cruas), azul no oposto
_CANTOS = b"1 0 0 rg 0 0 50 50 re f 0 0 1 rg 150 50 50 50 re f"


@pytest.mark.parametrize("rot_pagina", [90, 180, 270])
@pytest.mark.parametrize("box", ["media", "trim"])
def test_pagina_com_rotate_imprime_igual_ao_preview(tmp_path, rot_pagina, box):
    src = _pdf(tmp_path / "rot.pdf", _CANTOS, rotate=rot_pagina)
    art = PdfiumImporter().import_artworks(src, box)[0]
    prev = _preview(src, box)
    # tamanho importado == tamanho do preview (100x200 pt girada 90/270)
    assert prev.shape[1] == pytest.approx(art.size.width / PT2MM, abs=1)
    assert prev.shape[0] == pytest.approx(art.size.height / PT2MM, abs=1)
    _confere(prev, _impresso(tmp_path, src, box, art.size))


@pytest.mark.parametrize("rot_peca", [90, 270])
def test_pagina_girada_e_peca_girada_compoem(tmp_path, rot_peca):
    """Giro da pagina (/Rotate) e giro da peca no canvas (horario) somam."""
    src = _pdf(tmp_path / "rot.pdf", _CANTOS, rotate=90)
    art = PdfiumImporter().import_artworks(src, "media")[0]
    prev = _preview(src, "media")
    esperado = np.ascontiguousarray(np.rot90(prev, k=-1 if rot_peca == 90 else 1))
    _confere(esperado, _impresso(tmp_path, src, "media", art.size, rotate=rot_peca))


@pytest.mark.parametrize("box", ["media", "trim"])
def test_cropbox_menor_tamanho_preview_e_impressao_concordam(tmp_path, box):
    src = _pdf(
        tmp_path / "crop.pdf",
        b"1 0 0 rg 60 60 40 40 re f 0 0 1 rg 200 200 40 40 re f",
        media=(0, 0, 300, 300), crop=(50, 50, 250, 250),
    )
    art = PdfiumImporter().import_artworks(src, box)[0]
    prev = _preview(src, box)
    assert art.size.width == pytest.approx(200 * PT2MM, abs=0.05)
    assert prev.shape[1] == pytest.approx(200, abs=1)
    assert prev.shape[0] == pytest.approx(200, abs=1)
    _confere(prev, _impresso(tmp_path, src, box, art.size))


def test_trimbox_com_rotate_recorta_no_lugar_certo(tmp_path):
    src = _pdf(
        tmp_path / "trim.pdf", _CANTOS, trim=(20, 10, 190, 95), rotate=90,
    )
    art = PdfiumImporter().import_artworks(src, "trim")[0]
    prev = _preview(src, "trim")
    assert prev.shape[1] == pytest.approx(85, abs=1)
    assert prev.shape[0] == pytest.approx(170, abs=1)
    _confere(prev, _impresso(tmp_path, src, "trim", art.size))


# ---- faca do cliente: mesmo referencial da arte --------------------------

_FACA = b"1 0 1 RG 2 w 150 150 50 50 re S"


def _faixa_da_faca(rings):
    xs = [x for r in rings for x, _ in r]
    ys = [y for r in rings for _, y in r]
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize(
    ("kw", "esperado_pt"),
    [
        (dict(media=(0, 0, 300, 300)), (150, 100, 200, 150)),
        # MediaBox fora da origem: (150-100, 400-200)
        (dict(media=(100, 100, 400, 400)), (50, 200, 100, 250)),
        # CropBox menor: a arte (e o preview) comecam no topo da CropBox
        (dict(media=(0, 0, 300, 300), crop=(0, 0, 300, 250)), (150, 50, 200, 100)),
        # faca dentro de Form XObject deslocado: a matriz do pai conta
        (dict(media=(0, 0, 300, 300), form_cm="1 0 0 1 -100 -100"), (50, 200, 100, 250)),
    ],
)
def test_faca_no_referencial_da_arte(tmp_path, kw, esperado_pt):
    src = _pdf(tmp_path / "faca.pdf", _FACA, **kw)
    esperado = tuple(v * PT2MM for v in esperado_pt)
    obtido = _faixa_da_faca(PdfiumVectorExtractor().extract_rings(src))
    assert obtido == pytest.approx(esperado, abs=0.05)
    polys = PdfVectorImporter().load(src)
    pts = [(p.x, p.y) for pw in polys for p in pw.outer.vertices]
    assert _faixa_da_faca([pts]) == pytest.approx(esperado, abs=0.05)


@pytest.mark.parametrize("rot_pagina", [90, 180, 270])
def test_faca_em_pagina_girada_cai_sobre_o_preview(tmp_path, rot_pagina):
    """Quadrado vermelho cheio exatamente sob a faca: no preview girado, a
    faca tem que contornar o vermelho."""
    src = _pdf(
        tmp_path / "faca_rot.pdf",
        b"1 0 0 rg 150 50 40 30 re f 1 0 1 RG 1 w 150 50 40 30 re S",
        media=(0, 0, 200, 100), rotate=rot_pagina,
    )
    prev = _preview(src, "media")
    x0, y0, x1, y1 = _onde(prev, VERMELHO)
    fx0, fy0, fx1, fy1 = (v / PT2MM for v in _faixa_da_faca(
        PdfiumVectorExtractor().extract_rings(src)))
    assert (fx0, fy0) == pytest.approx((x0, y0), abs=2)
    assert (fx1, fy1) == pytest.approx((x1 + 1, y1 + 1), abs=2)


def test_faca_respeita_a_caixa_de_apara(tmp_path):
    src = _pdf(tmp_path / "faca_trim.pdf", _FACA, media=(0, 0, 300, 300),
               trim=(100, 100, 250, 250))
    rings = PdfiumVectorExtractor().extract_rings(src, 0, box="trim")
    # topo da apara em y=250: (150-100, 250-200)
    assert _faixa_da_faca(rings) == pytest.approx(
        tuple(v * PT2MM for v in (50, 50, 100, 100)), abs=0.05)
