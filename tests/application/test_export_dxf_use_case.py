import pytest
from app.application.ports.dxf_exporter import IDxfExporter
from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from app.shared.errors import ValidationError


def _contour():
    return CutContour([Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)])


class _FakeExporter(IDxfExporter):
    def __init__(self):
        self.contours = None
        self.path = None
        self.segments = None
        self.marks = None

    def export(self, contours, output_path, *, segments=(), marks=()):
        self.contours = list(contours)
        self.path = output_path
        self.segments = list(segments)
        self.marks = list(marks)


def test_exporta_lista_de_facas():
    fake = _FakeExporter()
    result = ExportDxfUseCase(fake).execute([_contour(), _contour()], "saida.dxf")
    assert result == "saida.dxf"
    assert len(fake.contours) == 2
    assert fake.path == "saida.dxf"


def test_aceita_faca_unica():
    fake = _FakeExporter()
    ExportDxfUseCase(fake).execute(_contour(), "saida.dxf")
    assert len(fake.contours) == 1


def test_lista_vazia_falha():
    with pytest.raises(ValidationError):
        ExportDxfUseCase(_FakeExporter()).execute([], "saida.dxf")


def test_exporta_so_segmentos_sem_contornos():
    from app.domain.cut.shared import Segment

    fake = _FakeExporter()
    seg = Segment(Point2D(0, 0), Point2D(10, 0))
    ExportDxfUseCase(fake).execute([], "saida.dxf", segments=[seg])
    assert fake.contours == []
    assert len(fake.segments) == 1


def test_repassa_marcas_de_registro():
    from app.domain.cut.registration import RegistrationMark

    fake = _FakeExporter()
    mark = RegistrationMark(Point2D(5, 5), 6.0)
    ExportDxfUseCase(fake).execute(_contour(), "saida.dxf", marks=[mark])
    assert len(fake.marks) == 1
