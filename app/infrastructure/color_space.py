"""Que espaco de cor tem a arte que entrou.

O PDF de impressao tem que sair no MESMO espaco da origem (relato de
producao de 03/09/2026: chapa exportada imprimia com cor completamente
diferente da arte). Para isso o exportador precisa saber, antes de compor a
pagina, se as pecas daquela chapa sao CMYK — e entao desenhar as marcas do
PrintNest em K puro em vez de RGB, em vez de misturar os dois espacos no
mesmo arquivo.

A deteccao e por amostragem barata e CONSERVADORA: na duvida devolve False
(RGB, o comportamento de sempre). Errar para CMYK mudaria a cor das marcas
num arquivo RGB; errar para RGB apenas mantem o que ja existia.
"""

from __future__ import annotations

import re
from pathlib import Path

import pikepdf
from PIL import Image

# "c m y k k" / "c m y k K": quatro numeros seguidos do operador de cor CMYK
_RE_OP_CMYK = re.compile(
    rb"(?:^|[\s])"
    rb"[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+"
    rb"[kK](?=[\s/\[\]<(]|$)"
)
_IMAGENS = {".png", ".jpg", ".jpeg", ".webp"}
_cache: dict[tuple, bool] = {}


def origem_e_cmyk(path: str, page_index: int = 0) -> bool:
    """A arte deste arquivo esta em CMYK? Cacheado por (caminho, mtime, pagina)."""
    try:
        st = Path(path).stat()
    except OSError:
        return False
    chave = (str(Path(path).resolve()), st.st_mtime_ns, st.st_size, page_index)
    hit = _cache.get(chave)
    if hit is not None:
        return hit
    try:
        if Path(path).suffix.lower() in _IMAGENS:
            resultado = _imagem_e_cmyk(path)
        else:
            resultado = _pdf_e_cmyk(path, page_index)
    except Exception:
        resultado = False  # ilegivel: segue como antes (RGB)
    _cache[chave] = resultado
    return resultado


def _imagem_e_cmyk(path: str) -> bool:
    with Image.open(path) as im:
        return im.mode == "CMYK"


def _pdf_e_cmyk(path: str, page_index: int) -> bool:
    with pikepdf.open(path) as pdf:
        if not (0 <= page_index < len(pdf.pages)):
            return False
        page = pdf.pages[page_index]
        if _RE_OP_CMYK.search(_conteudo(page)):
            return True
        return _recursos_tem_cmyk(page.get("/Resources"))


def _conteudo(page) -> bytes:
    """Bytes do content stream da pagina (ele pode vir partido em varios)."""
    contents = page.get("/Contents")
    if contents is None:
        return b""
    if isinstance(contents, pikepdf.Array):
        return b"\n".join(bytes(s.read_bytes()) for s in contents)
    return bytes(contents.read_bytes())


def _recursos_tem_cmyk(recursos, profundidade: int = 0) -> bool:
    """Procura espaco de cor de 4 canais nos recursos (e nos Form XObject
    aninhados, ate 3 niveis — arte de Corel/Illustrator costuma empacotar a
    pagina inteira dentro de um Form)."""
    if recursos is None or profundidade > 3:
        return False
    for cs in (recursos.get("/ColorSpace") or {}).values():
        if _cs_tem_quatro_canais(cs):
            return True
    for xo in (recursos.get("/XObject") or {}).values():
        d = xo.stream_dict if hasattr(xo, "stream_dict") else xo
        if str(d.get("/Subtype")) == "/Image":
            if _cs_tem_quatro_canais(d.get("/ColorSpace")):
                return True
            continue
        if _RE_OP_CMYK.search(bytes(xo.read_bytes())):
            return True
        if _recursos_tem_cmyk(d.get("/Resources"), profundidade + 1):
            return True
    return False


def _cs_tem_quatro_canais(cs) -> bool:
    if cs is None:
        return False
    if str(cs) == "/DeviceCMYK":
        return True
    try:
        if isinstance(cs, pikepdf.Array) and str(cs[0]) == "/ICCBased":
            return int(cs[1].get("/N", 0)) == 4
    except Exception:
        return False
    return False
