import fitz
import pytest
from app.domain.model.artwork import ArtKind, FileFormat
from app.infrastructure.importers.pymupdf_importer import PyMuPdfImporter, classify_kind
from app.shared.errors import PdfImportError

PT2MM = 25.4 / 72.0


def _vec_page(doc, w=600.0, h=400.0, n_rects=3):
    page = doc.new_page(width=w, height=h)
    for i in range(n_rects):
        page.draw_rect(fitz.Rect(10 + i * 5, 10, 100 + i * 5, 100), color=(0, 0, 0))
    return page


def _save(doc, tmp_path, name="t.pdf"):
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


# --- Classificacao (funcao pura) ---

def test_classify_vetorial():
    assert classify_kind(drawings=5, images=0) is ArtKind.VETORIAL


def test_classify_raster():
    assert classify_kind(drawings=1, images=1) is ArtKind.RASTER


def test_classify_retangular():
    assert classify_kind(drawings=0, images=0) is ArtKind.RETANGULAR


def test_classify_vetor_precede_raster():
    assert classify_kind(drawings=8, images=3) is ArtKind.VETORIAL


# --- Importacao ---

def test_multipagina_gera_multiplas_artworks(tmp_path):
    doc = fitz.open()
    _vec_page(doc)
    _vec_page(doc)
    _vec_page(doc)
    arts = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))
    assert len(arts) == 3
    assert all(a.file_format is FileFormat.PDF for a in arts)
    assert len({a.id for a in arts}) == 3  # ids independentes


def test_dimensao_mediabox(tmp_path):
    doc = fitz.open()
    _vec_page(doc, 600, 400)
    art = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))[0]
    assert art.size.width == pytest.approx(600 * PT2MM, abs=0.1)
    assert art.size.height == pytest.approx(400 * PT2MM, abs=0.1)


def test_prioridade_trimbox(tmp_path):
    doc = fitz.open()
    page = _vec_page(doc, 600, 400)
    doc.xref_set_key(page.xref, "TrimBox", "[50 50 350 250]")  # 300 x 200
    art = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))[0]
    assert art.size.width == pytest.approx(300 * PT2MM, abs=0.1)
    assert art.size.height == pytest.approx(200 * PT2MM, abs=0.1)


def test_fallback_cropbox(tmp_path):
    doc = fitz.open()
    page = _vec_page(doc, 600, 400)
    doc.xref_set_key(page.xref, "CropBox", "[0 0 300 400]")  # sem TrimBox
    art = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))[0]
    assert art.size.width == pytest.approx(300 * PT2MM, abs=0.1)


def test_rotacao_90_troca_dimensoes(tmp_path):
    doc = fitz.open()
    page = _vec_page(doc, 600, 400)
    page.set_rotation(90)
    art = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))[0]
    assert art.size.width == pytest.approx(400 * PT2MM, abs=0.1)
    assert art.size.height == pytest.approx(600 * PT2MM, abs=0.1)


def test_rotacao_180_mantem_dimensoes(tmp_path):
    doc = fitz.open()
    page = _vec_page(doc, 600, 400)
    page.set_rotation(180)
    art = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))[0]
    assert art.size.width == pytest.approx(600 * PT2MM, abs=0.1)


def test_trimbox_malformada_cai_para_proxima_box(tmp_path):
    doc = fitz.open()
    page = _vec_page(doc, 600, 400)
    doc.xref_set_key(page.xref, "TrimBox", "[a b c d]")  # invalido -> ignora
    art = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))[0]
    assert art.size.width == pytest.approx(600 * PT2MM, abs=0.1)  # usou MediaBox


def test_trimbox_incompleta_cai_para_proxima_box(tmp_path):
    doc = fitz.open()
    page = _vec_page(doc, 600, 400)
    doc.xref_set_key(page.xref, "TrimBox", "[0 0 100]")  # 3 numeros -> ignora
    art = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))[0]
    assert art.size.width == pytest.approx(600 * PT2MM, abs=0.1)


def test_pdf_vetorial_classifica_vetorial(tmp_path):
    doc = fitz.open()
    _vec_page(doc, n_rects=5)
    art = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))[0]
    assert art.kind is ArtKind.VETORIAL


def test_pdf_rasterizado_classifica_raster(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 16, 16), 0)
    pix.clear_with(100)
    page.insert_image(fitz.Rect(0, 0, 400, 300), pixmap=pix)
    art = PyMuPdfImporter().import_artworks(_save(doc, tmp_path))[0]
    assert art.kind is ArtKind.RASTER


def test_arquivo_invalido_levanta_erro(tmp_path):
    bad = tmp_path / "x.pdf"
    bad.write_text("isto nao e um pdf", encoding="utf-8")
    with pytest.raises(PdfImportError):
        PyMuPdfImporter().import_artworks(str(bad))


def test_arquivo_inexistente_levanta_erro(tmp_path):
    with pytest.raises(PdfImportError):
        PyMuPdfImporter().import_artworks(str(tmp_path / "nao_existe.pdf"))


def test_arquivo_imagem_nao_e_pdf(tmp_path):
    img = tmp_path / "a.png"
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), 0)
    pix.clear_with(0)
    pix.save(str(img))
    with pytest.raises(PdfImportError):
        PyMuPdfImporter().import_artworks(str(img))
