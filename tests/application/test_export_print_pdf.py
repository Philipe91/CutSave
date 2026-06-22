import pytest
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.shared.errors import ValidationError


def _rect_faca(w, h):
    return CutContour([Point2D(0, 0), Point2D(w, 0), Point2D(w, h), Point2D(0, h)])


def _faca_offset(art_w, art_h, off):
    # faca realista: centrada na arte, deslocada off em cada lado
    w, h = art_w + 2 * off, art_h + 2 * off
    return CutContour([
        Point2D(-off, -off), Point2D(w - off, -off),
        Point2D(w - off, h - off), Point2D(-off, h - off),
    ])


def _artwork(art_id, w, h, faca=None):
    return Artwork(
        id=art_id, name=art_id, file_format=FileFormat.PDF,
        size=Size(w, h), kind=ArtKind.RETANGULAR, cut_contour=faca,
    )


def _layout(items, used_length=98.0):
    return Layout(Material("UV", width=1300), items, used_length)


class _FakeExporter(IPrintPdfExporter):
    def __init__(self):
        self.sheets = None
        self.path = None

    def export(self, sheets, output_path):
        self.sheets = list(sheets)
        self.path = output_path


def test_carimba_arte_centralizada_na_celula_da_faca():
    # faca +3 (origem -3,-3); arte real 320x92 -> arte vai p/ (10,20)+3 = (13,23)
    art = _artwork("a0", 320, 92, faca=_faca_offset(320, 92, 3))
    layout = _layout([PlacedItem("a0", Point2D(10, 20))])
    fake = _FakeExporter()
    ExportPrintPdfUseCase(fake).execute([layout], [art], {"a0": ("bike.pdf", 0)}, "IMPRESSAO.pdf")

    pl = fake.sheets[0].placements[0]
    assert (round(pl.position.x, 1), round(pl.position.y, 1)) == (13.0, 23.0)
    assert pl.size == Size(320, 92)
    assert (pl.source_path, pl.source_page) == ("bike.pdf", 0)


def test_uma_pagina_por_chapa():
    art = _artwork("a0", 100, 50)
    s1 = _layout([PlacedItem("a0", Point2D(0, 0))], used_length=50.0)
    s2 = _layout([PlacedItem("a0", Point2D(0, 0))], used_length=50.0)
    fake = _FakeExporter()
    ExportPrintPdfUseCase(fake).execute([s1, s2], [art], {"a0": ("x.pdf", 0)}, "out.pdf")
    assert len(fake.sheets) == 2
    assert fake.sheets[0].size == Size(1300, 50)


def test_sem_faca_nao_aplica_inset():
    art = _artwork("a0", 100, 50)
    layout = _layout([PlacedItem("a0", Point2D(5, 5))], used_length=50.0)
    fake = _FakeExporter()
    ExportPrintPdfUseCase(fake).execute([layout], [art], {"a0": ("x.pdf", 0)}, "out.pdf")
    pos = fake.sheets[0].placements[0].position
    assert (pos.x, pos.y) == (5, 5)


def test_sem_chapas_com_pecas_falha():
    with pytest.raises(ValidationError):
        ExportPrintPdfUseCase(_FakeExporter()).execute(
            [_layout([], used_length=0.0)], [], {}, "out.pdf"
        )


def test_origem_ausente_falha():
    art = _artwork("a0", 100, 50)
    layout = _layout([PlacedItem("a0", Point2D(0, 0))], used_length=50.0)
    with pytest.raises(ValidationError):
        ExportPrintPdfUseCase(_FakeExporter()).execute([layout], [art], {}, "out.pdf")
