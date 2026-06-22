from app.application.dto.pdf_report import PdfDocumentReport, PdfPageReport
from app.domain.geometry import Size


def _page(index, vectors, rasters):
    return PdfPageReport(
        index=index,
        size_mm=Size(210, 297),
        width_pt=595.0,
        height_pt=842.0,
        vector_drawings=vectors,
        raster_images=rasters,
    )


def test_page_has_vector_e_has_raster():
    p = _page(0, vectors=3, rasters=0)
    assert p.has_vector is True
    assert p.has_raster is False


def test_document_agrega_vetor_e_raster():
    doc = PdfDocumentReport(
        path="x.pdf",
        page_count=2,
        pages=[_page(0, 2, 0), _page(1, 0, 1)],
    )
    assert doc.has_vector is True
    assert doc.has_raster is True


def test_document_sem_conteudo():
    doc = PdfDocumentReport(path="x.pdf", page_count=1, pages=[_page(0, 0, 0)])
    assert doc.has_vector is False
    assert doc.has_raster is False


def test_pages_convertido_para_tupla():
    doc = PdfDocumentReport(path="x.pdf", page_count=1, pages=[_page(0, 1, 1)])
    assert isinstance(doc.pages, tuple)
