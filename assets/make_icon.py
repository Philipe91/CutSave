"""Gera um icone temporario (assets/printnest.ico). Roda uma vez."""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (52, 73, 94, 255))  # cinza-azulado
draw = ImageDraw.Draw(img)
# moldura (material) e "faca" vermelha interna
draw.rectangle([26, 26, 230, 230], outline=(255, 255, 255, 255), width=10)
draw.rectangle([70, 70, 186, 186], outline=(220, 0, 0, 255), width=12)

out = Path(__file__).with_name("printnest.ico")
img.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icone gerado:", out)
