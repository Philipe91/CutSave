from app.domain.cut.shared import Segment, build_shared_grid
from app.domain.geometry import BoundingBox, Point2D


def test_vazio_retorna_lista_vazia():
    assert build_shared_grid([]) == []


def test_peca_unica_degrada_para_contorno():
    segs = build_shared_grid([BoundingBox(0, 0, 10, 10)])
    # 2 verticais (x=0, x=10) + 2 horizontais (y=0, y=10)
    assert len(segs) == 4
    assert Segment(Point2D(0, 0), Point2D(0, 10)) in segs
    assert Segment(Point2D(0, 10), Point2D(10, 10)) in segs


def test_grade_2x2_compartilha_linha_no_meio_do_vao():
    cells = [
        BoundingBox(0, 0, 10, 10),
        BoundingBox(12, 0, 22, 10),
        BoundingBox(0, 12, 10, 22),
        BoundingBox(12, 12, 22, 22),
    ]
    segs = build_shared_grid(cells)
    # 3 verticais (0, 11, 22) + 3 horizontais (0, 11, 22)
    assert len(segs) == 6
    # separador interno no meio do vao (gap de 10 a 12 -> 11), de fora a fora
    assert Segment(Point2D(11, 0), Point2D(11, 22)) in segs
    assert Segment(Point2D(0, 11), Point2D(22, 11)) in segs


def test_linha_horizontal_vai_de_fora_a_fora():
    cells = [BoundingBox(0, 0, 10, 50), BoundingBox(110, 0, 120, 50)]
    segs = build_shared_grid(cells)
    horizontais = [s for s in segs if s.start.y == s.end.y]
    for s in horizontais:
        assert s.start.x == 0 and s.end.x == 120


# --- Tamanhos misturados (13/10/2026) ---------------------------------------
# A grade projetava TODAS as pecas nos eixos: com uma peca 10x10 em cima de
# uma 30x10 nao existia linha em x=10 e a peca pequena saia com um rabo de
# 20mm de material (nunca cortada no lado direito). Grade so vale quando as
# pecas formam grade de verdade; senao, cada peca leva o proprio contorno.

_T = 1e-6


def _segment_crosses_interior(s: Segment, r: BoundingBox) -> bool:
    if abs(s.start.x - s.end.x) <= _T:  # vertical
        x = s.start.x
        y0, y1 = sorted((s.start.y, s.end.y))
        return r.min_x + _T < x < r.max_x - _T and y0 < r.max_y - _T and y1 > r.min_y + _T
    y = s.start.y
    x0, x1 = sorted((s.start.x, s.end.x))
    return r.min_y + _T < y < r.max_y - _T and x0 < r.max_x - _T and x1 > r.min_x + _T


def _side_cut(segs, rects, r: BoundingBox, side: str, folga: float) -> bool:
    """Existe linha cobrindo o lado inteiro de r, RENTE a ele (no maximo a
    meio vao de distancia) e sem outra peca no caminho."""
    for s in segs:
        vertical = abs(s.start.x - s.end.x) <= _T
        if side in ("L", "R") and vertical:
            x = s.start.x
            y0, y1 = sorted((s.start.y, s.end.y))
            if y0 > r.min_y + _T or y1 < r.max_y - _T:
                continue
            if side == "R" and x < r.max_x - _T or side == "L" and x > r.min_x + _T:
                continue
            if abs(x - (r.max_x if side == "R" else r.min_x)) > folga + _T:
                continue
            lo, hi = sorted((x, r.max_x if side == "R" else r.min_x))
            # nenhuma outra peca (na faixa de y de r) entre a borda e a linha
            if not any(
                o is not r and o.min_x < hi - _T and o.max_x > lo + _T
                and o.min_y < r.max_y - _T and o.max_y > r.min_y + _T
                for o in rects
            ):
                return True
        if side in ("T", "B") and not vertical:
            y = s.start.y
            x0, x1 = sorted((s.start.x, s.end.x))
            if x0 > r.min_x + _T or x1 < r.max_x - _T:
                continue
            if side == "B" and y < r.max_y - _T or side == "T" and y > r.min_y + _T:
                continue
            if abs(y - (r.max_y if side == "B" else r.min_y)) > folga + _T:
                continue
            lo, hi = sorted((y, r.max_y if side == "B" else r.min_y))
            if not any(
                o is not r and o.min_y < hi - _T and o.max_y > lo + _T
                and o.min_x < r.max_x - _T and o.max_x > r.min_x + _T
                for o in rects
            ):
                return True
    return False


def _assert_toda_peca_cortada(rects, gap):
    segs = build_shared_grid(rects)
    for r in rects:
        for s in segs:
            assert not _segment_crosses_interior(s, r), (s, r)
        for side in "LRTB":
            assert _side_cut(segs, rects, r, side, gap / 2), (r, side)


def test_peca_pequena_sobre_peca_larga_e_cortada_dos_quatro_lados():
    _assert_toda_peca_cortada([BoundingBox(0, 0, 10, 10), BoundingBox(0, 12, 30, 22)], 2.0)


def test_grade_uniforme_continua_compartilhada():
    cells = [BoundingBox(c * 12, r * 12, c * 12 + 10, r * 12 + 10)
             for r in range(3) for c in range(4)]
    segs = build_shared_grid(cells)
    assert len(segs) == 5 + 4  # 5 verticais + 4 horizontais fora a fora


def test_propriedade_layouts_de_shelf_aleatorios_tem_toda_peca_cortada():
    import random

    rng = random.Random(7)
    for _ in range(300):
        gap = rng.choice([0.0, 2.0, 5.0])
        rects = []
        y = 0.0
        for _row in range(rng.randint(1, 4)):
            x = 0.0
            row_h = 0.0
            uniforme = rng.random() < 0.4
            w0, h0 = rng.uniform(5, 40), rng.uniform(5, 40)
            for _col in range(rng.randint(1, 5)):
                w, h = (w0, h0) if uniforme else (rng.uniform(5, 40), rng.uniform(5, 40))
                rects.append(BoundingBox(x, y, x + w, y + h))
                x += w + gap
                row_h = max(row_h, h)
            y += row_h + gap
        _assert_toda_peca_cortada(rects, gap)
