"""Gera o arquivo de exemplo do tutorial guiado (assets/exemplo/exemplo-printnest.pdf).

O tutorial guiado (menu Tutoriais) precisa de um arquivo IGUAL para todos os
usuarios, para ensinar o fluxo com algo previsivel: adicionar -> colocar na
chapa -> gerar faca -> exportar. Este script monta esse arquivo.

O desenho e proposital, nao decorativo:
- silhueta ONDULADA (selo com lobos), nunca um retangulo: o tutorial manda o
  aluno escolher "Contorno justo" e ele precisa VER a faca abracando as ondas
  da arte. Com um selo quadrado o contorno justo sairia igual ao retangular e
  a demonstracao nao provaria nada;
- silhueta ESCURA sobre fundo BRANCO, com folga nas bordas -> a deteccao
  automatica acha a faca de primeira (e o que o tutorial promete);
- 2 paginas com artes diferentes -> mostra na pratica que um PDF vira VARIAS
  pecas na chapa.

Sem faca do cliente (linha magenta) de proposito: este e o arquivo de
DEMONSTRACAO do fluxo. Quem quer ver a faca do cliente tem o tutorial dela.

Rodar: .venv\\Scripts\\python.exe assets\\make_exemplo.py
(O build.bat nao roda este script: o PDF e versionado, nao muda a cada build.)
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infrastructure.exporters.pdf_writer import PdfWriter  # noqa: E402

HERE = Path(__file__).parent
OUT_DIR = HERE / "exemplo"
OUT = OUT_DIR / "exemplo-printnest.pdf"

W_MM, H_MM = 90.0, 90.0      # adesivo quadrado de 9 cm
MARGEM_MM = 8.0              # folga branca: a deteccao precisa dela
DPI = 300                    # arte em 300dpi (padrao de grafica)

AZUL = (37, 99, 235)         # #2563eb — acento da marca
ESCURO = (30, 58, 138)       # #1e3a8a — azul profundo


def _font(size: int):
    for name in ("segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _centralizar(draw, texto, fonte, cx, y, cor):
    x0, y0, x1, y1 = draw.textbbox((0, 0), texto, font=fonte)
    draw.text((cx - (x1 - x0) / 2, y - y0), texto, font=fonte, fill=cor)


def _silhueta(px_mm: float, lobos: int, escala: float = 1.0) -> list:
    """Contorno ondulado do selo, em PIXELS: r = base + amplitude*cos(lobos*t).

    E a razao de ser do arquivo. O contorno justo tem de sair visivelmente
    diferente do retangular, senao o passo do tutorial nao prova nada."""
    centro = W_MM * px_mm / 2
    base = (W_MM / 2 - MARGEM_MM) * px_mm * escala
    amplitude = base * 0.11
    pontos = []
    for i in range(360):
        t = math.radians(i)
        r = base + amplitude * math.cos(lobos * t)
        pontos.append((centro + r * math.cos(t), centro + r * math.sin(t)))
    return pontos


def _arte(titulo: str, subtitulo: str, fundo: tuple, lobos: int) -> Image.Image:
    """Selo ondulado com texto, sobre BRANCO (a folga vira a sangria)."""
    px_mm = DPI / 25.4
    w = h = int(W_MM * px_mm)
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.polygon(_silhueta(px_mm, lobos), fill=fundo)
    # anel claro por dentro (da profundidade e reforca a forma ondulada)
    draw.line(
        _silhueta(px_mm, lobos, escala=0.86) + [_silhueta(px_mm, lobos, 0.86)[0]],
        fill=(255, 255, 255), width=max(2, int(0.7 * px_mm)), joint="curve",
    )
    _centralizar(draw, titulo, _font(int(10 * px_mm)), w / 2, h * 0.39, (255, 255, 255))
    _centralizar(draw, subtitulo, _font(int(4.0 * px_mm)), w / 2, h * 0.57, (219, 235, 255))
    _centralizar(draw, "ARQUIVO DE EXEMPLO", _font(int(2.9 * px_mm)), w / 2, h * 0.67,
                 (219, 235, 255))
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = []
    pdf = PdfWriter()

    for i, (titulo, sub, cor, lobos) in enumerate((
        ("PrintNest", "adesivo de demonstração", AZUL, 10),
        ("Exemplo 2", "segunda arte do mesmo PDF", ESCURO, 7),
    )):
        png = OUT_DIR / f"_arte{i}.png"
        _arte(titulo, sub, cor, lobos).save(png, dpi=(DPI, DPI))
        tmp.append(png)

        pdf.new_page(W_MM, H_MM)
        pdf.place_image(str(png), 0, 0, W_MM, H_MM)

    pdf.save(str(OUT))
    for png in tmp:  # as artes viveram so para virar XObject dentro do PDF
        png.unlink(missing_ok=True)
    print(f"ok: {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
