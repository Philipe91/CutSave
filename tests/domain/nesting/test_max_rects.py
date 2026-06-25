"""Testes-ouro do MaxRectsPacker: sem sobreposicao, nada se perde, mais
aproveitamento que o grid em pecas de tamanhos variados."""

from app.domain.geometry import Size
from app.domain.model.material import Material
from app.domain.nesting.grid import GridPacker, NestingPiece
from app.domain.nesting.max_rects import MaxRectsPacker


def _sizes(pieces):
    return {p.artwork_id: p.size for p in pieces}


def _rects(layout, sizes):
    out = []
    for it in layout.items:
        s = sizes[it.artwork_id]
        out.append((it.position.x, it.position.y, s.width, s.height))
    return out


def _overlap(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    eps = 1e-6
    return (
        ax < bx + bw - eps and bx < ax + aw - eps
        and ay < by + bh - eps and by < ay + ah - eps
    )


def _no_overlaps(rects) -> bool:
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if _overlap(rects[i], rects[j]):
                return False
    return True


def test_pecas_nao_se_sobrepoem():
    pieces = [NestingPiece(f"a{i}", Size(w, h))
              for i, (w, h) in enumerate([(300, 200), (300, 200), (150, 400),
                                          (200, 150), (100, 100), (500, 100)])]
    layout = MaxRectsPacker().pack(pieces, Material("UV", width=1000, margin=0))
    assert _no_overlaps(_rects(layout, _sizes(pieces)))


def test_nada_se_perde():
    pieces = [NestingPiece(f"a{i}", Size(200, 120)) for i in range(17)]
    layout = MaxRectsPacker().pack(pieces, Material("UV", width=1000, margin=0))
    assert layout.item_count == 17  # todas as pecas posicionadas


def test_respeita_margem_e_largura():
    pieces = [NestingPiece(f"a{i}", Size(200, 120)) for i in range(10)]
    mat = Material("UV", width=1000, margin=20)
    layout = MaxRectsPacker().pack(pieces, mat)
    sizes = _sizes(pieces)
    for x, y, w, _h in _rects(layout, sizes):
        assert x >= 20 - 1e-6 and y >= 20 - 1e-6      # respeita a margem
        assert x + w <= 1000 - 20 + 1e-6              # nao passa da largura util


def test_aproveita_mais_que_o_grid():
    # pecas de alturas diferentes na mesma "linha": o grid desperdica o vao;
    # o MaxRects preenche -> comprimento usado menor (mais aproveitamento).
    pieces = [NestingPiece(f"a{i}", Size(w, h))
              for i, (w, h) in enumerate([(500, 300), (400, 100), (400, 100),
                                          (400, 100), (300, 200), (200, 200)])]
    mat = Material("UV", width=1000, margin=0)
    grid = GridPacker().pack(pieces, mat)
    mr = MaxRectsPacker().pack(pieces, mat)
    assert mr.used_length <= grid.used_length + 1e-6
    assert mr.used_length < grid.used_length  # de fato aproveitou melhor


def test_pack_sheets_divide_e_preserva_tudo():
    pieces = [NestingPiece(f"a{i}", Size(400, 300)) for i in range(10)]
    mat = Material("UV", width=1000, margin=0)
    sheets = MaxRectsPacker().pack_sheets(pieces, mat, sheet_length=700)
    assert len(sheets) >= 2
    assert sum(s.item_count for s in sheets) == 10  # nada se perde
    for s in sheets:
        assert s.used_length == 700  # chapa cheia
        assert _no_overlaps(_rects(s, _sizes(pieces)))


def test_pack_sheets_altura_zero_chapa_unica():
    pieces = [NestingPiece(f"a{i}", Size(200, 120)) for i in range(4)]
    sheets = MaxRectsPacker().pack_sheets(pieces, Material("UV", width=1000), 0)
    assert len(sheets) == 1


def test_peca_maior_que_a_chapa_nao_some():
    # peca mais larga que a chapa: deve ser posicionada assim mesmo (nao perdida).
    pieces = [NestingPiece("grande", Size(1500, 200)),
              NestingPiece("ok", Size(300, 200))]
    sheets = MaxRectsPacker().pack_sheets(pieces, Material("UV", width=1000), 500)
    assert sum(s.item_count for s in sheets) == 2


def test_sem_pecas():
    layout = MaxRectsPacker().pack([], Material("UV", width=1000))
    assert layout.item_count == 0
    assert layout.used_length == 0
