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

    def export(self, contours, output_path):
        self.contours = list(contours)
        self.path = output_path


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
