"""Gera o icone do app (assets/printnest.ico) a partir do LOGO real.

Usa o simbolo da marca (assets/printnest_symbol.png) — o "S" azul + play —,
centraliza com uma pequena folga e exporta um .ico multi-resolucao. Esse .ico
e o icone do executavel (PrintNest.spec) E o icone da janela/barra de tarefas
(app.presentation.__main__). Rodado automaticamente pelo build.bat.
"""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
SRC = HERE / "printnest_symbol.png"   # simbolo quadrado da marca
OUT = HERE / "printnest.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]
MARGIN = 0.10  # 10% de folga em volta do simbolo (respiro do icone)


def _framed(symbol: Image.Image, size: int) -> Image.Image:
    """Centraliza o simbolo num canvas quadrado transparente, com folga."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner = max(1, int(size * (1 - 2 * MARGIN)))
    art = symbol.copy()
    art.thumbnail((inner, inner), Image.LANCZOS)
    off = ((size - art.width) // 2, (size - art.height) // 2)
    canvas.paste(art, off, art)
    return canvas


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"logo nao encontrado: {SRC}")
    symbol = Image.open(SRC).convert("RGBA")
    frames = [_framed(symbol, s) for s in SIZES]
    # o maior frame carrega os demais tamanhos embutidos no .ico
    frames[-1].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
    print("icone gerado a partir do logo:", OUT)


if __name__ == "__main__":
    main()
