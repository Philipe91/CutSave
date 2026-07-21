import pytest
from app.domain.geometry import Point2D
from app.domain.model.cut_contour import CutContour
from app.infrastructure.exporters.svg_layout_exporter import write_layout_svg
from app.shared.errors import DxfExportError


def _rect(x0, y0, w, h):
    return CutContour([
        Point2D(x0, y0),
        Point2D(x0 + w, y0),
        Point2D(x0 + w, y0 + h),
        Point2D(x0, y0 + h),
    ])


def test_svg_com_tamanho_fisico_e_furo_como_subpath(tmp_path):
    out = str(tmp_path / "layout.svg")
    # peca com furo: outer + anel interno no MESMO path (evenodd vaza o furo)
    write_layout_svg([[_rect(0, 0, 40, 40), _rect(10, 10, 8, 8)]], 100.0, 50.0, out)
    svg = (tmp_path / "layout.svg").read_text(encoding="utf-8")
    assert 'width="100.00mm"' in svg and 'height="50.00mm"' in svg
    assert 'viewBox="0 0 100.00 50.00"' in svg  # 1 unidade = 1mm
    assert svg.count("<path") == 1  # outer + furo juntos na mesma peca
    assert svg.count("M ") == 2 and svg.count("Z") == 2  # dois subpaths
    assert 'fill-rule="evenodd"' in svg
    assert 'stroke="#ff00ff"' in svg and 'fill="none"' in svg  # faca magenta


def test_uma_path_por_peca(tmp_path):
    out = str(tmp_path / "layout.svg")
    write_layout_svg([[_rect(0, 0, 10, 10)], [_rect(20, 0, 10, 10)]], 50.0, 20.0, out)
    svg = (tmp_path / "layout.svg").read_text(encoding="utf-8")
    assert svg.count("<path") == 2


def test_caminho_invalido_lanca_erro(tmp_path):
    with pytest.raises(DxfExportError):
        write_layout_svg([[_rect(0, 0, 10, 10)]], 50.0, 20.0, str(tmp_path / "nao" / "x.svg"))
