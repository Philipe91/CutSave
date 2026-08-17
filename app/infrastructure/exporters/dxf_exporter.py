from __future__ import annotations

from collections.abc import Sequence

import ezdxf
from ezdxf.math import Bezier4P, Vec3, bezier_to_bspline

from app.application.ports.dxf_exporter import IDxfExporter
from app.domain.cut.curves import cubic_segments, has_curves
from app.domain.geometry.bezier import BezierSegment, bezier_bounds
from app.domain.cut.registration import RegistrationMark
from app.domain.cut.shared import Segment
from app.domain.geometry import Point2D
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
        mark_polylines: Sequence[Sequence[Point2D]] = (),
    ) -> None:
        # ESPELHAMENTO (beta 09/07): o modelo do PrintNest usa Y-para-BAIXO
        # (convencao de tela/PDF); CAD/CorelDRAW leem DXF com Y-para-CIMA.
        # Sem conversao, o corte abria espelhado na vertical. Aqui TODA a
        # geometria (facas, grade, marcas) e refletida junto — y' = H - y —
        # entao o alinhamento impressao x corte permanece exato e as
        # coordenadas continuam positivas.
        flip_h = self._extent_y(contours, segments, marks, mark_segments, mark_polylines)

        def fy(y: float) -> float:
            return flip_h - y

        doc = ezdxf.new(dxfversion=DXF_VERSION)
        doc.units = ezdxf.units.MM  # define $INSUNITS = 4 (milimetros)
        doc.header["$MEASUREMENT"] = 1  # sistema metrico
        doc.layers.add(CUT_LAYER, color=CUT_COLOR)

        msp = doc.modelspace()
        for contour in contours:
            flipped = [Point2D(p.x, fy(p.y)) for p in contour.points]
            # contorno CURVO sai como UM SPLINE FECHADO por contorno (F3:
            # render_splines_and_polylines quebrava o caminho a cada canto —
            # a letra abria em pedacos no Corel). Bezier -> B-spline e EXATO
            # (mesma curva, nos internos com multiplicidade 3 preservam os
            # cantos vivos); retas/retangulos seguem como polyline.
            #
            # ORIGEM DA CURVA: se o contorno trouxe a Bezier do ARQUIVO
            # (importador vetorial), usa ela — e a curva de verdade, com a
            # contagem de nos do desenho. Sem ela (faca detectada na imagem,
            # ou contorno simplificado), cai no refit de cubic_segments, que
            # adivinha uma curva por cima dos pontos.
            segs = (
                [_flip_segment(s, fy) for s in contour.curves]
                if contour.curves
                else cubic_segments(flipped)
            )
            if segs and has_curves(segs):
                beziers = [
                    Bezier4P((
                        Vec3(s.p0.x, s.p0.y, 0.0),
                        Vec3(s.c1.x, s.c1.y, 0.0),
                        Vec3(s.c2.x, s.c2.y, 0.0),
                        Vec3(s.p1.x, s.p1.y, 0.0),
                    ))
                    for s in segs
                ]
                spline = msp.add_spline(dxfattribs={"layer": CUT_LAYER})
                spline.apply_construction_tool(bezier_to_bspline(beziers))
                spline.closed = True
                continue
            points = [(p.x, p.y) for p in flipped]
            msp.add_lwpolyline(points, close=True, dxfattribs={"layer": CUT_LAYER})

        for segment in segments:
            msp.add_line(
                (segment.start.x, fy(segment.start.y)),
                (segment.end.x, fy(segment.end.y)),
                dxfattribs={"layer": CUT_LAYER},
            )

        if marks or mark_segments or mark_polylines:
            doc.layers.add(REGMARK_LAYER, color=REGMARK_COLOR)
            for mark in marks:
                msp.add_circle(
                    (mark.center.x, fy(mark.center.y)),
                    mark.radius,
                    dxfattribs={"layer": REGMARK_LAYER},
                )
            for segment in mark_segments:
                msp.add_line(
                    (segment.start.x, fy(segment.start.y)),
                    (segment.end.x, fy(segment.end.y)),
                    dxfattribs={"layer": REGMARK_LAYER},
                )
            for poly in mark_polylines:  # quadrado de registro: polilinha fechada
                msp.add_lwpolyline(
                    [(p.x, fy(p.y)) for p in poly],
                    close=True,
                    dxfattribs={"layer": REGMARK_LAYER},
                )

        try:
            doc.saveas(output_path)
        except OSError as exc:
            raise DxfExportError(f"Falha ao gravar DXF: {output_path}") from exc

    @staticmethod
    def _extent_y(contours, segments, marks, mark_segments, mark_polylines=()) -> float:
        """Maior Y da geometria — referencia da reflexao (y' = H - y)."""
        ys: list[float] = []
        for c in contours:
            ys += [p.y for p in c.points]
            # a curva original pode estufar para fora das cordas; sem contar os
            # extremos EXATOS dela a referencia do espelhamento sairia baixa e o
            # DXF ganharia Y negativo
            if c.curves:
                ys.append(bezier_bounds(c.curves).max_y)
        for s in (*segments, *mark_segments):
            ys += [s.start.y, s.end.y]
        for m in marks:
            ys.append(m.center.y + m.radius)
        for poly in mark_polylines:
            ys += [p.y for p in poly]
        return max(ys) if ys else 0.0


def _flip_segment(s: BezierSegment, fy) -> BezierSegment:
    """Espelha o trecho no mesmo eixo do resto da geometria (y' = H - y).

    Espelhar inverte o sentido de percurso do anel, o que nao altera a forma
    gravada — o DXF descreve a mesma curva.
    """
    return BezierSegment(
        Point2D(s.p0.x, fy(s.p0.y)),
        Point2D(s.c1.x, fy(s.c1.y)),
        Point2D(s.c2.x, fy(s.c2.y)),
        Point2D(s.p1.x, fy(s.p1.y)),
    )
