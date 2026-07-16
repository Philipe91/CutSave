import fitz
from app.domain.cut.vector import is_knife_color
from app.infrastructure.importers.pdfium_vector_extractor import PdfiumVectorExtractor
from app.infrastructure.pdfium_knife import knife_free_pdf


def _arte_com_faca(tmp_path, name="cliente.pdf"):
    doc = fitz.open()
    page = doc.new_page(width=267, height=101)
    page.draw_rect(fitz.Rect(15, 15, 250, 88), color=None, fill=(0.2, 0.4, 1))  # arte
    page.draw_rect(fitz.Rect(8, 8, 259, 93), color=(1, 0, 1), width=1.0)        # faca
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


def _tem_magenta(path):
    infos = PdfiumVectorExtractor().extract_rings_info(path)
    return any(
        i.stroked and i.stroke_rgb is not None and is_knife_color(i.stroke_rgb)
        for i in infos
    )


def test_copia_limpa_remove_o_magenta_e_preserva_a_arte(tmp_path):
    src = _arte_com_faca(tmp_path)
    clean = knife_free_pdf(src)
    assert clean != src                      # gerou cópia
    assert _tem_magenta(src)                 # original intacto
    assert not _tem_magenta(clean)           # cópia sem a linha de faca
    infos = PdfiumVectorExtractor().extract_rings_info(clean)
    assert len(infos) >= 1                   # a arte continua lá
    # cache: mesma chamada devolve o mesmo arquivo (não recria)
    assert knife_free_pdf(src) == clean


def test_render_da_copia_limpa_preserva_as_cores(tmp_path):
    # Regressão 16/07: a 1ª versão do strip (FPDFPage_GenerateContent, do
    # pdfium) reescrevia a página inteira e a ARTE RENDERIZAVA PRETA no
    # programa. O filtro pikepdf só tira o traço magenta — cores intactas.
    import io

    from PIL import Image

    from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer

    src = _arte_com_faca(tmp_path)
    png = PdfiumPageRenderer().render_png(src, 0, dpi=72)  # usa a cópia limpa
    img = Image.open(io.BytesIO(png)).convert("RGB")
    w, h = img.size
    r, g, b = img.getpixel((w // 2, h // 2))  # centro: arte azul (0.2, 0.4, 1)
    assert b > 150 and r < 120, f"arte deveria ser azul, veio rgb=({r},{g},{b})"
    edge = img.getpixel((8, h // 2))          # x=8pt: onde passava a linha da faca
    assert not is_knife_color(edge), f"linha magenta ainda renderiza: {edge}"


def test_pdf_sem_magenta_usa_o_original(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.draw_rect(fitz.Rect(10, 10, 90, 90), color=None, fill=(0, 0, 0))
    src = tmp_path / "soarte.pdf"
    doc.save(str(src))
    doc.close()
    assert knife_free_pdf(str(src)) == str(src)


def test_arquivo_nao_pdf_ou_inexistente_passa_direto(tmp_path):
    assert knife_free_pdf(str(tmp_path / "x.png")) == str(tmp_path / "x.png")
    assert knife_free_pdf(str(tmp_path / "nao-existe.pdf")) == str(tmp_path / "nao-existe.pdf")
