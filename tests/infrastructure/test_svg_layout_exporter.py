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


def test_contorno_com_curva_sai_com_comando_C(tmp_path):
    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import BezierSegment, line_segment
    from app.domain.model.cut_contour import CutContour

    a, b, c = Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)
    curvo = BezierSegment(a, Point2D(3, 2), Point2D(7, 2), b)
    contorno = CutContour((a, b, c), (curvo, line_segment(b, c), line_segment(c, a)))
    out = str(tmp_path / "curva.svg")

    write_layout_svg([[contorno]], 100.0, 50.0, out)
    d = open(out, encoding="utf-8").read()

    assert " C " in d, "trecho curvo tem que sair como C, nao como L"
    assert d.count(" C ") == 1, "so o trecho curvo e C; os retos sao L"


def test_retangulo_continua_so_com_L(tmp_path):
    """Regressao: contorno sem curva sai exatamente como antes."""
    from app.domain.geometry import Point2D
    from app.domain.model.cut_contour import CutContour

    contorno = CutContour(
        (Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10))
    )
    out = str(tmp_path / "ret.svg")

    write_layout_svg([[contorno]], 50.0, 20.0, out)
    d = open(out, encoding="utf-8").read()

    assert " C " not in d
    assert " L " in d


def test_trechos_retos_dentro_de_contorno_curvo_saem_como_L(tmp_path):
    """Reta gravada como reta: arquivo mais limpo e corte mais previsivel que
    uma 'curva' cujos controles estao sobre a corda."""
    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import line_segment
    from app.domain.model.cut_contour import CutContour

    a, b, c = Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)
    contorno = CutContour(
        (a, b, c), (line_segment(a, b), line_segment(b, c), line_segment(c, a))
    )
    out = str(tmp_path / "retas.svg")

    write_layout_svg([[contorno]], 50.0, 20.0, out)
    d = open(out, encoding="utf-8").read()

    assert " C " not in d
