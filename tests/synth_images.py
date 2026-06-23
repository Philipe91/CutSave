"""Imagens sinteticas para validar a importacao e a faca automatica (V1.4).

Cada funcao grava um arquivo e devolve o caminho (str). DPI default 150 para
medidas previsiveis: 150 px = 1 polegada = 25.4 mm  ->  1 px = 0.16933 mm.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

DPI = 150
MM_PER_PX = 25.4 / DPI  # ~0.16933


def _rgba(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def png_alpha_disc(dirpath, name="alpha_disc.png", dpi=DPI):
    """PNG transparente: disco vermelho opaco r=40px centrado em 200x100."""
    im = _rgba(200, 100)
    ImageDraw.Draw(im).ellipse([60, 10, 140, 90], fill=(200, 30, 30, 255))
    p = str(Path(dirpath) / name)
    im.save(p, dpi=(dpi, dpi))
    return p


def png_alpha_shadow(dirpath, name="alpha_shadow.png", dpi=DPI):
    """PNG com sombra: disco opaco r=30 + halo fraco (alpha 40) ate r=55."""
    im = _rgba(200, 200)
    d = ImageDraw.Draw(im)
    d.ellipse([45, 45, 155, 155], fill=(0, 0, 0, 40))     # sombra fraca r~55
    d.ellipse([70, 70, 130, 130], fill=(20, 20, 20, 255))  # produto solido r=30
    p = str(Path(dirpath) / name)
    im.save(p, dpi=(dpi, dpi))
    return p


def jpg_white_square(dirpath, name="white_square.jpg", dpi=DPI):
    """JPG fundo branco: quadrado preto 60px centrado em 120x120 (sem margem util)."""
    im = Image.new("RGB", (120, 120), (255, 255, 255))
    ImageDraw.Draw(im).rectangle([30, 30, 89, 89], fill=(0, 0, 0))
    p = str(Path(dirpath) / name)
    im.save(p, dpi=(dpi, dpi))
    return p


def jpg_white_margin(dirpath, name="white_margin.jpg", dpi=DPI):
    """JPG com margem branca larga: quadrado preto 40px em 200x200 branco."""
    im = Image.new("RGB", (200, 200), (255, 255, 255))
    ImageDraw.Draw(im).rectangle([80, 80, 119, 119], fill=(10, 10, 10))
    p = str(Path(dirpath) / name)
    im.save(p, dpi=(dpi, dpi))
    return p


def jpg_circle(dirpath, name="circle.jpg", dpi=DPI):
    """JPG fundo branco: circulo preto r=50px em 160x160 (forma circular)."""
    im = Image.new("RGB", (160, 160), (255, 255, 255))
    ImageDraw.Draw(im).ellipse([30, 30, 130, 130], fill=(0, 0, 0))
    p = str(Path(dirpath) / name)
    im.save(p, dpi=(dpi, dpi))
    return p


def png_irregular(dirpath, name="irregular.png", dpi=DPI):
    """PNG transparente: triangulo (forma irregular) opaco."""
    im = _rgba(200, 160)
    ImageDraw.Draw(im).polygon([(100, 20), (180, 140), (20, 140)], fill=(0, 120, 200, 255))
    p = str(Path(dirpath) / name)
    im.save(p, dpi=(dpi, dpi))
    return p


def webp_opaque(dirpath, name="opaque.webp", dpi=DPI):
    """WEBP opaco simples (cinza), para validar a normalizacao WEBP->PNG."""
    im = Image.new("RGB", (120, 80), (128, 128, 128))
    p = str(Path(dirpath) / name)
    im.save(p)
    return p
