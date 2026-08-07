from app.application.positioning import (
    SHEET_GAP_MM,
    cuts_bounding_box,
    positioned_cut_contours,
    positioned_cut_contours_sheets,
    registration_marks,
    shared_cut_segments,
)
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem


def _faca(x0, y0, w, h):
    return CutContour([
        Point2D(x0, y0), Point2D(x0 + w, y0), Point2D(x0 + w, y0 + h), Point2D(x0, y0 + h)
    ])


def _artwork(art_id, faca):
    return Artwork(id=art_id, name=art_id, file_format=FileFormat.PDF,
                   size=Size(faca.size.width, faca.size.height), kind=ArtKind.RETANGULAR,
                   cut_contour=faca)


def test_faca_e_transladada_para_a_posicao_no_layout():
    # faca em (-3,-3)..(323,95); peca posicionada em (0,0) -> faca vira (0,0)..(326,98)
    art = _artwork("a0", _faca(-3, -3, 326, 98))
    layout = Layout(Material("UV", width=1300), [PlacedItem("a0", Point2D(0, 0))], 98.0)
    contours = positioned_cut_contours(layout, [art])
    assert len(contours) == 1
    assert contours[0].origin == Point2D(0, 0)
    assert contours[0].size == Size(326, 98)


def test_ignora_pecas_sem_faca():
    art = Artwork(id="a0", name="a0", file_format=FileFormat.PDF,
                  size=Size(100, 50), kind=ArtKind.RETANGULAR)  # sem faca
    layout = Layout(Material("UV", width=1300), [PlacedItem("a0", Point2D(0, 0))], 50.0)
    assert positioned_cut_contours(layout, [art]) == []


def test_chapas_lado_a_lado_deslocam_em_x():
    art = _artwork("a0", _faca(0, 0, 100, 50))
    mat = Material("UV", width=200)
    s1 = Layout(mat, [PlacedItem("a0", Point2D(0, 0))], 50.0)
    s2 = Layout(mat, [PlacedItem("a0", Point2D(0, 0))], 50.0)

    contours = positioned_cut_contours_sheets([s1, s2], [art], sheet_width=200)
    assert len(contours) == 2
    # chapa 0 em x=0; chapa 1 deslocada por largura + gap
    assert contours[0].origin == Point2D(0, 0)
    assert contours[1].origin == Point2D(200 + SHEET_GAP_MM, 0)


def test_bbox_dos_cortes_envolve_todas_as_facas():
    art = _artwork("a0", _faca(0, 0, 100, 50))
    mat = Material("UV", width=1300)
    layout = Layout(mat, [PlacedItem("a0", Point2D(0, 0)), PlacedItem("a0", Point2D(110, 0))], 50.0)
    bbox = cuts_bounding_box(layout, [art])
    assert (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y) == (0, 0, 210, 50)


def test_faca_compartilhada_gera_grade():
    art = _artwork("a0", _faca(0, 0, 100, 50))
    mat = Material("UV", width=1300)
    layout = Layout(mat, [PlacedItem("a0", Point2D(0, 0)), PlacedItem("a0", Point2D(110, 0))], 50.0)
    segs = shared_cut_segments(layout, [art])
    # 3 verticais (0, 105, 210) + 2 horizontais (0, 50)
    assert len(segs) == 5
    assert any(s.start.x == 105 and s.end.x == 105 for s in segs)


def test_marcas_de_registro_em_volta_da_chapa():
    art = _artwork("a0", _faca(0, 0, 100, 50))
    mat = Material("UV", width=1300)
    layout = Layout(mat, [PlacedItem("a0", Point2D(0, 0))], 50.0)
    marks = registration_marks(layout, [art], margin_mm=15.0, diameter_mm=6.0)
    assert len(marks) == 5


def test_sem_faca_nao_gera_marcas():
    art = Artwork(id="a0", name="a0", file_format=FileFormat.PDF,
                  size=Size(100, 50), kind=ArtKind.RETANGULAR)
    layout = Layout(Material("UV", width=1300), [PlacedItem("a0", Point2D(0, 0))], 50.0)
    assert registration_marks(layout, [art], margin_mm=15.0, diameter_mm=6.0) == []
    assert cuts_bounding_box(layout, [art]) is None


# ---- giro POR PECA (07/08/2026) ---------------------------------------------
# O nesting do Modo Impressao vai passar a girar peca (MaxRectsPacker,
# allow_rotate). Sem estes testes, a faca sairia desenhada SEM girar dentro do
# espaco que o encaixe reservou GIRADO: pecas sobrepostas na chapa, calado.

def _layout_girado(art, graus, pos=Point2D(0, 0), largura=1300.0, comprimento=500.0):
    return Layout(
        Material("UV", width=largura),
        [PlacedItem(art.id, pos, graus)],
        comprimento,
    )


def test_faca_girada_90_troca_os_lados():
    art = _artwork("a0", _faca(0, 0, 300, 100))
    contours = positioned_cut_contours(_layout_girado(art, 90), [art])
    assert contours[0].size == Size(100, 300)


def test_faca_girada_180_mantem_os_lados():
    art = _artwork("a0", _faca(0, 0, 300, 100))
    contours = positioned_cut_contours(_layout_girado(art, 180), [art])
    assert contours[0].size == Size(300, 100)


def test_faca_girada_comeca_na_posicao_da_peca():
    """O canto da peca girada tem de cair EXATAMENTE onde o encaixe a pos."""
    art = _artwork("a0", _faca(0, 0, 300, 100))
    contours = positioned_cut_contours(
        _layout_girado(art, 90, pos=Point2D(200.0, 50.0)), [art]
    )
    assert contours[0].origin == Point2D(200.0, 50.0)


def test_faca_com_sangria_girada_nao_escapa_do_espaco_reservado():
    """Peca cuja faca esta DESLOCADA em relacao a arte (sangria assimetrica).

    Aqui a faca NAO comeca no canto da peca depois de girada, e esta certo: o
    footprint inclui a arte, que ultrapassa a faca embaixo; girado 90, esse
    pedaco vai para a esquerda. O que importa — e o que impede sobreposicao —
    e a faca caber INTEIRA dentro do espaco que o encaixe reservou."""
    from app.application.footprint import tamanho_ocupado

    art = _artwork("a0", _faca(-3, -3, 326, 98))
    ocupado = tamanho_ocupado(art, 90)
    pos = Point2D(10.0, 20.0)
    contour = positioned_cut_contours(_layout_girado(art, 90, pos=pos), [art])[0]
    assert contour.size == Size(98, 326), "a faca girada troca os lados"
    xs = [p.x for p in contour.points]
    ys = [p.y for p in contour.points]
    assert min(xs) >= pos.x - 1e-9 and max(xs) <= pos.x + ocupado.width + 1e-9
    assert min(ys) >= pos.y - 1e-9 and max(ys) <= pos.y + ocupado.height + 1e-9


def test_marcas_de_registro_seguem_a_peca_girada():
    """cuts_bounding_box alimenta as marcas; girar a peca move as marcas."""
    art = _artwork("a0", _faca(0, 0, 300, 100))
    reto = cuts_bounding_box(_layout_girado(art, 0), [art])
    girado = cuts_bounding_box(_layout_girado(art, 90), [art])
    assert (reto.max_x - reto.min_x, reto.max_y - reto.min_y) == (300, 100)
    assert (girado.max_x - girado.min_x, girado.max_y - girado.min_y) == (100, 300)


def test_sem_giro_nada_muda():
    """Regressao explicita: o caminho de sempre continua idêntico."""
    art = _artwork("a0", _faca(-3, -3, 326, 98))
    layout = Layout(Material("UV", width=1300), [PlacedItem("a0", Point2D(7, 11))], 98.0)
    contours = positioned_cut_contours(layout, [art])
    assert contours[0].origin == Point2D(7, 11)
    assert contours[0].size == Size(326, 98)
