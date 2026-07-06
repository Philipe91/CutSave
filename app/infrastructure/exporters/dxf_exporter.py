from __future__ import annotations

from collections.abc import Sequence

import ezdxf
from ezdxf.path import Path as EzPath
from ezdxf.path import render_splines_and_polylines

from app.application.ports.dxf_exporter import IDxfExporter
from app.domain.cut.curves import cubic_segments, has_curves
from app.domain.cut.registration import RegistrationMark
from app.domain.cut.shared import Segment
from app.domain.model.cut_contour import CutContour
from app.shared.errors import DxfExportError

CUT_LAYER = "CUT"
CUT_COLOR = 1  # vermelho (ACI), convencao comum para corte
REGMARK_LAYER = "REGMARK"
REGMARK_COLOR = 7  # preto (ACI), marca de registro
DXF_VERSION = "R2010"  # amplamente suportado por mesas de corte


class DxfExporter(IDxfExporter):
    """Exporta facas para DXF: unidades mm, layer CUT; marcas no layer REGMARK."""

    def export(
        self,
        contours: Sequence[CutContour],
        output_path: str,
        *,
        segments: Sequence[Segment] = (),
        marks: Sequence[RegistrationMark] = (),
        mark_segments: Sequence[Segment] = (),
    ) -> None:
        doc = ezdxf.new(dxfversion=DXF_VERSION)
        doc.units = ezdxf.units.MM  # define $INSUNITS = 4 (milimetros)
        doc.header["$MEASUREMENT"] = 1  # sistema metrico
        doc.layers.add(CUT_LAYER, color=CUT_COLOR)

        msp = doc.modelspace()
        for contour in contours:
            # contorno CURVO sai como SPLINE (curva de verdade, poucos nos —
            # corte liso na maquina); retas/retangulos seguem como polyline.
            segs = cubic_segments(contour.points)
            if segs and has_curves(segs):
                ez = EzPath((segs[0].p0.x, segs[0].p0.y))
                for s in segs:
                    ez.curve4_to(
                        (s.p1.x, s.p1.y), (s.c1.x, s.c1.y), (s.c2.x, s.c2.y)
                    )
                render_splines_and_polylines(
                    msp, [ez], dxfattribs={"layer": CUT_LAYER}
                )
                continue
            points = [(p.x, p.y) for p in contour.points]
            msp.add_lwpolyline(points, close=True, dxfattribs={"layer": CUT_LAYER})

        for segment in segments:
            msp.add_line(
                (segment.start.x, segment.start.y),
                (segment.end.x, segment.end.y),
                dxfattribs={"layer": CUT_LAYER},
            )

        if marks or mark_segments:
            doc.layers.add(REGMARK_LAYER, color=REGMARK_COLOR)
            for mark in marks:
                msp.add_circle(
                    (mark.center.x, mark.center.y),
                    mark.radius,
                    dxfattribs={"layer": REGMARK_LAYER},
                )
            for segment in mark_segments:
                msp.add_line(
                    (segment.start.x, segment.start.y),
                    (segment.end.x, segment.end.y),
                    dxfattribs={"layer": REGMARK_LAYER},
                )

        try:
            doc.saveas(output_path)
        except OSError as exc:
            raise DxfExportError(f"Falha ao gravar DXF: {output_path}") from exc
