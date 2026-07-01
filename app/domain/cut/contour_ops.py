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


def simplify_contour(contour: CutContour, tolerance_mm: float) -> CutContour:
    """Reduz os nos da faca (Douglas-Peucker via shapely) para tirar ruido/
    serrilhado da deteccao sem perder a forma. tolerance 0 = sem efeito; maior =
    faca mais lisa (menos nos). E o controle de 'densidade' da faca."""
    if tolerance_mm <= 0 or len(contour.points) < 4:
        return contour
    try:
        poly = ShapelyPolygon([(p.x, p.y) for p in contour.points])
        if not poly.is_valid:
            poly = poly.buffer(0)
        simp = poly.simplify(tolerance_mm, preserve_topology=True)
        ring = _largest_polygon(simp)
        if ring is None:
            return contour
        coords = list(ring.exterior.coords)[:-1]  # tira o ponto de fechamento repetido
    except Exception:
        return contour
    if len(coords) < 3:
        return contour
    return CutContour([Point2D(float(x), float(y)) for x, y in coords])


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


# Estilo de canto do offset (igual ao "Corners" da ferramenta Contorno do Corel).
_JOIN_STYLE = {"round": 1, "miter": 2, "bevel": 3}


def offset_contour(
    contour: CutContour, offset_mm: float, corner: str = "round", mitre_limit: float = 2.0
) -> CutContour:
    """Aplica um offset (mm) ao contorno: positivo cresce, negativo encolhe.

    `corner` define o estilo do canto (como a ferramenta Contorno do CorelDRAW):
    'round' (redondo, padrao seguro para a lamina), 'miter' (ponta viva, limitada
    por `mitre_limit` para nao criar farpas) ou 'bevel' (chanfro). Usa o anel
    externo do resultado (ignora furos). Offset zero devolve o contorno original.
    Encolher demais (poligono vazio) levanta ValidationError.
    """
    if offset_mm == 0:
        return contour
    poly = ShapelyPolygon([(p.x, p.y) for p in contour.points])
    if not poly.is_valid:
        poly = poly.buffer(0)
    join = _JOIN_STYLE.get(corner, 1)
    grown = poly.buffer(offset_mm, join_style=join, mitre_limit=mitre_limit)
    product = _largest_polygon(grown)
    if product is None or product.is_empty:
        raise ValidationError("Offset interno maior que o contorno da imagem.")
    coords = list(product.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return CutContour([Point2D(x, y) for x, y in coords])
