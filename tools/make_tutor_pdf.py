"""Gera o "Tutor IA — PrintNest.pdf" a partir de docs/produto/TUTOR-IA.md.

O PDF vai junto do programa (PrintNest_Build): o cliente joga o arquivo na IA
de preferência dele (ChatGPT, Claude, Gemini...) e ela vira um tutor do
PrintNest — responde "como faço X?" com os passos exatos da interface.

Usa o fitz.Story (PyMuPDF, já é dependência) com um subconjunto de Markdown:
títulos #/##, listas "-", **negrito** e parágrafos.

Uso: .venv\\Scripts\\python.exe tools/make_tutor_pdf.py [saida.pdf]
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import fitz

SRC = Path(__file__).resolve().parent.parent / "docs" / "produto" / "TUTOR-IA.md"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "Tutor IA - PrintNest.pdf"

CSS = """
body { font-family: sans-serif; font-size: 10pt; color: #111827; }
h1 { font-size: 20pt; color: #1d4ed8; margin: 0 0 6pt 0; }
h2 { font-size: 14pt; color: #1d4ed8; margin: 14pt 0 4pt 0; }
p { margin: 3pt 0; line-height: 1.35; }
li { margin: 2pt 0 2pt 14pt; line-height: 1.3; }
b { color: #0f172a; }
"""


def _inline(texto: str) -> str:
    """Escapa HTML e converte **negrito** e `codigo`."""
    out = html.escape(texto)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"`([^`]+)`", r"<b>\1</b>", out)
    return out


def md_para_html(md: str) -> str:
    """Markdown restrito -> HTML simples para o fitz.Story."""
    linhas = md.splitlines()
    partes: list[str] = []
    paragrafo: list[str] = []
    lista_aberta = False

    def fecha_paragrafo() -> None:
        nonlocal paragrafo
        if paragrafo:
            partes.append(f"<p>{_inline(' '.join(paragrafo))}</p>")
            paragrafo = []

    def fecha_lista() -> None:
        nonlocal lista_aberta
        if lista_aberta:
            partes.append("</ul>")
            lista_aberta = False

    for linha in linhas:
        crua = linha.rstrip()
        if crua.startswith("## "):
            fecha_paragrafo(); fecha_lista()
            partes.append(f"<h2>{_inline(crua[3:])}</h2>")
        elif crua.startswith("# "):
            fecha_paragrafo(); fecha_lista()
            partes.append(f"<h1>{_inline(crua[2:])}</h1>")
        elif crua.startswith("- "):
            fecha_paragrafo()
            if not lista_aberta:
                partes.append("<ul>")
                lista_aberta = True
            partes.append(f"<li>{_inline(crua[2:])}</li>")
        elif crua.startswith("  ") and lista_aberta and crua.strip():
            # continuação de item de lista (indentado)
            partes[-1] = partes[-1][:-5] + " " + _inline(crua.strip()) + "</li>"
        elif not crua.strip():
            fecha_paragrafo(); fecha_lista()
        else:
            fecha_lista()
            paragrafo.append(crua.strip())
    fecha_paragrafo(); fecha_lista()
    return "<body>" + "\n".join(partes) + "</body>"


def gerar(saida: Path = DEFAULT_OUT) -> Path:
    html_doc = md_para_html(SRC.read_text(encoding="utf-8"))
    story = fitz.Story(html=html_doc, user_css=CSS)
    writer = fitz.DocumentWriter(str(saida))
    page_rect = fitz.paper_rect("a4")
    area = page_rect + (36, 36, -36, -48)  # margens
    mais = 1
    while mais:
        device = writer.begin_page(page_rect)
        mais, _ = story.place(area)
        story.draw(device)
        writer.end_page()
    writer.close()
    return saida


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out = gerar(destino)
    paginas = fitz.open(str(out)).page_count
    print(f"gerado: {out} ({paginas} páginas)")
