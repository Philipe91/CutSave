"""Gera assets/printnest_dark.png — a logo para TEMAS ESCUROS.

Regra: pixels ESCUROS (texto navy "PRINTNEST" e a parte preta do símbolo)
viram branco-gelo; os azuis da marca ficam. Também limpa o anti-alias feito
para fundo claro (semitransparências escuras que viravam "sujeira"/miolos
estranhos sobre fundo escuro).

Rode uma vez: .venv\\Scripts\\python.exe assets/make_logo_dark.py
"""

from pathlib import Path

from PIL import Image

SRC = Path(__file__).with_name("printnest.png")
DST = Path(__file__).with_name("printnest_dark.png")
CLARO = (245, 247, 250)  # branco-gelo (nao branco puro: menos "estouro")

im = Image.open(SRC).convert("RGBA")
px = im.load()
w, h = im.size
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if a == 0:
            continue
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        azul = b > r + 30 and b > 90  # azul da marca: preserva
        if not azul and lum >= 235:
            # branco quase-puro (miolos do P/R e fundo pintado): vira
            # TRANSPARENTE — no claro era invisível, no escuro entupia a letra
            px[x, y] = (r, g, b, 0)
        elif not azul and lum < 110:
            # escuro (texto/simbolo preto) -> claro, mantendo o alpha do traço
            px[x, y] = (*CLARO, a)
        elif not azul and a < 255 and lum < 170:
            # anti-alias escuro de borda (feito p/ fundo claro): clareia
            px[x, y] = (*CLARO, a)
im.save(DST, optimize=True)
print(f"gerada: {DST} ({w}x{h})")
