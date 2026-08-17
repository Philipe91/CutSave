import math

import pytest
from app.infrastructure.importers.svg_vector_importer import SvgVectorImporter
from app.shared.errors import VectorImportError

# Nos fixtures abaixo width/viewBox casam 1:1 (100mm p/ 100 unidades), entao
# 1 unidade de usuario = 1mm — as assercoes leem direto em mm.
_XMLNS = 'xmlns="http://www.w3.org/2000/svg"'
_HEADER = f'<svg {_XMLNS} width="100mm" height="100mm" viewBox="0 0 100 100">'


def _load(tmp_path, body: str, header: str = _HEADER, **kwargs):
    svg = tmp_path / "fixture.svg"
    svg.write_text(f"{header}{body}</svg>", encoding="utf-8")
    return SvgVectorImporter(**kwargs).load(str(svg))


def test_retangulo_100x50_importa_em_mm(tmp_path):
    header = f'<svg {_XMLNS} width="100mm" height="50mm" viewBox="0 0 100 50">'
    shapes = _load(tmp_path, '<rect x="0" y="0" width="100" height="50"/>', header=header)
    assert len(shapes) == 1
    assert shapes[0].holes == ()
    bb = shapes[0].bounding_box
    assert bb.width == pytest.approx(100, abs=0.01)
    assert bb.height == pytest.approx(50, abs=0.01)


def test_letra_o_dois_circulos_concentricos_vira_furo(tmp_path):
    shapes = _load(
        tmp_path,
        '<circle cx="50" cy="50" r="20"/><circle cx="50" cy="50" r="10"/>',
    )
    assert len(shapes) == 1
    assert len(shapes[0].holes) == 1
    assert shapes[0].outer.area == pytest.approx(math.pi * 20**2, rel=0.01)
    assert shapes[0].area_liquida < shapes[0].outer.area
    assert shapes[0].area_liquida == pytest.approx(math.pi * (20**2 - 10**2), rel=0.01)


def test_letra_8_um_path_com_dois_furos(tmp_path):
    # "8" estilizado: corpo retangular + dois vaos, tudo num UNICO path
    d = "M10,10 h20 v40 h-20 Z M15,18 h10 v8 h-10 Z M15,34 h10 v8 h-10 Z"
    shapes = _load(tmp_path, f'<path d="{d}"/>')
    assert len(shapes) == 1
    assert len(shapes[0].holes) == 2
    assert shapes[0].area_liquida == pytest.approx(20 * 40 - 2 * (10 * 8), abs=0.01)


def test_transform_translate_desloca_em_mm(tmp_path):
    shapes = _load(
        tmp_path,
        '<g transform="translate(20,20)"><path d="M0,0 h10 v5 h-10 Z"/></g>',
    )
    assert len(shapes) == 1
    bb = shapes[0].bounding_box
    assert bb.min_x == pytest.approx(20, abs=0.01)
    assert bb.min_y == pytest.approx(20, abs=0.01)
    assert bb.width == pytest.approx(10, abs=0.01)
    assert bb.height == pytest.approx(5, abs=0.01)


def test_viewbox_em_cm_converte_para_mm(tmp_path):
    header = f'<svg {_XMLNS} width="10cm" height="5cm" viewBox="0 0 100 50">'
    shapes = _load(tmp_path, '<rect x="0" y="0" width="100" height="50"/>', header=header)
    bb = shapes[0].bounding_box
    assert bb.width == pytest.approx(100, abs=0.01)
    assert bb.height == pytest.approx(50, abs=0.01)


def test_eixo_y_cresce_para_baixo_como_no_resto_do_sistema(tmp_path):
    # dois retangulos: o desenhado mais ACIMA no SVG (y menor) deve sair com
    # min_y MENOR (origem topo-esquerda, sem espelhamento)
    shapes = _load(
        tmp_path,
        '<rect x="0" y="10" width="10" height="5"/><rect x="0" y="60" width="10" height="5"/>',
    )
    tops = sorted(s.bounding_box.min_y for s in shapes)
    assert tops[0] == pytest.approx(10, abs=0.01)
    assert tops[1] == pytest.approx(60, abs=0.01)


def test_linha_aberta_e_descartada_como_degenerada(tmp_path):
    shapes = _load(
        tmp_path,
        '<line x1="0" y1="0" x2="50" y2="0"/><rect x="0" y="10" width="20" height="20"/>',
    )
    assert len(shapes) == 1
    assert shapes[0].bounding_box.width == pytest.approx(20, abs=0.01)


def test_tolerancia_grosseira_gera_menos_pontos_que_fina(tmp_path):
    body = '<circle cx="50" cy="50" r="20"/>'
    fino = _load(tmp_path, body, approximation=0.01)[0]
    grosso = _load(tmp_path, body, approximation=1.0)[0]
    assert len(grosso.outer.vertices) < len(fino.outer.vertices)
    # mesmo grosseiro, a area nao pode degradar demais
    assert grosso.outer.area == pytest.approx(math.pi * 20**2, rel=0.05)


def test_arquivo_inexistente_lanca_vector_import_error(tmp_path):
    with pytest.raises(VectorImportError):
        SvgVectorImporter().load(str(tmp_path / "nao_existe.svg"))


def test_circulo_cubico_do_svg_sai_com_quatro_curvas(tmp_path):
    from app.infrastructure.importers.svg_vector_importer import SvgVectorImporter

    r, cx, cy = 50.0, 60.0, 60.0
    k = 4.0 / 3.0 * (2.0**0.5 - 1.0) * r
    d = (
        f"M {cx + r},{cy} "
        f"C {cx + r},{cy + k} {cx + k},{cy + r} {cx},{cy + r} "
        f"C {cx - k},{cy + r} {cx - r},{cy + k} {cx - r},{cy} "
        f"C {cx - r},{cy - k} {cx - k},{cy - r} {cx},{cy - r} "
        f"C {cx + k},{cy - r} {cx + r},{cy - k} {cx + r},{cy} Z"
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="120px" height="120px" '
        f'viewBox="0 0 120 120"><path d="{d}" fill="black"/></svg>'
    )
    out = tmp_path / "circulo.svg"
    out.write_text(svg, encoding="utf-8")

    shapes = SvgVectorImporter().load(str(out))

    assert len(shapes) == 1
    curvos = [s for s in shapes[0].outer.curves if not s.is_line()]
    assert len(curvos) == 4, f"esperava 4 trechos curvos, veio {len(curvos)}"


def test_retangulo_do_svg_sai_com_trechos_retos(tmp_path):
    from app.infrastructure.importers.svg_vector_importer import SvgVectorImporter

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100px" height="100px" '
        'viewBox="0 0 100 100"><path d="M 10,10 L 90,10 L 90,50 L 10,50 Z" '
        'fill="black"/></svg>'
    )
    out = tmp_path / "ret.svg"
    out.write_text(svg, encoding="utf-8")

    curves = SvgVectorImporter().load(str(out))[0].outer.curves

    assert curves
    assert all(s.is_line() for s in curves)


def test_arco_degrada_para_polilinha_sem_inventar_curva(tmp_path):
    """Arco de SVG nao tem cubica exata. Preferimos perder a curva (saida
    antiga, correta) a gravar uma aproximacao silenciosa."""
    from app.infrastructure.importers.svg_vector_importer import SvgVectorImporter

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100px" height="100px" '
        'viewBox="0 0 100 100">'
        '<path d="M 20,50 A 30,30 0 1 1 80,50 A 30,30 0 1 1 20,50 Z" fill="black"/>'
        "</svg>"
    )
    out = tmp_path / "arco.svg"
    out.write_text(svg, encoding="utf-8")

    shapes = SvgVectorImporter().load(str(out))

    assert shapes, "o arco deve continuar virando peca, so sem curva"
    assert shapes[0].outer.curves == ()
    assert len(shapes[0].outer.vertices) > 8  # achatou de verdade
