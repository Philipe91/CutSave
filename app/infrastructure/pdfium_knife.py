"""Cópia "limpa" do PDF: remove os traços MAGENTA (a faca do cliente).

A linha magenta é instrução de corte, não arte — como um RIP faz com a spot
CutContour, ela nunca deve sair na impressão nem aparecer no preview. O
renderizador (pdfium_renderer) e o exportador de impressão trocam o PDF
original por esta cópia; a EXTRAÇÃO da faca continua lendo o original.

A remoção é feita com pikepdf, filtrando SÓ as operações de pintura de traço
magenta do content stream — o resto do PDF (cores, recursos, transparência)
fica intacto. (A 1ª versão usava FPDFPage_GenerateContent do pdfium, que
REESCREVE a página inteira e corrompia as cores de PDFs reais — a arte
renderizava preta. Não voltar para esse caminho.)

Limitação conhecida: só filtra o content stream da página (traços dentro de
Form XObjects não são removidos). Nos PDFs de gráfica (Corel/Illustrator) a
linha de faca sai no nível da página.
"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

import pikepdf

from app.domain.cut.vector import is_knife_color

# (caminho absoluto, mtime_ns, tamanho) -> caminho a usar (original se nada a tirar)
_cache: dict[tuple, str] = {}
# ((chave do arquivo), pagina) -> (caminho, indice) de uma copia de UMA pagina
_page_cache: dict[tuple, tuple[str, int]] = {}
_lock = threading.Lock()
_tmpdir: str | None = None

_PATH_OPS = {"m", "l", "c", "v", "y", "re", "h"}
# nomes de cor spot que as gráficas usam para a faca
_KNIFE_SPOT_NAMES = ("cutcontour", "cut", "thru-cut", "faca", "corte", "dieline")


def knife_free_pdf(path: str) -> str:
    """Caminho de uma cópia do PDF sem os traços magenta da faca.

    Sem traço magenta (ou em qualquer erro), devolve o PRÓPRIO original —
    nunca quebra a renderização/impressão. Cacheado por (caminho, mtime,
    tamanho): arquivo editado fora gera cópia nova."""
    if Path(path).suffix.lower() != ".pdf":
        return path
    key = _file_key(path)
    if key is None:
        return path
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            return hit
        result = path
        try:
            result = _strip_knife_strokes(path) or path
        except Exception:
            result = path  # qualquer problema: imprime como veio
        _cache[key] = result
        return result


def _file_key(path: str):
    """Identidade do arquivo em cache: caminho + mtime + tamanho (editado
    fora do app gera copia nova). None se o arquivo sumiu."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (os.path.abspath(path), st.st_mtime_ns, st.st_size)


def knife_free_page(path: str, page_index: int) -> tuple[str, int]:
    """(caminho, indice) de uma copia sem faca contendo SO a pagina pedida.

    Existe porque limpar o documento INTEIRO para mostrar uma pagina e caro:
    o pikepdf reparseia o content stream de todas as paginas (medido: 4,3s
    num PDF de 60 paginas A3), e a miniatura da biblioteca precisava de UMA.
    Quem varre o documento todo (a producao) continua no knife_free_pdf, que
    amortiza o strip uma vez so.

    Sem traco magenta (ou em qualquer erro), devolve o ORIGINAL e o indice
    original — nunca quebra a renderizacao."""
    if Path(path).suffix.lower() != ".pdf":
        return path, page_index
    key = _file_key(path)
    if key is None:
        return path, page_index
    with _lock:
        inteiro = _cache.get(key)
        if inteiro is not None:
            # a copia limpa do documento todo ja existe: sai de graca, e com
            # a numeracao de paginas original
            return inteiro, page_index
        hit = _page_cache.get((key, page_index))
        if hit is not None:
            return hit
        result = (path, page_index)
        try:
            out = _strip_knife_page(path, page_index)
            if out is not None:
                result = (out, 0)  # a copia tem UMA pagina: indice sempre 0
        except Exception:
            result = (path, page_index)  # qualquer problema: mostra como veio
        _page_cache[(key, page_index)] = result
        return result


def _strip_knife_page(path: str, page_index: int) -> str | None:
    """Copia de UMA pagina sem os tracos magenta; None se nao havia o que tirar
    (ou se a pagina nao existe)."""
    global _tmpdir
    with pikepdf.open(path) as src:
        if not (0 <= page_index < len(src.pages)):
            return None
        out_pdf = pikepdf.new()
        out_pdf.pages.append(src.pages[page_index])
        page = out_pdf.pages[0]
        try:
            instructions = pikepdf.parse_content_stream(page)
        except Exception:
            return None  # stream exotico: pagina fica como esta
        ops, changed = _filter_instructions(instructions, page)
        if not changed:
            return None
        page.Contents = out_pdf.make_stream(pikepdf.unparse_content_stream(ops))
        if _tmpdir is None:
            _tmpdir = tempfile.mkdtemp(prefix="printnest-faca-")
        out_path = os.path.join(
            _tmpdir,
            f"p{len(_page_cache)}-{page_index}-{Path(path).stem}-sem-faca.pdf",
        )
        out_pdf.save(out_path)
    return out_path


def _strip_knife_strokes(path: str) -> str | None:
    """Salva uma cópia sem os traços magenta; None se não havia o que tirar."""
    global _tmpdir
    removed_any = False
    with pikepdf.open(path) as pdf:
        for page in pdf.pages:
            try:
                instructions = pikepdf.parse_content_stream(page)
            except Exception:
                continue  # stream exótico: página fica como está
            out, changed = _filter_instructions(instructions, page)
            if changed:
                page.Contents = pdf.make_stream(
                    pikepdf.unparse_content_stream(out)
                )
                removed_any = True
        if not removed_any:
            return None
        if _tmpdir is None:
            _tmpdir = tempfile.mkdtemp(prefix="printnest-faca-")
        out_path = os.path.join(
            _tmpdir, f"{len(_cache)}-{Path(path).stem}-sem-faca.pdf"
        )
        pdf.save(out_path)
    return out_path


def _filter_instructions(instructions, page):
    """Reemite o content stream sem os traços magenta.

    Acompanha a cor de TRAÇO corrente (RG/K/G direto, ou CS+SCN via
    colorspace — Corel/Illustrator usam ICCBased RGB —, com pilha q/Q); os
    operadores de caminho ficam num buffer e, na hora de pintar: traço puro
    (S/s) magenta é descartado; traço+preenchimento (B/b/B*/b*) magenta vira
    só preenchimento (f/f*). Todo o resto passa intocado."""
    out: list = []
    buf: list = []
    knife = False
    cs_kind = "other"  # interpretação dos operandos de SCN/SC do traço
    stack: list[tuple[bool, str]] = []
    changed = False

    def flush() -> None:
        out.extend(buf)
        buf.clear()

    for inst in instructions:
        if isinstance(inst, pikepdf.ContentStreamInlineImage):
            flush()
            out.append(inst)
            continue
        op = str(inst.operator)
        if op in _PATH_OPS:
            buf.append(inst)
            continue
        if op == "q":
            stack.append((knife, cs_kind))
            flush()
            out.append(inst)
            continue
        if op == "Q":
            knife, cs_kind = stack.pop() if stack else (False, "other")
            flush()
            out.append(inst)
            continue
        if op == "RG":
            r, g, b = (float(v) for v in inst.operands)
            knife = is_knife_color(
                (round(r * 255), round(g * 255), round(b * 255))
            )
            cs_kind = "rgb"
            out.append(inst)
            continue
        if op == "K":
            knife = is_knife_color(_cmyk_to_rgb(inst.operands))
            cs_kind = "cmyk"
            out.append(inst)
            continue
        if op == "G":  # traço em cinza: nunca é a faca magenta
            knife = False
            cs_kind = "gray"
            out.append(inst)
            continue
        if op == "CS":  # colorspace de traço (spot de faca, ICC, device...)
            cs_kind = _stroke_cs_kind(page, inst.operands[0])
            knife = cs_kind == "spot-knife"
            out.append(inst)
            continue
        if op in ("SCN", "SC"):
            knife = _scn_is_knife(cs_kind, inst.operands)
            out.append(inst)
            continue
        if op in ("S", "s"):
            if knife:
                buf.clear()  # descarta o caminho e a pintura do traço
                changed = True
                continue
            flush()
            out.append(inst)
            continue
        if op in ("B", "b", "B*", "b*"):
            if knife:
                # preenchimento fica, traço sai. b/b* fecham o caminho antes.
                if op in ("b", "b*"):
                    buf.append(pikepdf.ContentStreamInstruction([], pikepdf.Operator("h")))
                flush()
                fill = "f" if op in ("B", "b") else "f*"
                out.append(pikepdf.ContentStreamInstruction([], pikepdf.Operator(fill)))
                changed = True
                continue
            flush()
            out.append(inst)
            continue
        # qualquer outro operador (f, n, W, cm, gs, Do, BT...): passa direto
        flush()
        out.append(inst)
    flush()
    return out, changed


def _cmyk_to_rgb(operands) -> tuple[int, int, int]:
    c, m, y, k = (float(v) for v in operands[:4])
    return (
        round(255 * (1 - c) * (1 - k)),
        round(255 * (1 - m) * (1 - k)),
        round(255 * (1 - y) * (1 - k)),
    )


def _scn_is_knife(cs_kind: str, operands) -> bool:
    """SCN/SC define a cor do traço no colorspace corrente: é magenta?"""
    if cs_kind == "spot-knife":
        return True  # qualquer tinte da spot de faca conta como faca
    if operands and str(operands[-1]).startswith("/"):
        return False  # pattern (/P0 scn): não é cor sólida
    try:
        if cs_kind == "rgb" and len(operands) >= 3:
            r, g, b = (float(v) for v in operands[:3])
            return is_knife_color(
                (round(r * 255), round(g * 255), round(b * 255))
            )
        if cs_kind == "cmyk" and len(operands) >= 4:
            return is_knife_color(_cmyk_to_rgb(operands))
    except Exception:
        return False
    return False


def _stroke_cs_kind(page, operand) -> str:
    """Classifica o colorspace de traço definido por CS: 'rgb'/'cmyk'/'gray'
    (como interpretar o SCN seguinte), 'spot-knife' (Separation de faca:
    CutContour, Faca, Corte...) ou 'other'. Falha silenciosa = 'other'."""
    name = str(operand)
    if name in ("/DeviceRGB", "/CalRGB"):
        return "rgb"
    if name == "/DeviceCMYK":
        return "cmyk"
    if name in ("/DeviceGray", "/CalGray"):
        return "gray"
    try:
        cs = page.Resources.ColorSpace[operand]
        head = str(cs[0])
        if head == "/Separation":
            spot = str(cs[1]).lstrip("/").lower()
            return "spot-knife" if any(t in spot for t in _KNIFE_SPOT_NAMES) else "other"
        if head == "/ICCBased":
            n = int(cs[1].get("/N", 0))
            return {3: "rgb", 4: "cmyk", 1: "gray"}.get(n, "other")
        if head in ("/CalRGB", "/Lab"):
            return "rgb"
        if head == "/CalGray":
            return "gray"
    except Exception:
        pass
    return "other"
