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


# --- rotacao 90 (opt-in) -----------------------------------------------------


def _rects_com_rotacao(layout, sizes):
    """Bounding boxes efetivos honrando PlacedItem.rotation (90/270 troca w/h)."""
    out = []
    for it in layout.items:
        s = sizes[it.artwork_id]
        w, h = (s.height, s.width) if int(it.rotation) % 180 == 90 else (s.width, s.height)
        out.append((it.position.x, it.position.y, w, h))
    return out


def test_rotacao_desligada_por_padrao():
    # sem allow_rotate, nada muda: peca deitada NAO gira mesmo sendo melhor.
    pieces = [NestingPiece("a", Size(60, 40)), NestingPiece("b", Size(60, 40))]
    layout = MaxRectsPacker().pack(pieces, Material("UV", width=100, margin=0))
    assert all(int(it.rotation) == 0 for it in layout.items)
    assert layout.used_length == 80  # empilhadas (60+60 nao cabe em 100)


def test_peca_que_so_cabe_deitada_e_rotacionada():
    # 80mm de largura nao cabe na chapa de 50mm; a 90 (30x80) cabe.
    pieces = [NestingPiece("a", Size(80, 30))]
    layout = MaxRectsPacker(allow_rotate=True).pack(pieces, Material("UV", width=50, margin=0))
    (item,) = layout.items
    assert int(item.rotation) == 90
    assert item.position.x + 30 <= 50 + 1e-6  # largura efetiva respeita a chapa
    assert layout.used_length == 80


def test_rotacao_melhora_aproveitamento():
    pieces = [NestingPiece("a", Size(60, 40)), NestingPiece("b", Size(60, 40))]
    mat = Material("UV", width=100, margin=0)
    sem = MaxRectsPacker().pack(pieces, mat)
    com = MaxRectsPacker(allow_rotate=True).pack(pieces, mat)
    assert com.used_length < sem.used_length  # 60 (lado a lado girada) < 80
    assert _no_overlaps(_rects_com_rotacao(com, _sizes(pieces)))


def test_pack_sheets_com_rotacao_sem_sobreposicao():
    pieces = [NestingPiece(f"a{i}", Size(300, 150)) for i in range(6)]
    sheets = MaxRectsPacker(allow_rotate=True).pack_sheets(
        pieces, Material("UV", width=400, margin=10, spacing=5, spacing_y=5), 700
    )
    assert sum(s.item_count for s in sheets) == 6  # nada se perde
    for s in sheets:
        assert _no_overlaps(_rects_com_rotacao(s, _sizes(pieces)))


# --- Peca + espacamento mais larga que a chapa (13/10/2026) -----------------
# O bin reservava largura + espacamento ate na ULTIMA coluna: uma peca da
# largura util com spacing > 0 "nao cabia" e caia no fallback, que a punha
# em (0, max_bottom) SEM marcar o espaco — as pecas seguintes iam por cima
# dela (relato real "PECA EM CIMA DE PECA" com giro automatico).


def _footprints(layout, sizes):
    out = []
    for it in layout.items:
        s = sizes[it.artwork_id]
        w, h = (s.height, s.width) if int(it.rotation) % 180 == 90 else (s.width, s.height)
        out.append((it.position.x, it.position.y, w, h))
    return out


def _assert_layout_valido(layout, pieces, mat, sheet_length=0.0):
    tol = 0.011  # _EPS do packer + folga de float
    rects = _footprints(layout, _sizes(pieces))
    for i, (x, y, w, h) in enumerate(rects):
        assert x >= mat.margin - tol and y >= mat.margin - tol
        assert x + w <= mat.width - mat.margin + tol, (x, w)
        if sheet_length > 0:
            assert y + h <= sheet_length - mat.margin + tol, (y, h)
        for (x2, y2, w2, h2) in rects[i + 1:]:
            # sobreposicao contando o espacamento exigido entre pecas
            colide = (
                x < x2 + w2 + mat.spacing - tol and x2 < x + w + mat.spacing - tol
                and y < y2 + h2 + mat.spacing_y - tol and y2 < y + h + mat.spacing_y - tol
            )
            assert not colide, ((x, y, w, h), (x2, y2, w2, h2))


def test_peca_da_largura_util_com_espacamento_nao_e_sobreposta():
    mat = Material("m", width=100, margin=0, spacing=5, spacing_y=5)
    pieces = [NestingPiece("a", Size(100, 50)), NestingPiece("b", Size(40, 40)),
              NestingPiece("c", Size(40, 40))]
    layout = MaxRectsPacker().pack(pieces, mat)
    assert layout.item_count == 3
    _assert_layout_valido(layout, pieces, mat)


def test_duas_pecas_da_largura_util_cabem_numa_chapa_fixa():
    mat = Material("m", width=100, margin=0, spacing=5, spacing_y=5)
    pieces = [NestingPiece("a", Size(100, 50)), NestingPiece("b", Size(100, 50))]
    sheets = MaxRectsPacker().pack_sheets(pieces, mat, 1000)
    assert len(sheets) == 1
    _assert_layout_valido(sheets[0], pieces, mat, 1000)


def test_peca_maior_que_a_chapa_nao_recebe_outras_por_cima():
    # fallback "nao deveria acontecer": a peca larga demais vai para baixo e
    # o espaco dela fica OCUPADO para as seguintes.
    mat = Material("m", width=100, margin=0, spacing=0, spacing_y=0)
    pieces = [NestingPiece("big", Size(150, 30)), NestingPiece("b", Size(40, 40)),
              NestingPiece("c", Size(40, 40))]
    layout = MaxRectsPacker().pack(pieces, mat)
    rects = _footprints(layout, _sizes(pieces))
    big = rects[[it.artwork_id for it in layout.items].index("big")]
    for r in rects:
        if r is big:
            continue
        assert not (r[1] < big[1] + big[3] and big[1] < r[1] + r[3]), (r, big)


def test_propriedade_pecas_aleatorias_sem_sobreposicao_e_dentro_da_chapa():
    import random

    rng = random.Random(1)
    for _ in range(150):
        W = rng.choice([300, 500, 1000])
        m = rng.choice([0, 5, 10])
        mat = Material("m", W, m, rng.choice([0, 2, 5]), rng.choice([0, 2, 5]))
        pieces = [
            NestingPiece(f"p{i}", Size(rng.uniform(10, W - 2 * m), rng.uniform(10, 300)))
            for i in range(rng.randint(1, 25))
        ]
        for rot in (False, True):
            packer = MaxRectsPacker(rot)
            layout = packer.pack(pieces, mat)
            assert layout.item_count == len(pieces)
            _assert_layout_valido(layout, pieces, mat)
            sheets = packer.pack_sheets(pieces, mat, 600)
            assert sum(s.item_count for s in sheets) == len(pieces)
            for s in sheets:
                _assert_layout_valido(s, pieces, mat, 600)
