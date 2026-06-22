from __future__ import annotations

from collections.abc import Sequence

import ezdxf

from app.application.ports.dxf_exporter import IDxfExporter
from app.domain.model.cut_contour import CutContour
from app.shared.errors import DxfExportError

CUT_LAYER = "CUT"
CUT_COLOR = 1  # vermelho (ACI), convencao comum para corte
DXF_VERSION = "R2010"  # amplamente suportado por mesas de corte


class DxfExporter(IDxfExporter):
    """Exporta facas para DXF: unidades mm, polilinha fechada, layer CUT."""

    def export(self, contours: Sequence[CutContour], output_path: str) -> None:
        doc = ezdxf.new(dxfversion=DXF_VERSION)
        doc.units = ezdxf.units.MM  # define $INSUNITS = 4 (milimetros)
        doc.header["$MEASUREMENT"] = 1  # sistema metrico
        doc.layers.add(CUT_LAYER, color=CUT_COLOR)

        msp = doc.modelspace()
        for contour in contours:
            points = [(p.x, p.y) for p in contour.points]
            msp.add_lwpolyline(points, close=True, dxfattribs={"layer": CUT_LAYER})

        try:
            doc.saveas(output_path)
        except OSError as exc:
            raise DxfExportError(f"Falha ao gravar DXF: {output_path}") from exc
