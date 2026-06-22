from dataclasses import FrozenInstanceError

import pytest
from app.domain.model.export_job import ExportFormat, ExportJob, ExportStatus
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.shared.errors import ValidationError


def _job(**kw):
    layout = Layout(material=Material(name="Adesivo", width=1000.0), items=[])
    base = dict(id="j1", layout=layout, export_format=ExportFormat.DXF, output_path="saida.dxf")
    base.update(kw)
    return ExportJob(**base)


def test_export_job_status_default_pending():
    assert _job().status is ExportStatus.PENDING


def test_with_status_retorna_nova_copia():
    job = _job()
    concluido = job.with_status(ExportStatus.COMPLETED)
    assert concluido.status is ExportStatus.COMPLETED
    assert job.status is ExportStatus.PENDING  # original intacto


def test_export_job_exige_output_path():
    with pytest.raises(ValidationError):
        _job(output_path="   ")


def test_export_job_imutavel():
    job = _job()
    with pytest.raises(FrozenInstanceError):
        job.status = ExportStatus.FAILED
