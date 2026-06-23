from pathlib import Path

import pytest
from app.domain.model.artwork import FileFormat
from app.domain.model.image_artwork import ImageArtwork, ImageKind
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter
from app.shared.errors import ImageImportError
from tests import synth_images as si

MM_PER_PX = 25.4 / 150  # imagens sinteticas usam 150 dpi


def _imp(tmp_path):
    return Cv2ImageImporter(cache_dir=tmp_path / "cache")


def test_png_alpha_disco_classifica_e_detecta(tmp_path):
    p = si.png_alpha_disc(tmp_path)
    art = _imp(tmp_path).import_image(p).artwork
    assert isinstance(art, ImageArtwork)
    assert art.image_kind is ImageKind.IMAGE_ALPHA
    assert art.file_format is FileFormat.PNG
    # 200x100 px @150 dpi
    assert art.size.width == pytest.approx(200 * MM_PER_PX, abs=0.5)
    assert art.size.height == pytest.approx(100 * MM_PER_PX, abs=0.5)
    # disco de 80px de diametro -> ~13.5mm
    assert art.raw_contour.size.width == pytest.approx(80 * MM_PER_PX, abs=1.5)
    assert len(art.raw_contour.points) >= 8  # circulo aproximado


def test_png_com_sombra_sensibilidade_aumenta_area(tmp_path):
    p = si.png_alpha_shadow(tmp_path)
    imp = _imp(tmp_path)
    baixa = imp.import_image(p, sensitivity=5).artwork.raw_contour.size.width
    alta = imp.import_image(p, sensitivity=95).artwork.raw_contour.size.width
    # sensibilidade alta inclui o halo (sombra) -> contorno maior
    assert alta > baixa


def test_jpg_fundo_branco_recorta_area_util(tmp_path):
    p = si.jpg_white_square(tmp_path)
    art = _imp(tmp_path).import_image(p, ignore_white=True).artwork
    assert art.image_kind is ImageKind.IMAGE_OPAQUE
    # quadrado de 60px -> ~10.16mm, bem menor que a imagem (120px)
    assert art.raw_contour.size.width == pytest.approx(60 * MM_PER_PX, abs=1.5)
    assert art.raw_contour.size.width < art.size.width


def test_jpg_com_margem_branca_ignora_a_margem(tmp_path):
    p = si.jpg_white_margin(tmp_path)
    art = _imp(tmp_path).import_image(p, ignore_white=True).artwork
    bb = art.raw_contour.size
    org = art.raw_contour.origin
    assert bb.width == pytest.approx(40 * MM_PER_PX, abs=1.5)   # so o quadrado
    assert org.x == pytest.approx(80 * MM_PER_PX, abs=1.5)      # deslocado pela margem
    assert art.size.width == pytest.approx(200 * MM_PER_PX, abs=0.5)  # imagem inteira


def test_jpg_circular(tmp_path):
    p = si.jpg_circle(tmp_path)
    art = _imp(tmp_path).import_image(p).artwork
    assert art.raw_contour.size.width == pytest.approx(100 * MM_PER_PX, abs=2.0)
    assert len(art.raw_contour.points) >= 8


def test_png_irregular_triangulo(tmp_path):
    p = si.png_irregular(tmp_path)
    art = _imp(tmp_path).import_image(p).artwork
    assert art.image_kind is ImageKind.IMAGE_ALPHA
    assert 3 <= len(art.raw_contour.points) <= 8  # triangulo simplificado


def test_opaca_sem_ignorar_branco_usa_retangulo_cheio(tmp_path):
    p = si.jpg_white_square(tmp_path)
    art = _imp(tmp_path).import_image(p, ignore_white=False).artwork
    assert len(art.raw_contour.points) == 4
    assert art.raw_contour.size.width == pytest.approx(art.size.width, abs=0.5)


def test_webp_normaliza_para_png_em_cache(tmp_path):
    p = si.webp_opaque(tmp_path)
    res = _imp(tmp_path).import_image(p)
    assert res.artwork.file_format is FileFormat.WEBP
    assert res.render_path.lower().endswith(".png")
    assert res.render_path != p
    assert Path(res.render_path).exists()


def test_png_jpg_usam_o_arquivo_original_no_render(tmp_path):
    p = si.jpg_white_square(tmp_path)
    res = _imp(tmp_path).import_image(p)
    assert Path(res.render_path) == Path(p).resolve()


def test_cache_reaproveita_decodificacao(tmp_path):
    p = si.png_alpha_disc(tmp_path)
    imp = _imp(tmp_path)
    imp.import_image(p, sensitivity=20)
    imp.import_image(p, sensitivity=80)
    assert len(imp._decoded) == 1  # decodificou uma unica vez


def test_dpi_lido_da_imagem(tmp_path):
    p = si.png_alpha_disc(tmp_path, dpi=300)
    art = _imp(tmp_path).import_image(p).artwork
    assert art.dpi == pytest.approx(300, abs=1)


def test_imagem_grande_reduz_para_deteccao(tmp_path):
    # > MAX_DETECT_SIDE: exercita o downscale antes do findContours
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (1400, 900), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([300, 200, 1100, 700], fill=(200, 30, 30, 255))
    p = str(tmp_path / "grande.png")
    im.save(p, dpi=(150, 150))
    art = _imp(tmp_path).import_image(p).artwork
    assert art.size.width == pytest.approx(1400 * MM_PER_PX, abs=0.5)
    # elipse ~800px de largura -> ~135mm, detectada mesmo apos reducao
    assert art.raw_contour.size.width == pytest.approx(800 * MM_PER_PX, abs=6)


def test_imagem_totalmente_transparente_usa_retangulo_cheio(tmp_path):
    from PIL import Image
    p = str(tmp_path / "vazia.png")
    Image.new("RGBA", (100, 60), (0, 0, 0, 0)).save(p, dpi=(150, 150))
    art = _imp(tmp_path).import_image(p).artwork
    assert len(art.raw_contour.points) == 4  # sem conteudo -> faca = limites da imagem
    assert art.raw_contour.size.width == pytest.approx(art.size.width, abs=0.5)


def test_png_sem_dpi_usa_padrao(tmp_path):
    from PIL import Image
    p = str(tmp_path / "semdpi.png")
    Image.new("RGBA", (96, 96), (10, 10, 10, 255)).save(p)  # sem dpi
    art = _imp(tmp_path).import_image(p).artwork
    assert art.dpi == 96.0


def test_webp_render_path_reutiliza_cache(tmp_path):
    p = si.webp_opaque(tmp_path)
    imp = _imp(tmp_path)
    a = imp.import_image(p).render_path
    b = imp.import_image(p).render_path
    assert a == b and Path(a).exists()


def test_formato_nao_suportado_levanta(tmp_path):
    with pytest.raises(ImageImportError):
        _imp(tmp_path).import_image(str(tmp_path / "x.gif"))


def test_pdf_nao_e_imagem(tmp_path):
    with pytest.raises(ImageImportError):
        _imp(tmp_path).import_image(str(tmp_path / "x.pdf"))
