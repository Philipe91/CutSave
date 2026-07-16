"""Cartelas: divisao da chapa em mini-chapas para o fluxo Mimaki + IECHO.

Fluxo da grafica: a chapa impressa carrega VARIAS cartelas (ex.: pouco
maiores que A4), cada uma com suas pecas. A Mimaki corta as pecas (lendo as
marcas em L); a IECHO separa as cartelas com cortes RETOS fora a fora
(lendo as bolinhas de registro). Este modulo so faz a geometria: a grade de
cartelas na chapa e as linhas de separacao para a IECHO.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.cut.shared import Segment
from app.domain.geometry import Point2D

# tolerancia para deduplicar linhas coincidentes (gutter zero)
_EPS = 1e-6


@dataclass(frozen=True, slots=True)
class CartelaGrid:
    """Grade de cartelas centrada na chapa. Medidas em mm."""

    cols: int
    rows: int          # 0 = chapa aberta (cresce conforme a demanda)
    cell_w: float
    cell_h: float
    gutter: float      # espaco entre cartelas (0 = coladas, corte unico)
    origin_x: float    # canto superior-esquerdo da 1a cartela
    origin_y: float

    @property
    def per_sheet(self) -> int:
        """Cartelas por chapa (0 = ilimitado, chapa aberta)."""
        return self.cols * self.rows

    def slot_origin(self, index: int) -> tuple[float, float]:
        """Canto superior-esquerdo da cartela 'index' na chapa (ordem de
        leitura: esquerda -> direita, cima -> baixo)."""
        col = index % self.cols
        row = index // self.cols
        return (
            self.origin_x + col * (self.cell_w + self.gutter),
            self.origin_y + row * (self.cell_h + self.gutter),
        )

    def block_height(self, n_cartelas: int) -> float:
        """Altura ocupada por n cartelas (para chapa aberta)."""
        rows = max(1, math.ceil(n_cartelas / self.cols))
        return rows * self.cell_h + (rows - 1) * self.gutter


def build_cartela_grid(
    sheet_width: float,
    sheet_length: float,
    cell_w: float,
    cell_h: float,
    gutter: float = 0.0,
) -> CartelaGrid | None:
    """Monta a grade de cartelas centrada na chapa; None se nem UMA cabe.

    sheet_length <= 0 (chapa aberta): a grade tem colunas fixas e cresce em
    linhas conforme a demanda (rows=0)."""
    if cell_w <= 0 or cell_h <= 0 or gutter < 0:
        return None
    if cell_w > sheet_width + _EPS:
        return None
    cols = int((sheet_width + gutter + _EPS) // (cell_w + gutter))
    block_w = cols * cell_w + (cols - 1) * gutter
    origin_x = (sheet_width - block_w) / 2
    if sheet_length <= 0:
        return CartelaGrid(cols, 0, cell_w, cell_h, gutter, origin_x, 0.0)
    if cell_h > sheet_length + _EPS:
        return None
    rows = int((sheet_length + gutter + _EPS) // (cell_h + gutter))
    block_h = rows * cell_h + (rows - 1) * gutter
    origin_y = (sheet_length - block_h) / 2
    return CartelaGrid(cols, rows, cell_w, cell_h, gutter, origin_x, origin_y)


def cartela_separation_segments(
    grid: CartelaGrid,
    sheet_width: float,
    sheet_length: float,
    rows_used: int | None = None,
) -> list[Segment]:
    """Linhas de separacao das cartelas para a IECHO: cortes RETOS fora a
    fora (atravessam a chapa inteira), em toda borda de cartela — inclusive
    as bordas externas do bloco (refile). Com gutter 0, bordas coincidentes
    viram UMA linha (a maquina corta uma vez so)."""
    rows = grid.rows if grid.rows > 0 else (rows_used or 1)
    xs: list[float] = []
    for c in range(grid.cols):
        left = grid.origin_x + c * (grid.cell_w + grid.gutter)
        xs.append(left)
        xs.append(left + grid.cell_w)
    ys: list[float] = []
    origin_y = grid.origin_y
    for r in range(rows):
        top = origin_y + r * (grid.cell_h + grid.gutter)
        ys.append(top)
        ys.append(top + grid.cell_h)

    def dedupe(values: list[float]) -> list[float]:
        out: list[float] = []
        for v in sorted(values):
            if not out or v - out[-1] > _EPS:
                out.append(v)
        return out

    height = sheet_length if sheet_length > 0 else (
        origin_y + rows * grid.cell_h + (rows - 1) * grid.gutter
    )
    segments = [
        Segment(Point2D(x, 0.0), Point2D(x, height)) for x in dedupe(xs)
    ]
    segments.extend(
        Segment(Point2D(0.0, y), Point2D(sheet_width, y)) for y in dedupe(ys)
    )
    return segments
