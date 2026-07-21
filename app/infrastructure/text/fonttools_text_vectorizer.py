"""Vetorizacao de texto digitado -> GlyphShapes (Fase 3C).

Le a fonte com fontTools e desenha cada glifo pelo pen protocol: TTF (glyf)
e OTF (CFF) saem pelo mesmo caminho, glifos COMPOSTOS (acentos: e, c) e
qCurveTo com varios off-curves ja chegam decompostos pelo BasePen.

Convencoes e limites:
- ESCALA: size_mm e o corpo tipografico (em): mm por unidade =
  size_mm / unitsPerEm — mesmo comportamento de Corel/Illustrator; a
  MAIUSCULA fica ~70% disso (capHeight). "Altura exata da letra" e opcao
  de UI (Fase 5).
- EIXO Y: fonte tem Y para CIMA; aqui vira Y para BAIXO (flip) e o conjunto
  inteiro e transladado para o bounding box global comecar em (0, 0) — sem
  coordenadas negativas de ascendente/descendente.
- POSICAO: letras lado a lado pelo advance do hmtx (baseline unica).
  Kerning GPOS fora do escopo — o nesting rearranja tudo depois.
- FUROS: group_rings POR GLIFO (contencao even-odd), nunca global.
  Limitacao aceita: glifo com contornos que se SOBREPOEM (winding non-zero,
  raro em fontes boas) pode sair errado — fica para depois.
- Espaco e glifos vazios nao geram GlyphShapes, mas o advance anda o cursor.
"""

from __future__ import annotations

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from app.application.ports.text_vectorizer import GlyphShapes, ITextVectorizer
from app.domain.geometry.polygon import Polygon
from app.domain.geometry.polygon_with_holes import group_rings
from app.infrastructure.importers._flatten import PointAt, flatten_curve, to_ring
from app.shared.errors import TextVectorizeError


def _cubic_at(p0, p1, p2, p3) -> PointAt:
    """Avaliador t -> (x, y) da Bezier cubica (CFF), como na 3B."""

    def at(t: float) -> tuple[float, float]:
        mt = 1.0 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]
        return (x, y)

    return at


def _quad_at(p0, p1, p2) -> PointAt:
    """Avaliador t -> (x, y) da Bezier quadratica (TrueType)."""

    def at(t: float) -> tuple[float, float]:
        mt = 1.0 - t
        x = mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0]
        y = mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]
        return (x, y)

    return at


class _ContourPen(BasePen):
    """Achata cada contorno do glifo numa polilinha em unidades da fonte
    (Y ainda para cima). Um contorno por moveTo/closePath."""

    def __init__(self, glyph_set, tol_units: float) -> None:
        super().__init__(glyph_set)
        self._tol = tol_units
        self.contours: list[list[tuple[float, float]]] = []
        self._points: list[tuple[float, float]] = []

    def _moveTo(self, pt) -> None:
        self._flush()
        self._points = [pt]

    def _lineTo(self, pt) -> None:
        self._points.append(pt)

    def _curveToOne(self, p1, p2, p3) -> None:
        flatten_curve(_cubic_at(self._points[-1], p1, p2, p3), self._tol, self._points)

    def _qCurveToOne(self, p1, p2) -> None:
        flatten_curve(_quad_at(self._points[-1], p1, p2), self._tol, self._points)

    def _closePath(self) -> None:
        self._flush()

    def _endPath(self) -> None:  # contorno aberto: Polygon fecha sozinho
        self._flush()

    def _flush(self) -> None:
        if self._points:
            self.contours.append(self._points)
        self._points = []


class FontToolsTextVectorizer(ITextVectorizer):
    """Vetoriza texto com fontTools; uma GlyphShapes por letra com corpo."""

    def __init__(self, approximation: float = 0.1) -> None:
        if approximation <= 0:
            raise TextVectorizeError("approximation deve ser positiva (mm).")
        self._approximation = approximation

    def vectorize(self, text: str, font_path: str, size_mm: float) -> list[GlyphShapes]:
        if size_mm <= 0:
            raise TextVectorizeError("size_mm deve ser positivo (mm).")
        try:
            font = TTFont(font_path)
        except Exception as exc:  # TTLibError/OSError variados
            msg = f"Nao foi possivel abrir a fonte ({font_path}): {exc}"
            raise TextVectorizeError(msg) from exc
        try:
            return self._vectorize(font, text, size_mm)
        finally:
            font.close()

    # -- internas ---------------------------------------------------------------

    def _vectorize(self, font: TTFont, text: str, size_mm: float) -> list[GlyphShapes]:
        try:
            cmap = font.getBestCmap()
        except Exception as exc:
            raise TextVectorizeError(f"Fonte sem tabela de caracteres (cmap): {exc}") from exc
        missing = sorted({ch for ch in text if ord(ch) not in cmap})
        if missing:
            raise TextVectorizeError(
                "Caracteres sem glifo na fonte: " + ", ".join(repr(ch) for ch in missing)
            )
        scale = size_mm / font["head"].unitsPerEm
        tol_units = self._approximation / scale
        glyph_set = font.getGlyphSet()
        hmtx = font["hmtx"]

        # passo 1: contornos achatados, posicionados pelo advance e com o
        # flip de Y, ainda em unidades da fonte
        placed: list[tuple[str, list[list[tuple[float, float]]]]] = []
        cursor = 0.0
        for ch in text:
            glyph_name = cmap[ord(ch)]
            pen = _ContourPen(glyph_set, tol_units)
            glyph_set[glyph_name].draw(pen)
            contours = [[(x + cursor, -y) for x, y in contour] for contour in pen.contours]
            if contours:
                placed.append((ch, contours))
            cursor += hmtx[glyph_name][0]

        points = [p for _, contours in placed for contour in contours for p in contour]
        if not points:
            return []  # so espacos/glifos vazios
        min_x = min(x for x, _ in points)
        min_y = min(y for _, y in points)

        # passo 2: normaliza o conjunto para (0, 0), converte para mm e
        # resolve furos POR GLIFO
        result: list[GlyphShapes] = []
        for ch, contours in placed:
            rings: list[Polygon] = []
            for contour in contours:
                ring = to_ring([(x - min_x, y - min_y) for x, y in contour], scale)
                if ring is not None:
                    rings.append(ring)
            shapes = group_rings(rings)
            if shapes:
                result.append(GlyphShapes(ch, tuple(shapes)))
        return result
