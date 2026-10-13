"""Imagem do cliente: orientacao EXIF, PNG 16 bits, imagem gigante (13/10/2026).

O importador, o preview e a impressao abriam a imagem cada um do seu jeito:

- foto de celular (JPEG com EXIF orientation 6) entrava na chapa com o tamanho
  em pe, mas a impressao embutia o JPEG cru deitado e ESTICADO para caber;
- PNG cinza de 16 bits (modo I;16) virava branco puro no preview e no PDF;
- banner acima de 179 MP estourava com mensagem do Pillow em ingles, e uma
  imagem de 40 MP alocava mais de 2 GB so para achar o contorno.
"""

from __future__ import annotations

import tracemalloc

import numpy as np
import PIL.Image
import pypdfium2 as pdfium
import pytest
from app.infrastructure.exporters.pdf_writer import PdfWriter
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer
from app.shared.errors import ImageImportError
from PIL import Image

VERMELHO = np.array([255, 0, 0])
AZUL = np.array([0, 0, 255])


def _perto(px, cor, tol=60) -> bool:
    return bool(np.all(np.abs(np.asarray(px[:3], int) - cor) < tol))


def _jpeg_exif6(path):
    """Gravado 200x100 deitado (esquerda vermelha, direita azul) com EXIF 6:
    o leitor mostra 100x200 em pe, VERMELHO EM CIMA e azul embaixo."""
    a = np.zeros((100, 200, 3), np.uint8)
    a[:, :100] = (255, 0, 0)
    a[:, 100:] = (0, 0, 255)
    ex = Image.Exif()
    ex[0x0112] = 6
    Image.fromarray(a).save(path, exif=ex, dpi=(72, 72), quality=95)
    return str(path)


def _render_writer(path, w_mm, h_mm) -> np.ndarray:
    w = PdfWriter()
    try:
        w.new_page(w_mm, h_mm)
        w.place_image(path, 0, 0, w_mm, h_mm)
        data = w.save_bytes()
    finally:
        w.close()
    doc = pdfium.PdfDocument(data)
    try:
        return np.array(doc[0].render(scale=1).to_pil().convert("RGB"))
    finally:
        doc.close()


def test_exif_orientacao_importa_preview_e_imprime_em_pe(tmp_path):
    src = _jpeg_exif6(tmp_path / "foto.jpg")
    art = Cv2ImageImporter().import_image(src).artwork
    assert art.size.height > art.size.width  # em pe

    data, w, h = PdfiumPageRenderer().render_raw(src, dpi=72)
    assert (w, h) == (100, 200)
    prev = np.frombuffer(data, np.uint8).reshape(h, w, 4)
    assert _perto(prev[20, 50], VERMELHO) and _perto(prev[180, 50], AZUL)

    out = _render_writer(src, art.size.width, art.size.height)
    alto, largo = out.shape[:2]
    assert _perto(out[alto // 10, largo // 2], VERMELHO)
    assert _perto(out[alto * 9 // 10, largo // 2], AZUL)


def test_exif_orientacao_mantem_o_perfil_icc(tmp_path):
    from PIL import ImageCms

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    a = np.zeros((40, 80, 3), np.uint8)
    ex = Image.Exif()
    ex[0x0112] = 6
    src = tmp_path / "icc.jpg"
    Image.fromarray(a).save(src, exif=ex, icc_profile=icc, quality=95)
    w = PdfWriter()
    try:
        xo = w._image_xobject(str(src))
        assert int(xo.Width) == 40 and int(xo.Height) == 80
        cs = xo.ColorSpace
        assert str(cs[0]) == "/ICCBased"
    finally:
        w.close()


def _png16(path):
    g = np.full((100, 100), 65535, np.uint16)  # branco
    # metade esquerda cinza ESCURO (~12%): truncar 16->8 bits satura em 255
    g[:, :50] = 8192
    Image.fromarray(g).save(path)
    return str(path)


def test_png_cinza_16_bits_nao_vira_branco(tmp_path):
    src = _png16(tmp_path / "g16.png")
    rgba = Cv2ImageImporter()._decode(src)
    assert 20 < rgba[50, 10, 0] < 45 and rgba[50, 90, 0] > 225

    data, w, h = PdfiumPageRenderer().render_raw(src, dpi=72)
    prev = np.frombuffer(data, np.uint8).reshape(h, w, 4)
    assert 20 < prev[50, 10, 0] < 45 and prev[50, 90, 0] > 225

    out = _render_writer(src, 100 * 25.4 / 72, 100 * 25.4 / 72)
    alto, largo = out.shape[:2]
    assert 20 < out[alto // 2, largo // 10, 0] < 45
    assert out[alto // 2, largo * 9 // 10, 0] > 225


def test_imagem_acima_do_limite_da_erro_claro_em_portugues(tmp_path, monkeypatch):
    src = tmp_path / "banner.png"
    Image.new("L", (100, 100), 255).save(src)
    # limite reduzido so neste teste: o arquivo de 10.000 px vira "gigante"
    monkeypatch.setattr(PIL.Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(ImageImportError) as exc:
        Cv2ImageImporter().import_image(str(src))
    assert "megapixels" in str(exc.value)
    assert "decompression" not in str(exc.value).lower()


def test_limite_de_pixels_cobre_banner_de_grafica():
    import app.infrastructure.imagem  # noqa: F401  (ajusta o limite global)

    # 3 x 1,5 m a 150 DPI = 157 MP: abre sem erro
    assert PIL.Image.MAX_IMAGE_PIXELS * 2 >= 3000 / 25.4 * 150 * 1500 / 25.4 * 150


def test_contorno_de_imagem_grande_nao_aloca_gigas():
    rgba = np.full((5000, 8000, 4), 255, np.uint8)
    rgba[1000:4000, 1000:7000, :3] = 30
    tracemalloc.start()
    try:
        contornos = Cv2ImageImporter().detect_contours(rgba, 200)
        _cur, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert contornos
    assert pico < 150_000_000, f"pico de {pico / 1e6:.0f} MB na deteccao"
    # o retangulo escuro continua no lugar (1 px de deteccao = 0,64 mm aqui)
    xs = [p.x for p in contornos[0].points]
    assert min(xs) == pytest.approx(1000 / 200 * 25.4, abs=1.0)
    assert max(xs) == pytest.approx(7000 / 200 * 25.4, abs=1.0)


def test_cache_de_imagens_decodificadas_e_limitado(tmp_path):
    imp = Cv2ImageImporter(cache_dir=tmp_path / "cache")
    for i in range(10):
        p = tmp_path / f"a{i}.png"
        Image.new("RGB", (20, 20), (i, 0, 0)).save(p)
        imp.import_image(str(p))
    assert len(imp._decoded) <= 4
