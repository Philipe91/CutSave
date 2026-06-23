from __future__ import annotations

import fitz


def _raw_box(doc, page, key: str):
    kind, value = doc.xref_get_key(page.xref, key)
    if kind == "null" or not value:
        return None
    try:
        nums = [float(n) for n in value.strip("[]").split()]
    except ValueError:
        return None
    return nums if len(nums) == 4 else None


def box_clip_rect(doc, page, box: str):
    """Retangulo de recorte (coords do fitz, topo-esquerdo) para a caixa escolhida.

    - 'media': None (pagina inteira, com sangria/marcas).
    - 'trim'/'auto': TrimBox (corte) convertido para coords do fitz; None se ausente.

    Considera apenas paginas sem rotacao (os arquivos da operacao usam /Rotate 0).
    """
    if box == "media":
        return None
    trim = _raw_box(doc, page, "TrimBox")
    if trim is None:
        return None  # sem apara -> pagina inteira
    media = _raw_box(doc, page, "MediaBox") or [0.0, 0.0, page.rect.width, page.rect.height]
    mx0, _my0, _mx1, my1 = media
    tx0, ty0, tx1, ty1 = trim
    # PDF tem origem embaixo-esquerda; fitz tem topo-esquerda (inverte Y).
    return fitz.Rect(tx0 - mx0, my1 - ty1, tx1 - mx0, my1 - ty0)
