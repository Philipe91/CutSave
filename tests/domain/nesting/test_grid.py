import pytest
from app.domain.geometry import Size
from app.domain.model.material import Material
from app.domain.nesting.grid import GridPacker, NestingPiece


def _pieces(n, w=320.0, h=92.0):
    return [NestingPiece(f"a{i}", Size(w, h)) for i in range(n)]


def _positions(layout):
    return [(round(it.position.x, 1), round(it.position.y, 1)) for it in layout.items]


def test_uma_linha_quando_cabe():
    material = Material("UV", width=1300, spacing=5, margin=0)
    layout = GridPacker().pack(_pieces(4), material)
    assert _positions(layout) == [(0, 0), (325, 0), (650, 0), (975, 0)]


def test_quebra_de_linha_automatica():
    material = Material("UV", width=1300, spacing=5, margin=0)
    layout = GridPacker().pack(_pieces(6), material)
    # 4 cabem na linha 1; as 2 restantes vao para a linha 2 (y = 92 + 5)
    assert _positions(layout) == [
        (0, 0), (325, 0), (650, 0), (975, 0),
        (0, 97), (325, 97),
    ]


def test_comprimento_utilizado():
    material = Material("UV", width=1300, spacing=5, margin=0)
    layout = GridPacker().pack(_pieces(6), material)
    # linha 2 em y=97, altura 92 -> 189
    assert layout.used_length == pytest.approx(189)


def test_espacamento_aplicado():
    material = Material("UV", width=1300, spacing=10, margin=0)
    layout = GridPacker().pack(_pieces(2, w=100, h=50), material)
    assert _positions(layout) == [(0, 0), (110, 0)]


def test_margem_desloca_inicio():
    material = Material("UV", width=1300, spacing=5, margin=20)
    layout = GridPacker().pack(_pieces(1, w=100, h=50), material)
    assert _positions(layout) == [(20, 20)]


def test_peca_maior_que_largura_e_posicionada_assim_mesmo():
    material = Material("UV", width=300, spacing=5, margin=0)
    layout = GridPacker().pack(_pieces(2, w=320, h=92), material)
    # primeira peca (maior que a largura) fica em x=0; a segunda quebra linha
    assert _positions(layout) == [(0, 0), (0, 97)]


def test_sem_pecas_layout_vazio():
    material = Material("UV", width=1300, spacing=5, margin=0)
    layout = GridPacker().pack([], material)
    assert layout.item_count == 0
    assert layout.used_length == 0.0


def test_pack_sheets_divide_em_varias_chapas():
    material = Material("UV", width=120, spacing=0, margin=0)  # 1 peca por linha
    pieces = _pieces(4, w=100, h=50)
    sheets = GridPacker().pack_sheets(pieces, material, sheet_length=60)
    # cada chapa cabe 1 linha de 50mm (proxima linha estouraria 60) -> 4 chapas
    assert len(sheets) == 4
    assert all(s.used_length == 60 for s in sheets)


def test_pack_sheets_altura_zero_retorna_chapa_unica():
    material = Material("UV", width=1300, spacing=5, margin=0)
    sheets = GridPacker().pack_sheets(_pieces(6), material, sheet_length=0)
    assert len(sheets) == 1


def test_pack_sheets_duas_linhas_por_chapa():
    material = Material("UV", width=120, spacing=0, margin=0)  # 1 peca por linha
    pieces = _pieces(4, w=100, h=50)
    # altura 110 cabe 2 linhas (50 + 50 = 100 <= 110) -> 2 chapas
    sheets = GridPacker().pack_sheets(pieces, material, sheet_length=110)
    assert len(sheets) == 2
    assert all(s.item_count == 2 for s in sheets)
