"""Utilidades de leitura de PDF com pypdfium2 (motor do Chrome/PDFium).

Substitui o pdf_boxes do PyMuPDF na migração de licença (AGPL -> livre):
mesma semântica de caixas (Mídia = página inteira com sangria; Apara = área
final de corte), mas em cima do pdfium.

Convenção de coordenadas: o PDF nativo tem origem EMBAIXO-esquerda; o resto
do PrintNest pensa TOPO-esquerda (como o Qt e o antigo fitz). As funções
"_topleft" já entregam a conversão feita.
"""

from __future__ import annotations

import threading

import pypdfium2 as pdfium

from app.shared.errors import PdfImportError

_PDF_MAGIC = b"%PDF"

# O PDFium NAO e thread-safe (nem para leitura): o render roda no worker de
# produção enquanto a UI extrai faca/miniaturas na thread principal. Todo
# trecho que toca pdfium segura este lock — sem ele, access violation
# (0xC0000005) intermitente, visto no teste real de 16/07. Reentrante para
# um trecho protegido poder chamar outro (ex.: strip -> extractor).
PDFIUM_LOCK = threading.RLock()


def open_pdf(path: str) -> pdfium.PdfDocument:
    """Abre um PDF, com os MESMOS erros amigáveis do importador antigo:
    arquivo que nem é PDF -> "não é um PDF válido"; resto -> "Falha ao abrir".
    """
    try:
        head = open(path, "rb").read(8)
    except OSError as exc:
        raise PdfImportError(f"Falha ao abrir PDF: {path}") from exc
    if not head.startswith(_PDF_MAGIC):
        raise PdfImportError(f"Arquivo nao e um PDF valido: {path}")
    try:
        return pdfium.PdfDocument(path)
    except Exception as exc:  # pdfium levanta PdfiumError proprio
        raise PdfImportError(f"Falha ao abrir PDF: {path}") from exc


def raw_box(page: pdfium.PdfPage, key: str):
    """Caixa CRUA (x0, y0, x1, y1) em pt, coords PDF (baixo-esquerda), ou
    None se o PDF não declara essa caixa (sem fallback automático).

    Caixa DEGENERADA (malformada/incompleta no PDF: largura ou altura ~0)
    conta como ausente — o pdfium devolve lixo nesses casos, o motor antigo
    ignorava e caia para a próxima caixa."""
    getter = {
        "MediaBox": page.get_mediabox,
        "CropBox": page.get_cropbox,
        "TrimBox": page.get_trimbox,
    }[key]
    box = getter(fallback_ok=(key == "MediaBox"))
    if box is not None and (abs(box[2] - box[0]) < 1e-3 or abs(box[3] - box[1]) < 1e-3):
        return None
    return box


def _normalizada(caixa) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = (float(v) for v in caixa)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def pagina_visivel_pdf(page: pdfium.PdfPage) -> tuple[float, float, float, float]:
    """A pagina que o leitor MOSTRA, em coords PDF cruas: CropBox ∩ MediaBox.

    E exatamente o que o pdfium rasteriza (preview, miniatura, exportacao em
    imagem) e o que o Acrobat imprime. Ate 13/10/2026 o tamanho importado usava
    a MediaBox inteira enquanto o preview mostrava so a CropBox: arquivo com
    CropBox menor entrava na chapa com um tamanho e aparecia com outro."""
    x0, y0, x1, y1 = _normalizada(page.get_bbox())
    if x1 - x0 < 1e-3 or y1 - y0 < 1e-3:
        w, h = page.get_size()
        return (0.0, 0.0, float(w), float(h))
    return (x0, y0, x1, y1)


def rotacao_da_pagina(page: pdfium.PdfPage) -> int:
    """/Rotate da pagina normalizado para 0/90/180/270 (sentido horario)."""
    try:
        return int(page.get_rotation()) % 360
    except Exception:
        return 0


def regiao_pdf(page: pdfium.PdfPage, box: str) -> tuple[float, float, float, float]:
    """A regiao da pagina que vira a ARTE, em coords PDF cruas (sem /Rotate).

    Fonte unica de verdade para o tamanho importado, o recorte do preview, o
    recorte da impressao e a origem da faca — antes cada um resolvia a caixa
    do seu jeito e os quatro discordavam em PDF com CropBox (auditoria de
    13/10/2026).

    - 'media': a pagina visivel (CropBox ∩ MediaBox; sem CropBox, a MediaBox).
    - 'trim'/'auto': a TrimBox, se declarada; senao a pagina visivel.
    """
    visivel = pagina_visivel_pdf(page)
    if box != "media":
        trim = raw_box(page, "TrimBox")
        if trim is not None:
            tx0, ty0, tx1, ty1 = _normalizada(trim)
            vx0, vy0, vx1, vy1 = visivel
            # apara que vaza da pagina visivel: o que esta fora nem renderiza
            x0, y0 = max(tx0, vx0), max(ty0, vy0)
            x1, y1 = min(tx1, vx1), min(ty1, vy1)
            if x1 - x0 > 1e-3 and y1 - y0 > 1e-3:
                return (x0, y0, x1, y1)
    return visivel


def page_box_dims_pt(page: pdfium.PdfPage, box: str) -> tuple[float, float]:
    """(largura, altura) em pt da regiao da caixa escolhida, SEM a rotacao da
    pagina (o importador troca largura/altura em /Rotate 90/270)."""
    x0, y0, x1, y1 = regiao_pdf(page, box)
    return x1 - x0, y1 - y0


def para_topo_esquerda(page: pdfium.PdfPage, box: str = "media"):
    """Funcao (x, y) PDF cru -> (x, y) em pt no referencial da ARTE: origem no
    canto TOPO-esquerdo da regiao da caixa, ja com o /Rotate aplicado.

    E o referencial do preview (o pdfium rasteriza a pagina visivel girada) e,
    por isso, o da faca: a faca que sai deste mapeamento cai em cima do pixel
    que o operador ve. A pagina visivel gira em torno de si mesma (horario,
    como o leitor mostra) e a regiao da caixa e subtraida depois."""
    cx0, cy0, cx1, cy1 = pagina_visivel_pdf(page)
    rot = rotacao_da_pagina(page)

    def na_pagina(x: float, y: float) -> tuple[float, float]:
        if rot == 90:
            return y - cy0, x - cx0
        if rot == 180:
            return cx1 - x, y - cy0
        if rot == 270:
            return cy1 - y, cx1 - x
        return x - cx0, cy1 - y

    rx0, ry0, rx1, ry1 = regiao_pdf(page, box)
    a, b = na_pagina(rx0, ry0), na_pagina(rx1, ry1)
    ox, oy = min(a[0], b[0]), min(a[1], b[1])

    def mapear(x: float, y: float) -> tuple[float, float]:
        px, py = na_pagina(x, y)
        return px - ox, py - oy

    return mapear


def trim_clip_pdf(page: pdfium.PdfPage, box: str):
    """Regiao de recorte em coords PDF cruas (x0, y0, x1, y1) para a caixa
    escolhida — a mesma `regiao_pdf` do tamanho e do preview."""
    return regiao_pdf(page, box)


def clip_topleft_pt(page: pdfium.PdfPage, box: str):
    """Recorte (x0, y0, largura, altura) em pt com origem TOPO-esquerda da
    pagina RENDERIZADA (ja girada pelo /Rotate), ou None para pagina inteira.

    Ate 13/10/2026 ignorava o /Rotate e recortava a TrimBox no lugar errado de
    pagina girada."""
    regiao = regiao_pdf(page, box)
    if regiao == pagina_visivel_pdf(page):
        return None
    mapear = para_topo_esquerda(page, "media")
    x0, y0, x1, y1 = regiao
    a, b = mapear(x0, y0), mapear(x1, y1)
    return (min(a[0], b[0]), min(a[1], b[1]), abs(b[0] - a[0]), abs(b[1] - a[1]))


def matriz_acumulada(obj) -> tuple[float, float, float, float, float, float]:
    """Matriz (a, b, c, d, e, f) do objeto ATE o espaco da pagina.

    O FPDFPageObj_GetMatrix devolve so a matriz LOCAL: um traco dentro de um
    Form XObject desenhado com `cm` deslocado saia na posicao do form, nao na
    da pagina (faca 35mm fora da arte, auditoria de 13/10/2026). Aqui sobe
    pelos forms-pai compondo cada matriz."""
    import pypdfium2.raw as pdfium_raw

    def local(o):
        m = pdfium_raw.FS_MATRIX()
        if not pdfium_raw.FPDFPageObj_GetMatrix(o.raw, m):
            return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        return (m.a, m.b, m.c, m.d, m.e, m.f)

    a, b, c, d, e, f = local(obj)
    pai = getattr(obj, "container", None)
    while pai is not None:
        pa, pb, pc, pd, pe, pf = local(pai)
        # aplica a do filho e depois a do pai (convencao do operador cm)
        a, b, c, d, e, f = (
            a * pa + b * pc, a * pb + b * pd,
            c * pa + d * pc, c * pb + d * pd,
            e * pa + f * pc + pe, e * pb + f * pd + pf,
        )
        pai = getattr(pai, "container", None)
    return (a, b, c, d, e, f)
