"""Use case da Fase 4: nesting true-shape -> DXF para a maquina de corte.

Liga a Fase 3 (importadores -> PolygonWithHoles) ao TrueShapePacker (Fase 2)
e ao ExportDxfUseCase, reconstruindo cada peca posicionada com o contorno
REAL do chamador.

RECONSTRUCAO (convencao 2E, docstring do TrueShapePacker): position = canto
minimo do bounding box do contorno JA GIRADO. Aqui: girar o contorno
ORIGINAL por PlacedItem.rotation (graus; o centro nao importa porque a
normalizacao vem depois), normalizar (bbox.min do outer girado na origem) e
transladar para position. FUROS recebem EXATAMENTE o mesmo transform do
outer — mesmo centro de giro e mesmo delta; normalizar o furo pelo proprio
bbox descolaria o furo da letra.

DETALHE ORIGINAL: o 'approximation' do packer simplifica o contorno SO para
acelerar o NFP. O DXF corta o contorno REAL: a reconstrucao parte das
NestingShapes que o CHAMADOR passou (por artwork_id), nunca do que o packer
usou internamente.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.domain.geometry import Point2D
from app.domain.geometry.polygon_with_holes import PolygonWithHoles
from app.domain.model.cut_contour import CutContour
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.domain.nesting.true_shape import NestingShape, TrueShapePacker
from app.shared.errors import ValidationError

_ORIGIN = Point2D(0.0, 0.0)


def to_nesting_shapes(
    shapes: Sequence[PolygonWithHoles],
    *,
    rotations: tuple[float, ...] = (0.0, 90.0, 180.0, 270.0),
    start: int = 1,
) -> list[NestingShape]:
    """PolygonWithHoles -> NestingShape com ids sequenciais estaveis
    ("shape-0001", ...). Quem tem GlyphShapes achata os .shapes antes de
    chamar — cada corpo vira uma peca independente no nesting.

    'start' existe porque a numeracao reinicia a cada chamada: quem JUNTA o
    resultado de varias chamadas (a UI da Fase 5 importa varios arquivos)
    precisa continuar a contagem, senao dois lotes colidem no mesmo id e o
    dicionario da reconstrucao devolve o contorno errado."""
    return [
        NestingShape(f"shape-{i:04d}", shape.outer, tuple(rotations), shape.holes)
        for i, shape in enumerate(shapes, start=start)
    ]


def placed_cut_contours(shape: NestingShape, item: PlacedItem) -> list[CutContour]:
    """Peca REAL reconstruida na posicao do layout: outer + um CutContour por
    furo, todos com o MESMO transform (ver convencao no topo do modulo)."""
    degrees = float(item.rotation)
    outer = shape.contour.rotated(degrees, around=_ORIGIN)
    bb = outer.bounding_box
    dx = item.position.x - bb.min_x
    dy = item.position.y - bb.min_y
    contours = [CutContour(outer.translated(dx, dy).vertices)]
    contours.extend(
        CutContour(hole.rotated(degrees, around=_ORIGIN).translated(dx, dy).vertices)
        for hole in shape.holes
    )
    return contours


@dataclass(frozen=True, slots=True)
class NestingExportResult:
    """Saida da Fase 4. Peca que NAO coube aparece em unplaced_ids — nunca
    some em silencio."""

    dxf_paths: tuple[str, ...]
    layouts: tuple[Layout, ...]
    unplaced_ids: tuple[str, ...]


class RunTrueShapeNestingUseCase:
    """Nesting true-shape + exportacao DXF, com o packer e o exportador
    injetados (padrao dos demais use cases)."""

    def __init__(self, packer: TrueShapePacker, exporter: ExportDxfUseCase) -> None:
        self._packer = packer
        self._exporter = exporter

    # -- calculo (sem gravar nada) ----------------------------------------------

    def pack(self, shapes: Sequence[NestingShape], material: Material) -> Layout:
        """So o nesting da chapa aberta. Existe separado de execute() para o
        PREVIEW: com genetics_time o resultado NAO e deterministico, entao
        desenhar e exportar precisam partir do MESMO Layout — senao o DXF sai
        diferente do que o usuario viu na tela."""
        return self._packer.pack(self._checked(shapes), material)

    def pack_sheets(
        self, shapes: Sequence[NestingShape], material: Material, sheet_length: float
    ) -> list[Layout]:
        """So o nesting em folhas (ver pack)."""
        return list(self._packer.pack_sheets(self._checked(shapes), material, sheet_length))

    # -- gravacao ---------------------------------------------------------------

    def export_layouts(
        self,
        shapes: Sequence[NestingShape],
        layouts: Sequence[Layout],
        output_path: str,
        *,
        per_sheet: bool = False,
    ) -> NestingExportResult:
        """Grava layouts JA calculados. per_sheet=True gera um DXF por folha
        com sufixo _folha1, _folha2... — a numeracao segue os ARQUIVOS
        gravados, entao folha vazia no meio nao abre buraco na sequencia."""
        shapes = self._checked(shapes)
        layouts = tuple(layouts)
        unplaced = _unplaced_ids(shapes, layouts)
        paths: list[str] = []
        for layout in layouts:
            contours = _layout_contours(shapes, layout)
            if not contours:
                continue
            path = _sheet_path(output_path, len(paths) + 1) if per_sheet else output_path
            paths.append(self._exporter.execute(contours, path))
        if not paths:
            raise ValidationError(
                "Nenhuma peca coube no material — nada para exportar "
                f"(fora do nesting: {', '.join(unplaced)})."
            )
        return NestingExportResult(tuple(paths), layouts, unplaced)

    # -- pack + gravacao (atalho) -----------------------------------------------

    def execute(
        self,
        shapes: Sequence[NestingShape],
        material: Material,
        output_path: str,
    ) -> NestingExportResult:
        """Chapa aberta/bobina (pack): UM DXF em output_path."""
        shapes = self._checked(shapes)
        return self.export_layouts(shapes, (self.pack(shapes, material),), output_path)

    def execute_sheets(
        self,
        shapes: Sequence[NestingShape],
        material: Material,
        output_path: str,
        *,
        sheet_length: float,
    ) -> NestingExportResult:
        """Folhas de altura fixa (pack_sheets): um DXF por folha, com sufixo
        _folha1, _folha2... no nome de output_path."""
        shapes = self._checked(shapes)
        layouts = self.pack_sheets(shapes, material, sheet_length)
        return self.export_layouts(shapes, layouts, output_path, per_sheet=True)

    # -- internas ---------------------------------------------------------------

    @staticmethod
    def _checked(shapes: Sequence[NestingShape]) -> list[NestingShape]:
        shapes = list(shapes)
        if not shapes:
            raise ValidationError("Nenhuma peca para o nesting true-shape.")
        return shapes


def _layout_contours(shapes: Sequence[NestingShape], layout: Layout) -> list[CutContour]:
    """Contornos reais de todas as pecas do layout, na ordem dos items.
    Copias com o mesmo artwork_id compartilham o contorno (precondicao do
    packer), entao o dicionario por id basta."""
    by_id = {shape.artwork_id: shape for shape in shapes}
    contours: list[CutContour] = []
    for item in layout.items:
        contours.extend(placed_cut_contours(by_id[item.artwork_id], item))
    return contours


def _unplaced_ids(
    shapes: Sequence[NestingShape], layouts: Sequence[Layout]
) -> tuple[str, ...]:
    """Multiset de entrada menos multiset colocado, na ordem de entrada —
    copias com o mesmo id contam uma a uma."""
    placed = Counter(item.artwork_id for layout in layouts for item in layout.items)
    unplaced: list[str] = []
    for shape in shapes:
        if placed.get(shape.artwork_id, 0) > 0:
            placed[shape.artwork_id] -= 1
        else:
            unplaced.append(shape.artwork_id)
    return tuple(unplaced)


def _sheet_path(output_path: str, number: int) -> str:
    root, ext = os.path.splitext(output_path)
    return f"{root}_folha{number}{ext}"
