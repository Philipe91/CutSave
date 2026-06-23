import pytest
from app.domain.cut.mimaki import MimakiMarkGenerator
from app.domain.geometry import BoundingBox
from app.shared.errors import ValidationError


def test_quadro_afastado_da_bbox():
    marks = MimakiMarkGenerator().generate(
        BoundingBox(0, 0, 100, 50), distance_mm=15, mark_size_mm=15
    )
    f = marks.frame
    assert (f.min_x, f.min_y, f.max_x, f.max_y) == (-15, -15, 115, 65)


def test_oito_segmentos_em_l():
    marks = MimakiMarkGenerator().generate(
        BoundingBox(0, 0, 100, 50), distance_mm=15, mark_size_mm=15
    )
    assert len(marks.segments) == 8  # 2 por canto


def test_marca_tem_o_tamanho_pedido():
    marks = MimakiMarkGenerator().generate(
        BoundingBox(0, 0, 100, 50), distance_mm=10, mark_size_mm=15
    )
    # primeiro segmento: horizontal do canto sup-esq, comprimento 15
    seg = marks.segments[0]
    assert abs(seg.end.x - seg.start.x) == 15


def test_frame_contour_fecha_o_quadro():
    gen = MimakiMarkGenerator()
    marks = gen.generate(BoundingBox(0, 0, 100, 50), distance_mm=15, mark_size_mm=15)
    contour = gen.frame_contour(marks)
    assert contour.size.width == 130
    assert contour.size.height == 80


@pytest.mark.parametrize("dist,size", [(-1, 15), (15, 0)])
def test_validacoes(dist, size):
    bbox = BoundingBox(0, 0, 100, 50)
    with pytest.raises(ValidationError):
        MimakiMarkGenerator().generate(bbox, distance_mm=dist, mark_size_mm=size)
