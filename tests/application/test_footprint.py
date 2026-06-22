from app.application.footprint import artwork_footprint
from app.application.use_cases.generate_rectangular_cut import GenerateRectangularCutUseCase
from app.domain.geometry import Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat


def _art():
    return Artwork(id="a0", name="a0", file_format=FileFormat.PDF,
                   size=Size(100, 50), kind=ArtKind.RETANGULAR)


def test_sem_faca_footprint_e_a_arte():
    fp = artwork_footprint(_art())
    assert fp.min_x == 0 and fp.min_y == 0
    assert fp.size == Size(100, 50)


def test_faca_externa_footprint_e_a_faca():
    art = GenerateRectangularCutUseCase().execute(_art(), offset_mm=5.0)  # faca p/ fora
    fp = artwork_footprint(art)
    assert fp.size == Size(110, 60)  # 100+10 x 50+10
    assert (fp.min_x, fp.min_y) == (-5, -5)


def test_faca_interna_footprint_continua_sendo_a_arte():
    art = GenerateRectangularCutUseCase().execute(_art(), offset_mm=-5.0)  # recuo p/ dentro
    fp = artwork_footprint(art)
    # faca menor (90x40), mas a peca ainda ocupa a arte inteira -> sem sobreposicao
    assert fp.size == Size(100, 50)
    assert (fp.min_x, fp.min_y) == (0, 0)
