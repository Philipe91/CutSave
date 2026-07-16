"""Cartelas IDENTICAS: a tabela define o conteudo de UMA cartela e a chapa
inteira e preenchida com copias exatas dela (fluxo classico da grafica:
uma faca Mimaki serve para todas; o refile separa as copias)."""

from app.application.use_cases.cartela_nesting import IdenticalCartelaNestingUseCase
from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
from app.domain.geometry import Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.material import Material
from app.domain.nesting.max_rects import MaxRectsPacker


def _art(i: int, w: float = 100.0, h: float = 100.0) -> Artwork:
    art = Artwork(
        id=f"a{i}", name=f"a{i}", file_format=FileFormat.PDF,
        size=Size(w, h), kind=ArtKind.RETANGULAR,
    )
    return GenerateRectangularCutUseCase().execute(art, 0.0)


def _uc(cell_w=330.0, cell_h=480.0, gutter=0.0, margin=5.0):
    return IdenticalCartelaNestingUseCase(
        RunGridNestingUseCase(MaxRectsPacker()), cell_w, cell_h, gutter, margin
    )


def _slot_content(layout, grid, slot):
    """Conjunto de (id, x, y) RELATIVOS ao canto da cartela 'slot'."""
    ox, oy = grid.slot_origin(slot)
    eps = 1e-6
    return sorted(
        (it.artwork_id, round(it.position.x - ox, 6), round(it.position.y - oy, 6))
        for it in layout.items
        if ox - eps <= it.position.x <= ox + grid.cell_w + eps
        and oy - eps <= it.position.y <= oy + grid.cell_h + eps
    )


def test_chapa_cheia_de_copias_identicas():
    material = Material("m", width=700, spacing=2)
    uc = _uc()
    arts = [_art(0), _art(1)]  # conteudo de UMA cartela: 2 pecas
    sheets = uc.execute_sheets(arts, material, 1000)
    assert len(sheets) == 1
    grid = uc.grid_for(material, 1000)  # 2 x 2 = 4 cartelas
    assert grid.per_sheet == 4
    assert sheets[0].item_count == 2 * 4  # 2 pecas x 4 cartelas
    base = _slot_content(sheets[0], grid, 0)
    assert len(base) == 2
    for slot in range(1, 4):  # TODAS as cartelas iguais a primeira
        assert _slot_content(sheets[0], grid, slot) == base


def test_renesting_da_producao_replicada_nao_multiplica():
    """Re-nesting (mudar espaco/giro): as instancias chegam ja replicadas
    (conteudo x cartelas); o use case recupera o conteudo de UMA cartela."""
    material = Material("m", width=700, spacing=2)
    uc = _uc()
    arts = [_art(0), _art(1)]
    sheets = uc.execute_sheets(arts, material, 1000)
    # simula o _relayout sem from_table: instancias = producao atual, na ordem
    by_id = {a.id: a for a in arts}
    replicated = [by_id[it.artwork_id] for it in sheets[0].items]
    assert len(replicated) == 8
    uc2 = _uc()
    uc2.set_from_table(False)
    again = uc2.execute_sheets(replicated, material, 1000)
    assert again[0].item_count == 8  # continua 2 x 4, nao 8 x 4


def test_conteudo_que_nao_cabe_cai_no_sequencial():
    """Quantidade grande demais para uma cartela: nao quebra — usa o encaixe
    sequencial da classe mae (cartelas preenchidas em ordem)."""
    material = Material("m", width=700, spacing=2)
    sheets = _uc().execute_sheets([_art(i) for i in range(30)], material, 1000)
    total = sum(s.item_count for s in sheets)
    assert total == 30  # producao completa preservada


def test_conteudo_centralizado_no_corte():
    """A cartela e centralizada DENTRO do corte (pedido 15/07): o encaixe
    empacotava tudo no canto superior esquerdo e o refile saia com a sobra
    toda de um lado so."""
    material = Material("m", width=700, spacing=2)
    uc = _uc()
    sheets = uc.execute_sheets([_art(0)], material, 1000)  # 1 peca de 100x100
    grid = uc.grid_for(material, 1000)
    assert sheets[0].item_count == grid.per_sheet  # 1 peca por cartela
    esperados = {
        (round(ox + (330 - 100) / 2, 6), round(oy + (480 - 100) / 2, 6))
        for ox, oy in (grid.slot_origin(s) for s in range(grid.per_sheet))
    }
    reais = {
        (round(i.position.x, 6), round(i.position.y, 6)) for i in sheets[0].items
    }
    assert reais == esperados


def test_chapa_aberta_replica_uma_fileira():
    material = Material("m", width=700, spacing=2)
    uc = _uc()
    sheets = uc.execute_sheets([_art(0)], material, 0)  # comprimento livre
    grid = uc.grid_for(material, 0)
    assert sheets[0].item_count == grid.cols  # uma fileira de copias
    assert sheets[0].used_length > 0
