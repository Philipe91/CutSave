import fitz
import pytest
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer
from app.shared.errors import PdfImportError


def _pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    path = tmp_path / "x.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_render_retorna_png(tmp_path):
    data = PdfiumPageRenderer().render_png(_pdf(tmp_path))
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # assinatura PNG


def test_apara_recorta_no_trimbox(tmp_path):
    # pagina 200x100 com TrimBox menor (50,25..150,75) -> 100x50
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
    doc.xref_set_key(page.xref, "TrimBox", "[50 25 150 75]")
    path = tmp_path / "trim.pdf"
    doc.save(str(path))
    doc.close()

    renderer = PdfiumPageRenderer()
    media_png = renderer.render_png(str(path), box="media")
    trim_png = renderer.render_png(str(path), box="trim")
    # a renderizacao da apara e menor (so o miolo do TrimBox)
    media_img = fitz.open("png", media_png)[0].rect
    trim_img = fitz.open("png", trim_png)[0].rect
    assert trim_img.width < media_img.width
    assert trim_img.height < media_img.height


def test_arquivo_inexistente_falha(tmp_path):
    with pytest.raises(PdfImportError):
        PdfiumPageRenderer().render_png(str(tmp_path / "nao_existe.pdf"))


def _pdf_com_faca(tmp_path, n_pages=4):
    """PDF de varias paginas com um contorno MAGENTA (a faca do cliente)."""
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page(width=200, height=100)
        page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 0), fill=(0, 0, 0))
        page.draw_circle((60 + i * 10, 50), 20, color=(0, 1, 0), fill=(0, 1, 0))
        page.draw_rect(fitz.Rect(5, 5, 195, 95), color=(1, 0, 1))  # faca magenta
    path = tmp_path / "faca.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.mark.parametrize("box", ["media", "trim", "auto"])
def test_render_raw_e_o_mesmo_pixel_do_png(tmp_path, box):
    # render_raw existe para o preview NAO pagar codificar+decodificar PNG
    # (eram 25 dos 29s de janela travada num PDF de 60 paginas). O atalho so
    # vale se a imagem sair identica a do caminho antigo.
    import io

    from PIL import Image

    src = _pdf_com_faca(tmp_path)
    renderer = PdfiumPageRenderer()
    png = Image.open(io.BytesIO(renderer.render_png(src, 1, box=box))).convert("RGBA")
    data, w, h = renderer.render_raw(src, 1, box=box)
    assert (w, h) == png.size
    assert data == png.tobytes()


def test_only_page_limpa_a_faca_igual_ao_documento_inteiro(tmp_path):
    # only_page limpa o magenta de UMA pagina em vez do documento todo (soltar
    # um PDF de 60 paginas na biblioteca travava 4,3s so pela miniatura). O
    # resultado tem de ser o MESMO pixel do strip do documento inteiro, e a
    # pagina certa — a copia de uma pagina so reindexa para 0.
    from app.infrastructure import pdfium_knife

    src = _pdf_com_faca(tmp_path)
    renderer = PdfiumPageRenderer()
    for page in range(4):
        pdfium_knife._cache.clear()
        pdfium_knife._page_cache.clear()
        inteiro = renderer.render_png(src, page)
        pdfium_knife._cache.clear()
        pdfium_knife._page_cache.clear()
        so_uma = renderer.render_png(src, page, only_page=True)
        assert so_uma == inteiro, f"pagina {page} divergiu"


def test_only_page_reaproveita_a_copia_inteira_quando_ja_existe(tmp_path):
    # com a copia limpa do documento ja em cache, only_page devolve ELA com a
    # numeracao original (nao paga um strip de pagina a toa)
    from app.infrastructure import pdfium_knife

    src = _pdf_com_faca(tmp_path)
    pdfium_knife._cache.clear()
    pdfium_knife._page_cache.clear()
    inteiro = pdfium_knife.knife_free_pdf(src)
    assert inteiro != src  # havia magenta para tirar
    assert pdfium_knife.knife_free_page(src, 2) == (inteiro, 2)
    assert pdfium_knife._page_cache == {}  # nem chegou a gerar copia de pagina


def test_sem_faca_o_render_usa_o_original(tmp_path):
    # PDF sem magenta nenhum: nada a limpar, os dois caminhos devolvem o
    # proprio arquivo (sem copia em disco)
    from app.infrastructure import pdfium_knife

    src = _pdf(tmp_path)
    pdfium_knife._cache.clear()
    pdfium_knife._page_cache.clear()
    assert pdfium_knife.knife_free_pdf(src) == src
    pdfium_knife._cache.clear()
    assert pdfium_knife.knife_free_page(src, 0) == (src, 0)


@pytest.mark.parametrize("box", ["media", "trim", "auto"])
def test_render_imagem_em_qualquer_caixa_nao_quebra(tmp_path, box):
    # imagem (nao-PDF) com box de apara NAO pode acessar page.xref (falha nativa):
    # box_clip_rect deve devolver a pagina inteira. Regressao do crash em producao.
    from PIL import Image
    p = tmp_path / "img.png"
    Image.new("RGBA", (120, 80), (10, 10, 10, 255)).save(p, dpi=(150, 150))
    data = PdfiumPageRenderer().render_png(str(p), box=box)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_raw_de_imagem_nao_quebra(tmp_path):
    # o caminho de IMAGEM (nao-PDF) tambem tem de servir o preview sem PNG
    from PIL import Image

    p = tmp_path / "img.png"
    Image.new("RGBA", (120, 80), (10, 20, 30, 255)).save(p, dpi=(72, 72))
    # dpi=72 -> escala 1:1 (imagem sai reescalada por dpi/72, como o motor antigo)
    data, w, h = PdfiumPageRenderer().render_raw(str(p), dpi=72)
    assert (w, h) == (120, 80)
    assert len(data) == 120 * 80 * 4
