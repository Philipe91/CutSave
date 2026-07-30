"""Gera as pecas do hero: recorta cada adesivo e extrai o CONTORNO REAL do
alfa (o mesmo tipo de linha que o PrintNest desenha), virando um path SVG.

Saida:
  site/app/public/assets/app/pecas/pNN.webp   (arte recortada, com alfa)
  site/app/src/components/pn/pecas.ts         (paths + proporcao de cada peca)
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SRC = Path(r"C:\Users\Pc Fechamento\Downloads")
DEST_IMG = Path(r"c:\projetos\Cutph\site\app\public\assets\app\pecas")
DEST_TS = Path(r"c:\projetos\Cutph\site\app\src\components\pn\pecas.ts")
DEST_IMG.mkdir(parents=True, exist_ok=True)

ARQUIVOS = [
    "download (13).png",
    "download (12).png",
    "download (11).png",
    "download (10).png",
    "download (8).png",
    "download (7).png",
    "download (6).png",
    "download (5).png",
    "download (4).png",
    "download (3).png",
    "download (2).png",
    "download (1).png",
]

LARGURA = 260  # px da arte exportada


def mascara(im: Image.Image) -> np.ndarray:
    """Mascara da arte: usa o alfa quando existe, senao descarta o fundo
    branco (e o que o PrintNest faz com JPG/PNG de fundo branco)."""
    a = np.array(im.getchannel("A"))
    if a.min() < 250:  # tem transparencia de verdade
        return (a > 24).astype(np.uint8) * 255
    rgb = np.array(im.convert("RGB")).astype(np.int16)
    dist = 255 - rgb.min(axis=2)  # 0 = branco puro
    return (dist > 18).astype(np.uint8) * 255


def contorno(mask0: np.ndarray) -> list[tuple[float, float]]:
    """Maior contorno externo da mascara, simplificado."""
    mask = mask0
    # fecha buracos pequenos para a linha nao ficar serrilhada
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    conts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not conts:
        return []
    c = max(conts, key=cv2.contourArea)
    eps = 0.0035 * cv2.arcLength(c, True)
    c = cv2.approxPolyDP(c, eps, True)
    return [(float(p[0][0]), float(p[0][1])) for p in c]


def para_path(pts, w: int, h: int, escala: float) -> str:
    """Path SVG normalizado em 0..100 x 0..(100*h/w), com um leve offset
    para fora (a sangria da faca)."""
    if not pts:
        return ""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    saida = []
    for x, y in pts:
        # empurra o ponto para fora do centro = offset da faca
        dx, dy = x - cx, y - cy
        n = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        x2 = x + dx / n * escala
        y2 = y + dy / n * escala
        saida.append((round(x2 / w * 100, 2), round(y2 / w * 100, 2)))
    d = f"M{saida[0][0]} {saida[0][1]}"
    for x, y in saida[1:]:
        d += f"L{x} {y}"
    return d + "Z"


pecas = []
for i, nome in enumerate(ARQUIVOS, start=1):
    caminho = SRC / nome
    if not caminho.exists():
        print("faltando:", nome)
        continue
    im = Image.open(caminho).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    if bbox:
        im = im.crop(bbox)
    if im.width > LARGURA:
        im = im.resize((LARGURA, round(im.height * LARGURA / im.width)), Image.LANCZOS)

    m = mascara(im)
    # aplica a mascara: o adesivo passa a flutuar, sem o retangulo branco
    suave = cv2.GaussianBlur(m, (3, 3), 0)
    im.putalpha(Image.fromarray(suave))
    pts = contorno(m)
    d = para_path(pts, im.width, im.height, escala=im.width * 0.018)

    saida = DEST_IMG / f"p{i:02d}.webp"
    im.save(saida, "WEBP", quality=88, method=6)
    pecas.append(
        {
            "src": f"/assets/app/pecas/p{i:02d}.webp",
            "ratio": round(im.height / im.width, 4),
            "d": d,
            "nos": len(pts),
        }
    )
    print(f"p{i:02d}  {im.size}  nos={len(pts)}  {saida.stat().st_size // 1024} KB")

cabecalho = (
    "/* GERADO por scripts/gerar-pecas-hero.py. Nao editar a mao.\n"
    "   Cada peca traz a arte recortada e o CONTORNO REAL extraido do alfa,\n"
    "   normalizado em uma viewBox de largura 100 (a altura sai de ratio).\n"
    "   E a mesma linha que o PrintNest desenha em volta da peca. */\n\n"
    "export type PecaHero = { src: string; ratio: number; d: string }\n\n"
    "export const PECAS_HERO: PecaHero[] = "
)
corpo = json.dumps(
    [{"src": p["src"], "ratio": p["ratio"], "d": p["d"]} for p in pecas],
    indent=2,
    ensure_ascii=False,
)
DEST_TS.write_text(cabecalho + corpo + "\n", encoding="utf-8")
print("\nescrito:", DEST_TS, f"({len(pecas)} pecas)")
