"""Benchmark de desempenho do PrintNest (standalone, fora da UI).

Mede os tempos das etapas pesadas em dados sinteticos:
  1. Importacao + faca retangular de PDF (por pagina)
  2. Deteccao de contorno de imagem (faca de imagem / PDF por contorno)
  3. Nesting em grade escalando a quantidade de copias

Uso:
    python scripts/benchmark.py
    python scripts/benchmark.py --pages 20 --images 20 --copies 5000

Compare os numeros com as metas em docs/produto/PLANO-COMERCIALIZACAO.md (secao Desempenho).
Nao altera nada do app: so cria arquivos temporarios e mede.
"""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

import fitz
import numpy as np
from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
from app.application.use_cases.import_pdf import ImportPdfUseCase
from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
from app.domain.model.material import Material
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter
from app.infrastructure.importers.pymupdf_importer import PyMuPdfImporter
from PIL import Image


def _timer():
    start = time.perf_counter()
    return lambda: (time.perf_counter() - start) * 1000.0  # ms


def _make_pdf(path: Path, pages: int) -> None:
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=283.46, height=283.46)  # ~100mm
        page.draw_circle(fitz.Point(141, 141), 120, color=(0, 0.5, 0), fill=(0, 0.5, 0))
    doc.save(str(path))
    doc.close()


def _make_png(path: Path, size: int = 600) -> None:
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    yy, xx = np.ogrid[:size, :size]
    r = size // 2 - 20
    disc = (xx - size / 2) ** 2 + (yy - size / 2) ** 2 <= r * r
    rgba[disc] = (40, 160, 80, 255)
    Image.fromarray(rgba, "RGBA").save(path)


def bench_pdf(tmp: Path, pages: int) -> None:
    pdf = tmp / "bench.pdf"
    _make_pdf(pdf, pages)
    importer = ImportPdfUseCase(PyMuPdfImporter())
    faca = GenerateRectangularCutUseCase()
    t = _timer()
    arts = importer.execute(str(pdf), "media")
    for art in arts:
        faca.execute(art, 3.0)
    total = t()
    print(f"[PDF]   {pages} paginas: {total:7.1f} ms  ({total / pages:6.2f} ms/pagina)")


def bench_image_contour(tmp: Path, images: int) -> None:
    importer = Cv2ImageImporter(cache_dir=tmp / "cache")
    paths = []
    for i in range(images):
        p = tmp / f"img_{i}.png"
        _make_png(p)
        paths.append(p)
    t = _timer()
    for p in paths:
        importer.import_image(str(p), sensitivity=50.0, ignore_white=True)
    total = t()
    print(f"[IMG]   {images} imagens: {total:7.1f} ms  ({total / images:6.2f} ms/imagem)")


def bench_nesting(tmp: Path, copies: int) -> None:
    importer = ImportPdfUseCase(PyMuPdfImporter())
    faca = GenerateRectangularCutUseCase()
    pdf = tmp / "one.pdf"
    _make_pdf(pdf, 1)
    art = faca.execute(importer.execute(str(pdf), "media")[0], 3.0)
    artworks = [art] * copies
    material = Material(name="bench", width=1300.0, spacing=5.0)
    nesting = RunGridNestingUseCase()
    t = _timer()
    sheets = nesting.execute_sheets(artworks, material, 0.0)
    total = t()
    placed = sum(s.item_count for s in sheets)
    print(f"[NEST]  {copies} copias -> {placed} pecas / {len(sheets)} chapa(s): {total:7.1f} ms")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=20)
    ap.add_argument("--images", type=int, default=20)
    ap.add_argument("--copies", type=int, default=5000)
    args = ap.parse_args()

    print("=== Benchmark PrintNest ===")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        bench_pdf(tmp, args.pages)
        bench_image_contour(tmp, args.images)
        bench_nesting(tmp, args.copies)
    print("Compare com as metas em docs/produto/PLANO-COMERCIALIZACAO.md (Desempenho).")


if __name__ == "__main__":
    main()
