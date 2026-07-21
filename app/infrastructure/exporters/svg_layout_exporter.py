"""Layout organizado -> SVG (curvas do corte), para voltar ao CorelDRAW.

O "Enviar para o Corel" do Modo Corte gera este SVG e a ponte COM importa
na pagina ativa — o operador manipula o arranjo como curvas normais.

Convencoes:
- mm reais: width/height fisicos + viewBox 1:1 (1 unidade = 1mm), entao o
  Corel importa no tamanho exato.
- Cada peca vira UM <path> com subpaths (outer + furos) e fill-rule evenodd
  — mover a peca no Corel carrega os furos junto.
- Traco MAGENTA hairline sem preenchimento: a convencao de faca do cliente
  (o proprio PrintNest reimporta este SVG como linha de corte).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.model.cut_contour import CutContour
from app.shared.errors import DxfExportError

_STROKE = "#ff00ff"       # magenta = faca (convencao do cliente)
_STROKE_W = 0.2           # hairline em mm


def _path_d(rings: Sequence[CutContour]) -> str:
    parts: list[str] = []
    for ring in rings:
        points = ring.points
        parts.append(
            "M " + " L ".join(f"{p.x:.3f},{p.y:.3f}" for p in points) + " Z"
        )
    return " ".join(parts)


def write_layout_svg(
    pieces: Sequence[Sequence[CutContour]],
    width_mm: float,
    height_mm: float,
    output_path: str,
) -> str:
    """Grava o SVG do layout (uma lista de aneis por peca: outer + furos).
    Devolve output_path. Lanca DxfExportError se nao conseguir gravar."""
    paths = "\n".join(
        f'  <path d="{_path_d(rings)}" fill="none" stroke="{_STROKE}" '
        f'stroke-width="{_STROKE_W}" fill-rule="evenodd"/>'
        for rings in pieces
        if rings
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width_mm:.2f}mm" height="{height_mm:.2f}mm" '
        f'viewBox="0 0 {width_mm:.2f} {height_mm:.2f}">\n'
        f"{paths}\n</svg>\n"
    )
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(svg)
    except OSError as exc:
        raise DxfExportError(f"Falha ao gravar SVG: {output_path}") from exc
    return output_path
