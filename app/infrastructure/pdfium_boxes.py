"""Utilidades de leitura de PDF com pypdfium2 (motor do Chrome/PDFium).

Substitui o pdf_boxes do PyMuPDF na migração de licença (AGPL -> livre):
mesma semântica de caixas (Mídia = página inteira com sangria; Apara = área
final de corte), mas em cima do pdfium.

Convenção de coordenadas: o PDF nativo tem origem EMBAIXO-esquerda; o resto
do PrintNest pensa TOPO-esquerda (como o Qt e o antigo fitz). As funções
"_topleft" já entregam a conversão feita.
"""

from __future__ import annotations

import pypdfium2 as pdfium

from app.shared.errors import PdfImportError

_PDF_MAGIC = b"%PDF"


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


def page_box_dims_pt(page: pdfium.PdfPage, box: str) -> tuple[float, float]:
    """(largura, altura) em pt da caixa escolhida, com a MESMA ordem de
    prioridade do importador antigo: auto/trim = Apara -> Crop -> Mídia;
    media = Mídia direto. Fallback final: tamanho da página."""
    order = ("MediaBox",) if box == "media" else ("TrimBox", "CropBox", "MediaBox")
    for key in order:
        dims = raw_box(page, key)
        if dims is not None:
            x0, y0, x1, y1 = dims
            return abs(x1 - x0), abs(y1 - y0)
    return page.get_size()


def trim_clip_pdf(page: pdfium.PdfPage, box: str):
    """Região de recorte em coords PDF cruas (x0, y0, x1, y1) para a caixa
    escolhida, ou None para usar a página inteira.

    - 'media': None (página inteira, com sangria/marcas).
    - 'trim'/'auto': TrimBox se declarada; None se ausente.

    Considera apenas páginas sem rotação (os arquivos da operação usam
    /Rotate 0) — mesmo contrato do box_clip_rect antigo."""
    if box == "media":
        return None
    return raw_box(page, "TrimBox")


def clip_topleft_pt(page: pdfium.PdfPage, box: str):
    """Recorte (x0, y0, largura, altura) em pt com origem TOPO-esquerda da
    página (a convenção do preview), ou None para página inteira."""
    trim = trim_clip_pdf(page, box)
    if trim is None:
        return None
    media = raw_box(page, "MediaBox")
    if media is None:
        w, h = page.get_size()
        media = (0.0, 0.0, w, h)
    mx0, _my0, _mx1, my1 = media
    tx0, ty0, tx1, ty1 = trim
    # PDF tem origem embaixo-esquerda; o preview usa topo-esquerda (inverte Y)
    return (tx0 - mx0, my1 - ty1, tx1 - tx0, ty1 - ty0)
