"""Gera a tela de abertura (assets/splash.png) a partir do LOGO real.

Fundo azul da marca (degrade) + o logo claro (printnest_dark.png, a versao
feita para fundos escuros) centralizado + a linha do produto. A imagem e
usada em DOIS lugares, para o cliente ver UMA abertura continua:
- a splash NATIVA do PyInstaller, durante a descompactacao do .exe (antes
  do Python iniciar) — configurada no PrintNest.spec;
- a QSplashScreen do app, enquanto a janela principal e montada.
Rodada automaticamente pelo build.bat (junto do make_icon.py).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
LOGO = HERE / "printnest_dark.png"   # logo claro (proprio para fundo escuro)
OUT = HERE / "splash.png"

W, H = 560, 320
TOP = (30, 58, 138)      # #1e3a8a — azul profundo
BOT = (37, 99, 235)      # #2563eb — acento da marca (theme.ACCENT)
TAGLINE = "Preparação de produção gráfica"
TAG_RGB = (219, 235, 255)  # #dbebff — acento suave (theme.ACCENT_SOFT)


def _gradient(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    """Degrade vertical simples (topo -> base)."""
    base = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(base)
    for y in range(h):
        t = y / max(1, h - 1)
        draw.line(
            [(0, y), (w, y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )
    return base


def _whiten_pro(logo: Image.Image) -> Image.Image:
    """Deixa o 'PRO' do logo BRANCO. No logo ele e azul (#2563eb) e, sobre o
    fundo azul da splash, fica quase invisivel. Recolore para branco apenas os
    pixels azuis do canto inferior direito (onde vive o 'PRO'), sem tocar no
    simbolo (esquerda) nem na barra azul do 'E' (meio, mais acima)."""
    logo = logo.copy()
    px = logo.load()
    w, h = logo.size
    x0, y0 = int(w * 0.58), int(h * 0.60)
    for y in range(y0, h):
        for x in range(x0, w):
            r, g, b, a = px[x, y]
            if a > 20 and b > 90 and b >= r and b >= g:  # pixel azul opaco
                px[x, y] = (255, 255, 255, a)
    return logo


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    if not LOGO.exists():
        raise SystemExit(f"logo nao encontrado: {LOGO}")
    canvas = _gradient(W, H, TOP, BOT).convert("RGBA")

    logo = Image.open(LOGO).convert("RGBA")
    logo = _whiten_pro(logo)  # 'PRO' branco (legivel no fundo azul)
    logo.thumbnail((int(W * 0.62), int(H * 0.42)), Image.LANCZOS)
    lx = (W - logo.width) // 2
    ly = int(H * 0.28)
    canvas.paste(logo, (lx, ly), logo)

    draw = ImageDraw.Draw(canvas)
    font = _font(19)
    bbox = draw.textbbox((0, 0), TAGLINE, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(
        ((W - tw) / 2, ly + logo.height + 24),
        TAGLINE, fill=TAG_RGB + (255,), font=font,
    )
    canvas.convert("RGB").save(OUT)
    print("splash gerada a partir do logo:", OUT)


if __name__ == "__main__":
    main()
