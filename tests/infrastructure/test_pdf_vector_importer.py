import math

import fitz
import pytest
from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter
from app.shared.errors import VectorImportError

PT2MM = 25.4 / 72.0


def _save(tmp_path, doc):
    path = tmp_path / "fixture.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_retangulo_100x50pt_importa_em_mm(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_rect(fitz.Rect(50, 100, 150, 150), color=(0, 0, 0), fill=(0, 0, 0))
    shapes = PdfVectorImporter().load(_save(tmp_path, doc))
    assert len(shapes) == 1
    assert shapes[0].holes == ()
    bb = shapes[0].bounding_box
    assert bb.width == pytest.approx(100 * PT2MM, abs=0.01)
    assert bb.height == pytest.approx(50 * PT2MM, abs=0.01)


def test_letra_o_num_unico_path_object_vira_furo(tmp_path):
    # Dois circulos concentricos no MESMO objeto de path (subpaths): com a
    # logica antiga de subpaths fundidos o furo sumiria — o teste central da 3B.
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    shape = page.new_shape()
    shape.draw_circle(fitz.Point(200, 200), 80)
    shape.draw_circle(fitz.Point(200, 200), 40)
    shape.finish(fill=(0, 0, 0))
    shape.commit()
    shapes = PdfVectorImporter().load(_save(tmp_path, doc))
    assert len(shapes) == 1
    assert len(shapes[0].holes) == 1
    r_out, r_in = 80 * PT2MM, 40 * PT2MM
    assert shapes[0].outer.area == pytest.approx(math.pi * r_out**2, rel=0.01)
    assert shapes[0].area_liquida == pytest.approx(math.pi * (r_out**2 - r_in**2), rel=0.01)


def test_dois_objetos_separados_tambem_viram_furo(tmp_path):
    # Mesma letra "O", mas cada circulo num objeto proprio: group_rings resolve.
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_circle(fitz.Point(200, 200), 80, color=(0, 0, 0), fill=(0, 0, 0))
    page.draw_circle(fitz.Point(200, 200), 40, color=(0, 0, 0), fill=(0, 0, 0))
    shapes = PdfVectorImporter().load(_save(tmp_path, doc))
    assert len(shapes) == 1
    assert len(shapes[0].holes) == 1
    r_out, r_in = 80 * PT2MM, 40 * PT2MM
    assert shapes[0].area_liquida == pytest.approx(math.pi * (r_out**2 - r_in**2), rel=0.01)


def test_flip_y_retangulo_no_topo_da_pagina_sai_com_y_min_pequeno(tmp_path):
    # fitz desenha em coords topo-esquerda; o PDF salva em baixo-esquerda.
    # Depois do flip, o retangulo perto do TOPO tem de voltar com y_min pequeno.
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_rect(fitz.Rect(10, 10, 60, 30), color=(0, 0, 0), fill=(0, 0, 0))
    shapes = PdfVectorImporter().load(_save(tmp_path, doc))
    assert len(shapes) == 1
    bb = shapes[0].bounding_box
    assert bb.min_y == pytest.approx(10 * PT2MM, abs=0.01)
    assert bb.min_x == pytest.approx(10 * PT2MM, abs=0.01)


def test_tolerancia_grosseira_gera_menos_pontos_que_fina(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_circle(fitz.Point(200, 200), 100, color=(0, 0, 0), fill=(0, 0, 0))
    path = _save(tmp_path, doc)
    fino = PdfVectorImporter(approximation=0.01).load(path)[0]
    grosso = PdfVectorImporter(approximation=1.0).load(path)[0]
    assert len(grosso.outer.vertices) < len(fino.outer.vertices)
    r_mm = 100 * PT2MM
    assert grosso.outer.area == pytest.approx(math.pi * r_mm**2, rel=0.05)
    assert fino.outer.area == pytest.approx(math.pi * r_mm**2, rel=0.05)


def test_pagina_so_com_texto_retorna_lista_vazia(tmp_path):
    # Texto nao e path: precisa vir convertido em curvas (texto digitado e a 3C).
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text(fitz.Point(50, 50), "PrintNest")
    assert PdfVectorImporter().load(_save(tmp_path, doc)) == []


def test_arquivo_inexistente_lanca_vector_import_error(tmp_path):
    with pytest.raises(VectorImportError):
        PdfVectorImporter().load(str(tmp_path / "nao_existe.pdf"))
