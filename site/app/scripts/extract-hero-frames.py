# -*- coding: utf-8 -*-
"""
Extrai frames de um vídeo para uma variante do hero scrollytelling.

Uso:
    python scripts/extract-hero-frames.py "<video.mp4>" <nome-da-variante> [step]

Gera:
    src/assets/hero-variants/<nome>/hd/frame-NNN.jpg   (1920 de largura)
    src/assets/hero-variants/<nome>/sd/frame-NNN.jpg   (1152 de largura)

- step: pega 1 a cada N frames do vídeo (padrão 3; menor = mais liso e mais pesado).
- Se o vídeo for menor que o alvo HD, aplica Lanczos + máscara de nitidez.
- O site detecta as variantes automaticamente (import.meta.glob) — basta rodar
  este script e rebuildar; nada de hardcode.
"""
import os
import sys

import cv2
from PIL import Image, ImageFilter

HD_W, HD_Q = 1920, 82
SD_W, SD_Q = 1152, 72


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    src = sys.argv[1]
    variant = sys.argv[2]
    step = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    base = os.path.join(os.path.dirname(__file__), "..", "src", "assets", "hero-variants", variant)
    hd_dir = os.path.abspath(os.path.join(base, "hd"))
    sd_dir = os.path.abspath(os.path.join(base, "sd"))
    os.makedirs(hd_dir, exist_ok=True)
    os.makedirs(sd_dir, exist_ok=True)
    for d in (hd_dir, sd_dir):
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))

    cap = cv2.VideoCapture(src)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    out = 0
    for i in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, bgr = cap.read()
        if not ok:
            break
        im = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))

        for width, q, dest in ((HD_W, HD_Q, hd_dir), (SD_W, SD_Q, sd_dir)):
            h = round(im.height * width / im.width)
            frame = im.resize((width, h), Image.LANCZOS)
            if src_w < width:  # upscale: recupera nitidez
                frame = frame.filter(ImageFilter.UnsharpMask(radius=1.4, percent=72, threshold=2))
            frame.save(os.path.join(dest, f"frame-{out:03d}.jpg"), quality=q, optimize=True, progressive=True)
        out += 1
    cap.release()

    def mb(d: str) -> float:
        return round(sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)) / 1e6, 1)

    print(f"variante '{variant}': {out} frames | HD {mb(hd_dir)} MB | SD {mb(sd_dir)} MB")


if __name__ == "__main__":
    main()
