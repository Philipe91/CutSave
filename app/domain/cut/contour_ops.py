from __future__ import annotations

from shapely.geometry import Polygon as ShapelyPolygon

from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


def _largest_polygon(geometry):
    candidates = getattr(geometry, "geoms", None)
    if candidates is not None:
        polygons = [g for g in candidates if g.geom_type == "Polygon" and g.area > 0]
    elif geometry.geom_type == "Polygon" and geometry.area > 0:
        polygons = [geometry]
    else:
        polygons = []
    if not polygons:
        return None
    return max(polygons, key=lambda g: g.area)


def smooth_contour(contour: CutContour, iterations: int, ratio: float = 0.25) -> CutContour:
    """Suaviza a faca arredondando os cantos (algoritmo de Chaikin, fechado).

    Cada iteracao corta cada canto em dois pontos (a 'ratio' e '1-ratio' da
    aresta), trocando o vinco reto por uma curva. 1-2 iteracoes ja deixam as
    curvas macias; mais iteracoes = mais suave (e mais pontos). 0 = sem efeito.
    """
    if iterations <= 0:
        return contour
    pts = [(p.x, p.y) for p in contour.points]
    for _ in range(iterations):
        n = len(pts)
        if n < 3:
            break
        smoothed: list[tuple[float, float]] = []
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            smoothed.append((x0 + (x1 - x0) * ratio, y0 + (y1 - y0) * ratio))
            smoothed.append((x0 + (x1 - x0) * (1 - ratio), y0 + (y1 - y0) * (1 - ratio)))
        pts = smoothed
    return CutContour([Point2D(x, y) for x, y in pts])


def crop_and_rotate_contour(
    contour: CutContour, crop_mm: float, rotation: int, width: float, height: float
) -> tuple[CutContour, float, float]:
    """Recorta a borda (crop_mm) e rotaciona (0/90/180/270) o contorno de imagem.

    Devolve (contorno, largura, altura) no mesmo sistema da arte exibida, para a
    faca acompanhar o pixmap girado/cortado do preview. Usa a convencao de
    QTransform().rotate (eixo Y para baixo): 90 -> (H - y, x), 180 -> (W - x,
    H - y), 270 -> (y, W - x). Espelha o que `_transform` faz com o tamanho das
    artes vetoriais, mantendo faca, nesting e exportacao alinhados.
    """
    w = width - 2 * crop_mm
    h = height - 2 * crop_mm
    pts = [(p.x - crop_mm, p.y - crop_mm) for p in contour.points]
    r = rotation % 360
    if r == 90:
        pts = [(h - y, x) for x, y in pts]
        w, h = h, w
    elif r == 180:
        pts = [(w - x, h - y) for x, y in pts]
    elif r == 270:
        pts = [(y, w - x) for x, y in pts]
        w, h = h, w
    return CutContour([Point2D(x, y) for x, y in pts]), w, h


def offset_contour(contour: CutContour, offset_mm: float) -> CutContour:
    """Aplica um offset (mm) ao contorno: positivo cresce, negativo encolhe.

    Usa o anel externo do resultado (ignora furos). Offset zero devolve o
    contorno original. Encolher demais (poligono vazio) levanta ValidationError.
    """
    if offset_mm == 0:
        return contour
    poly = ShapelyPolygon([(p.x, p.y) for p in contour.points])
    if not poly.is_valid:
        poly = poly.buffer(0)
    grown = poly.buffer(offset_mm, join_style=2)  # join_style=2 (mitre) mantem cantos
    product = _largest_polygon(grown)
    if product is None or product.is_empty:
        raise ValidationError("Offset interno maior que o contorno da imagem.")
    coords = list(product.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return CutContour([Point2D(x, y) for x, y in coords])
