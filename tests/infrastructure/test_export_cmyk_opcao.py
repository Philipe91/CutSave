"""Opcao RGB/CMYK na exportacao em imagem (estilo Corel).

O pdfium so rasteriza em RGB, entao a imagem NUNCA devolve o CMYK original
byte a byte — para isso existe a exportacao em PDF. O que esta opcao faz e
tirar a conversao do chute do RIP: quem escolhe o perfil de destino e o
operador, e o perfil vai EMBUTIDO no arquivo.
"""

import pytest
from PIL import Image

from app.application.dto.print_placement import PrintPlacement, PrintSheet
from app.domain.geometry import Point2D, Size
from app.infrastructure.color_profiles import (
    caminho_do_perfil_padrao,
    descricao_do_perfil,
    perfis_cmyk_do_sistema,
)
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter


def _folha(tmp_path):
    src = tmp_path / "arte.png"
    Image.new("RGB", (60, 30), (0, 174, 239)).save(src)  # ciano de quadricromia
    return PrintSheet(
        (PrintPlacement(str(src), 0, Point2D(0, 0), Size(60, 30)),), Size(60, 30)
    )


# ---- perfis instalados na maquina ----

def test_acha_algum_perfil_cmyk_no_sistema():
    """O Windows ja traz o RSWOP (U.S. Web Coated): a lista nunca vem vazia."""
    perfis = perfis_cmyk_do_sistema()
    assert perfis, "nenhum perfil CMYK encontrado no sistema"
    assert all(p.caminho.lower().endswith((".icc", ".icm")) for p in perfis)
    assert all(p.nome for p in perfis)


def test_perfil_padrao_existe_e_e_cmyk():
    padrao = caminho_do_perfil_padrao()
    assert padrao is not None
    assert descricao_do_perfil(padrao) is not None


def test_perfil_rgb_nao_entra_na_lista_de_cmyk():
    """sRGB esta na mesma pasta e nao pode aparecer como destino CMYK."""
    nomes = " ".join(p.nome.lower() for p in perfis_cmyk_do_sistema())
    assert "srgb" not in nomes


# ---- conversao na exportacao ----

def test_jpeg_cmyk_sai_em_quatro_canais(tmp_path):
    alvo = str(tmp_path / "chapa.jpg")
    (gerado,) = PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], alvo, dpi=72, image_format="jpeg", color_space="cmyk"
    )
    with Image.open(gerado) as im:
        assert im.mode == "CMYK", f"exportou em {im.mode}, nao em CMYK"


def test_jpeg_cmyk_leva_o_perfil_embutido(tmp_path):
    """Sem perfil embutido o RIP volta a adivinhar — que e o bug de origem."""
    alvo = str(tmp_path / "chapa.jpg")
    (gerado,) = PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], alvo, dpi=72, image_format="jpeg", color_space="cmyk"
    )
    with Image.open(gerado) as im:
        assert im.info.get("icc_profile"), "JPEG CMYK saiu sem perfil embutido"


def test_cmyk_converte_ciano_em_tinta_ciano(tmp_path):
    """A conversao tem que ser gerenciada: ciano vira tinta CIANO dominante,
    nao uma mistura qualquer das quatro."""
    alvo = str(tmp_path / "chapa.jpg")
    (gerado,) = PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], alvo, dpi=72, image_format="jpeg", color_space="cmyk"
    )
    with Image.open(gerado) as im:
        c, m, y, k = im.getpixel((im.width // 2, im.height // 2))
    assert c > 150, f"ciano perdeu a tinta ciano: C={c}"
    assert m < 80 and y < 80, f"ciano ganhou tinta demais: M={m} Y={y}"


def test_png_nunca_vira_cmyk(tmp_path):
    """PNG nao guarda CMYK (limite do formato): pedir CMYK sai em RGB, e o
    arquivo tem que sair — nao e motivo para recusar a exportacao."""
    alvo = str(tmp_path / "chapa.png")
    (gerado,) = PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], alvo, dpi=72, image_format="png", color_space="cmyk"
    )
    with Image.open(gerado) as im:
        assert im.mode == "RGB"


def test_rgb_continua_o_padrao(tmp_path):
    """Sem pedir nada, nada muda: quem ja exportava segue igual."""
    alvo = str(tmp_path / "chapa.jpg")
    (gerado,) = PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], alvo, dpi=72, image_format="jpeg"
    )
    with Image.open(gerado) as im:
        assert im.mode == "RGB"


def test_qualidade_jpeg_muda_o_tamanho_do_arquivo(tmp_path):
    """Controle de qualidade do Corel: 40 tem que gerar arquivo menor que 95."""
    import os
    folha = _folha(tmp_path)
    tamanhos = {}
    for q in (40, 95):
        alvo = str(tmp_path / f"q{q}.jpg")
        (gerado,) = PikePdfPrintExporter().export_image(
            [folha], alvo, dpi=200, image_format="jpeg", quality=q
        )
        tamanhos[q] = os.path.getsize(gerado)
    assert tamanhos[40] < tamanhos[95]


def test_perfil_escolhido_pelo_operador_e_o_usado(tmp_path):
    """Quem aponta o .icc da propria grafica tem que ver ESSE perfil no
    arquivo, nao o padrao do sistema."""
    escolhido = caminho_do_perfil_padrao()
    alvo = str(tmp_path / "chapa.jpg")
    (gerado,) = PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], alvo, dpi=72, image_format="jpeg",
        color_space="cmyk", icc_path=escolhido,
    )
    with Image.open(gerado) as im:
        embutido = im.info.get("icc_profile")
    from PIL import ImageCms
    import io
    lido = ImageCms.getOpenProfile(io.BytesIO(embutido)).profile.profile_description
    assert lido == descricao_do_perfil(escolhido)


def test_perfil_invalido_nao_derruba_a_exportacao(tmp_path):
    """Arquivo do cliente e sagrado: perfil quebrado exporta em RGB, sem
    explodir na cara de quem so queria a chapa."""
    ruim = tmp_path / "quebrado.icc"
    ruim.write_bytes(b"isso nao e um perfil")
    alvo = str(tmp_path / "chapa.jpg")
    (gerado,) = PikePdfPrintExporter().export_image(
        [_folha(tmp_path)], alvo, dpi=72, image_format="jpeg",
        color_space="cmyk", icc_path=str(ruim),
    )
    with Image.open(gerado) as im:
        assert im.mode in ("RGB", "CMYK")
