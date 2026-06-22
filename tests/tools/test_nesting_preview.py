from app.domain.geometry import Size
from app.domain.model.material import Material
from app.domain.nesting.grid import GridPacker, NestingPiece
from app.tools.nesting_preview import format_layout


def test_preview_logico_mostra_pecas_e_linhas():
    material = Material("UV", width=1300, spacing=5, margin=0)
    pieces = [NestingPiece(f"a{i}", Size(320, 92)) for i in range(6)]
    layout = GridPacker().pack(pieces, material)
    texto = format_layout(layout)
    assert "Pecas: 6" in texto
    assert "linha 1" in texto
    assert "linha 2" in texto
    assert "a0: x=0.0 y=0.0" in texto
