import pytest
from app.application.use_cases.cartela_nesting import CartelaNestingUseCase
from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
from app.domain.geometry import Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.material import Material
from app.domain.nesting.max_rects import MaxRectsPacker
from app.shared.errors import ValidationError


def _art(i: int, w: float = 100.0, h: float = 100.0) -> Artwork:
    art = Artwork(
        id=f"a{i}", name=f"a{i}", file_format=FileFormat.PDF,
        size=Size(w, h), kind=ArtKind.RETANGULAR,
    )
    return GenerateRectangularCutUseCase().execute(art, 0.0)


def _uc(cell_w=330.0, cell_h=480.0, gutter=0.0, margin=5.0) -> CartelaNestingUseCase:
    return CartelaNestingUseCase(
        RunGridNestingUseCase(MaxRectsPacker()), cell_w, cell_h, gutter, margin
    )


def test_pecas_ficam_dentro_das_cartelas():
    material = Material("m", width=700, spacing=2)
    # 12 pecas de 100mm: 8 por cartela (330x480 com respiro 5) nao — depende
    # do encaixe; o que TEM de valer: toda peca dentro de ALGUMA cartela.
    sheets = _uc().execute_sheets([_art(i) for i in range(12)], material, 1000)
    grid_x0, grid_y0 = 20.0, 20.0  # origem da grade (testada no dominio)
    cells = [
        (grid_x0 + c * 330, grid_y0 + r * 480)
        for r in range(2) for c in range(2)
    ]
    for layout in sheets:
        for item in layout.items:
            dentro = any(
                cx - 1e-6 <= item.position.x and item.position.x + 100 <= cx + 330 + 1e-6
                and cy - 1e-6 <= item.position.y and item.position.y + 100 <= cy + 480 + 1e-6
                for cx, cy in cells
            )
            assert dentro, f"peca em {item.position} fora de qualquer cartela"


def test_respiro_interno_afasta_da_borda_da_cartela():
    material = Material("m", width=700, spacing=0)
    sheets = _uc(margin=5.0).execute_sheets([_art(0)], material, 1000)
    item = sheets[0].items[0]
    # 1a cartela comeca em (20, 20); com respiro 5 a peca nao encosta na linha
    assert item.position.x >= 20 + 5 - 1e-6
    assert item.position.y >= 20 + 5 - 1e-6


def test_transborda_para_nova_chapa_quando_enche():
    material = Material("m", width=700, spacing=0)
    # cartela 330x480 com respiro 5 comporta 3x4=12 pecas de 100; 4 cartelas
    # por chapa = 48. Com 49 pecas TEM de abrir a 2a chapa.
    sheets = _uc().execute_sheets([_art(i) for i in range(49)], material, 1000)
    assert len(sheets) == 2
    assert sum(len(s.items) for s in sheets) == 49


def test_conteudo_centralizado_no_corte():
    """Tambem no encaixe sequencial cada cartela sai centrada no corte."""
    material = Material("m", width=700, spacing=0)
    sheets = _uc().execute_sheets([_art(0)], material, 1000)
    item = sheets[0].items[0]
    assert item.position.x == pytest.approx(20 + (330 - 100) / 2)
    assert item.position.y == pytest.approx(20 + (480 - 100) / 2)


def test_cartela_maior_que_a_chapa_erro_amigavel():
    material = Material("m", width=300, spacing=0)
    with pytest.raises(ValidationError):
        _uc().execute_sheets([_art(0)], material, 400)
