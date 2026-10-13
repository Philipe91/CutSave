"""Abertura da imagem do cliente — UMA regra para importador, preview e impressao.

Ate 13/10/2026 cada um abria a imagem do seu jeito, e os tres discordavam:

- so o importador aplicava a orientacao EXIF. Foto de celular (JPEG com
  orientation 6) entrava na chapa em pe, mas a impressao embutia o JPEG cru,
  deitado, ESTICADO para caber no retangulo em pe;
- PNG cinza de 16 bits (modo I;16) era truncado para 8 bits — todo valor acima
  de 255 saturava, e a arte saia BRANCA no preview e no PDF;
- banner acima de ~179 MP batia na trava anti-"decompression bomb" do Pillow e
  o operador via uma mensagem em ingles sobre ataque de negacao de servico.
"""

from __future__ import annotations

import warnings

import numpy as np
from PIL import Image, ImageOps

from app.shared.errors import ImageImportError

# Grafica abre banner de verdade: 3 x 1,5 m a 150 DPI sao 157 MP, acima do
# limite padrao do Pillow (89 MP avisa, 179 MP recusa). O Pillow recusa acima
# do DOBRO deste valor: 500 MP (~2 GB em RGBA) e o que ainda cabe com folga
# numa maquina de producao de 8-16 GB. Acima disso a resposta certa e baixar a
# resolucao — e a mensagem diz isso, em portugues.
LIMITE_PIXELS_AVISO = 250_000_000
Image.MAX_IMAGE_PIXELS = LIMITE_PIXELS_AVISO
# entre o aviso e a recusa e banner legitimo: sem barulho no log
warnings.simplefilter("ignore", Image.DecompressionBombWarning)

_TAG_ORIENTACAO = 0x0112
# modos inteiros de 16/32 bits que o Pillow devolve para PNG/TIFF cinza fundo
_MODOS_16_BITS = ("I;16", "I;16L", "I;16B", "I;16N", "I")


def _texto_grande_demais(path: str, pixels: int | None) -> str:
    limite = f"{2 * Image.MAX_IMAGE_PIXELS / 1e6:,.0f}".replace(",", ".")
    tamanho = (
        f"A imagem tem {pixels / 1e6:,.0f} megapixels".replace(",", ".")
        if pixels else "A imagem é grande demais"
    )
    return (
        f"{tamanho} — acima do limite de {limite} megapixels que o PrintNest "
        "abre com segurança.\n\n"
        "Reduza a resolução (150 a 300 DPI no tamanho final já é qualidade de "
        f"impressão) e importe de novo.\n\n{path}"
    )


def orientacao_exif(im: Image.Image) -> int:
    """Orientation do EXIF (1 = normal; 2..8 = espelhada e/ou girada)."""
    try:
        valor = int(im.getexif().get(_TAG_ORIENTACAO, 1) or 1)
    except Exception:
        return 1
    return valor if 1 <= valor <= 8 else 1


def para_8_bits(im: Image.Image) -> Image.Image:
    """Cinza de 16/32 bits -> 'L' de 8 bits, ESCALANDO (nao truncando).

    O convert('L'/'RGB') do Pillow satura tudo acima de 255: um PNG cinza de
    16 bits sai branco. Aqui a faixa 0..65535 vira 0..255 como o leitor faz."""
    if im.mode not in _MODOS_16_BITS:
        return im
    arr = np.asarray(im)
    if im.mode == "I" and arr.size and int(arr.max()) <= 255 and int(arr.min()) >= 0:
        escala = 1.0  # "I" que na verdade guarda 8 bits
    else:
        escala = 1.0 / 257.0
    oito = np.clip(np.rint(arr.astype(np.float32) * escala), 0, 255).astype(np.uint8)
    convertida = Image.fromarray(oito, "L")
    convertida.info.update({k: v for k, v in im.info.items() if k in ("dpi", "icc_profile")})
    return convertida


def abrir_imagem(path: str) -> Image.Image:
    """Imagem do cliente ja CARREGADA, na orientacao em que ela e vista
    (EXIF aplicado) e com cinza de 16 bits em 8 bits. Mantem dpi e icc_profile.

    Erros: ImageImportError com mensagem em portugues (arquivo ilegivel,
    grande demais, sem memoria)."""
    try:
        im = Image.open(path)
    except Image.DecompressionBombError as exc:
        raise ImageImportError(_texto_grande_demais(path, None)) from exc
    except (OSError, ValueError) as exc:
        raise ImageImportError(f"Falha ao ler a imagem: {path}") from exc
    try:
        try:
            im.load()
        except Image.DecompressionBombError as exc:
            raise ImageImportError(
                _texto_grande_demais(path, im.width * im.height)
            ) from exc
        except MemoryError as exc:
            raise ImageImportError(
                _texto_grande_demais(path, im.width * im.height)
            ) from exc
        except (OSError, ValueError) as exc:
            raise ImageImportError(f"Falha ao ler a imagem: {path}") from exc
        info = {k: v for k, v in im.info.items() if k in ("dpi", "icc_profile")}
        if orientacao_exif(im) != 1:
            girada = ImageOps.exif_transpose(im)
            for chave, valor in info.items():
                girada.info.setdefault(chave, valor)
            if girada is not im:
                im.close()
            im = girada
        return para_8_bits(im)
    except BaseException:
        im.close()
        raise
