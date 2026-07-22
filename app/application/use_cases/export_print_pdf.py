from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from app.application.dto.print_placement import (
    PrintCircle,
    PrintLine,
    PrintPlacement,
    PrintRect,
    PrintSheet,
)
from app.application.footprint import artwork_footprint
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.application.positioning import (
    corner_l_segments,
    cross_mark_segments,
    mimaki_marks,
    mimaki_marks_for_frames,
    registration_marks,
    square_marks,
)
from app.domain.geometry import BoundingBox, Point2D, Size
from app.domain.model.artwork import Artwork
from app.domain.model.layout import Layout
from app.shared.errors import ValidationError


class ExportPrintPdfUseCase:
    """Gera um PDF de impressao com uma pagina por chapa do nesting.

    Tipos de registro ('reg_type'):
      - 'none'     : sem marcas.
      - 'circles'  : 5 bolinhas ao redor (padding = margem + diametro).
      - 'mimaki'   : marcas em L nos cantos de um quadro (padding = distancia).
      - 'squares'  : 4 quadrados cheios nos cantos (Summa/OPOS).
      - 'crosses'  : 4 cruzes nos cantos (AOKE/iECHO).
      - 'corner_l' : 4 Ls de canto sem quadro, abrindo para fora (Graphtec/Roland).
    A pagina ganha 'padding' para as marcas caberem; o conteudo e deslocado.
    """

    def __init__(self, exporter: IPrintPdfExporter) -> None:
        self._exporter = exporter

    def build_print_sheets(
        self,
        sheets: Sequence[Layout],
        artworks: Sequence[Artwork],
        sources: Mapping[str, tuple[str, int]],
        *,
        reg_type: str = "none",
        reg_margin_mm: float = 15.0,
        reg_diameter_mm: float = 6.0,
        reg_thickness_mm: float = 0.8,
        mimaki_distance_mm: float = 15.0,
        mimaki_size_mm: float = 15.0,
        mimaki_thickness_mm: float = 1.0,
        crop_mm: float = 0.0,
        rotate: int = 0,
        rotations: Mapping[str, int] | None = None,
        box: str = "media",
        mimaki_frames_for: Callable[[Layout], Sequence[BoundingBox]] | None = None,
    ) -> list[PrintSheet]:
        """Monta os PrintSheet (posicao, escala e marcas) usados na exportacao.

        'rotate' e o giro padrao; 'rotations' (artwork_id -> graus) sobrepoe o
        giro de pecas especificas (rotacao por peca). O tamanho de cada arte ja
        vem girado, entao o exportador so rotaciona o conteudo da origem.
        """
        layouts = [layout for layout in sheets if layout.items]
        if not layouts:
            raise ValidationError("Nenhuma chapa com pecas para imprimir.")
        by_id = {art.id: art for art in artworks}

        pad = 0.0
        if reg_type in ("circles", "both"):
            pad = max(pad, reg_margin_mm + reg_diameter_mm)
        if reg_type in ("mimaki", "both"):
            pad = max(pad, mimaki_distance_mm + mimaki_thickness_mm)
        if reg_type in ("squares", "crosses"):
            pad = max(pad, reg_margin_mm + reg_diameter_mm)
        if reg_type == "corner_l":
            # os bracos do L crescem PARA FORA do quadro afastado
            pad = max(pad, reg_margin_mm + reg_diameter_mm + reg_thickness_mm)

        print_sheets: list[PrintSheet] = []
        for layout in layouts:
            placements = []
            for item in layout.items:
                art = by_id.get(item.artwork_id)
                if art is None:
                    raise ValidationError(f"Arte ausente para id {item.artwork_id}.")
                source = sources.get(item.artwork_id)
                if source is None:
                    raise ValidationError(f"Origem ausente para id {item.artwork_id}.")
                footprint = artwork_footprint(art)
                position = Point2D(
                    item.position.x - footprint.min_x + pad,
                    item.position.y - footprint.min_y + pad,
                )
                rot = rotations.get(item.artwork_id, rotate) if rotations else rotate
                placements.append(
                    PrintPlacement(source[0], source[1], position, art.size, crop_mm, rot, box)
                )

            circles, lines, rects = self._marks(
                layout, artworks, reg_type, pad,
                reg_margin_mm, reg_diameter_mm, reg_thickness_mm,
                mimaki_distance_mm, mimaki_size_mm, mimaki_thickness_mm,
                mimaki_frames_for=mimaki_frames_for,
            )
            sheet_size = Size(layout.material.width + 2 * pad, layout.used_length + 2 * pad)
            print_sheets.append(
                PrintSheet(tuple(placements), sheet_size, circles, lines, rects)
            )
        return print_sheets

    def execute(
        self,
        sheets: Sequence[Layout],
        artworks: Sequence[Artwork],
        sources: Mapping[str, tuple[str, int]],
        output_path: str,
        **kwargs,
    ) -> str:
        print_sheets = self.build_print_sheets(sheets, artworks, sources, **kwargs)
        self._exporter.export(print_sheets, output_path)
        return output_path

    def execute_image(
        self,
        sheets: Sequence[Layout],
        artworks: Sequence[Artwork],
        sources: Mapping[str, tuple[str, int]],
        output_path: str,
        *,
        dpi: int = 150,
        image_format: str = "png",
        **kwargs,
    ) -> list[str]:
        """Exporta a impressao como imagem (PNG/JPEG) no DPI pedido."""
        print_sheets = self.build_print_sheets(sheets, artworks, sources, **kwargs)
        return self._exporter.export_image(
            print_sheets, output_path, dpi=dpi, image_format=image_format
        )

    @staticmethod
    def _marks(
        layout, artworks, reg_type, pad,
        reg_margin_mm, reg_diameter_mm, reg_thickness_mm,
        mimaki_distance_mm, mimaki_size_mm, mimaki_thickness_mm,
        mimaki_frames_for=None,
    ):
        circles: tuple[PrintCircle, ...] = ()
        lines: tuple[PrintLine, ...] = ()
        rects: tuple[PrintRect, ...] = ()
        if reg_type in ("circles", "both"):
            marks = registration_marks(
                layout, artworks, margin_mm=reg_margin_mm, diameter_mm=reg_diameter_mm
            )
            circles = tuple(
                PrintCircle(m.center.translated(pad, pad), m.diameter) for m in marks
            )
        if reg_type in ("mimaki", "both"):
            # cartelas identicas: um conjunto de marcas em L POR cartela (a
            # Mimaki le cada cartela depois do refile); sem frames, o quadro
            # unico ao redor da chapa segue como sempre foi.
            frames = mimaki_frames_for(layout) if mimaki_frames_for else None
            if frames:
                segments = [
                    s
                    for mk in mimaki_marks_for_frames(
                        frames,
                        distance_mm=mimaki_distance_mm, mark_size_mm=mimaki_size_mm,
                    )
                    for s in mk.segments
                ]
            else:
                marks = mimaki_marks(
                    layout, artworks,
                    distance_mm=mimaki_distance_mm, mark_size_mm=mimaki_size_mm,
                )
                segments = list(marks.segments) if marks is not None else []
            lines = tuple(
                PrintLine(
                    s.start.translated(pad, pad),
                    s.end.translated(pad, pad),
                    mimaki_thickness_mm,
                )
                for s in segments
            )
        if reg_type == "squares":
            rects = tuple(
                PrintRect(m.center.translated(pad, pad), m.size)
                for m in square_marks(
                    layout, artworks, margin_mm=reg_margin_mm, size_mm=reg_diameter_mm
                )
            )
        if reg_type in ("crosses", "corner_l"):
            fn = cross_mark_segments if reg_type == "crosses" else corner_l_segments
            lines = lines + tuple(
                PrintLine(
                    s.start.translated(pad, pad),
                    s.end.translated(pad, pad),
                    reg_thickness_mm,
                )
                for s in fn(
                    layout, artworks, margin_mm=reg_margin_mm, size_mm=reg_diameter_mm
                )
            )
        return circles, lines, rects
