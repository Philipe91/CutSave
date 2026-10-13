from __future__ import annotations

import hashlib
import math
import tempfile
from collections import OrderedDict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.application.ports.image_importer import IImageImporter, ImportedImage
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.image_artwork import ImageArtwork, ImageKind
from app.infrastructure.imagem import abrir_imagem
from app.shared.errors import ImageImportError

MM_PER_INCH = 25.4
DEFAULT_DPI = 96.0
# Lado maximo (px) da mascara antes do findContours: limita o custo em imagens
# grandes. 1600 (era 1000): mascara mais fina = curva mais fiel ao desenho.
MAX_DETECT_SIDE = 1600
# Imagens PEQUENAS (adesivo em baixa resolucao): amplia a mascara com
# interpolacao antes do contorno — precisao SUB-PIXEL, a curva para de seguir
# os degraus dos pixels (faca "reta demais" em circulos pequenos).
MIN_DETECT_SIDE = 900
UPSCALE_MAX = 6.0
# Tolerancia de simplificacao do contorno (mm): remove pontos redundantes.
# 0.12 (era 0.3): cordas curtas preservam a CURVA na origem — a suavizacao e a
# reducao de nos (Fino/Medio/Leve) atuam depois e controlam a contagem final.
SIMPLIFY_MM = 0.12
# Alpha minimo (0-255) para considerar um pixel opaco ao classificar a imagem.
_ALPHA_OPAQUE = 250
# Multi-desenho: area MINIMA (em mm^2) para um contorno contar como um desenho
# separado. Absoluto (nao fracao da imagem): pega elementos pequenos reais
# (ex.: uma estrelinha ~4x4mm) mas ignora respingos/ruido, seja qual for o
# tamanho da imagem. ~9mm^2 = um quadradinho de 3x3mm. E teto de desenhos.
MIN_DESIGN_MM2 = 9.0
MAX_DESIGNS = 400
# Quantas imagens decodificadas ficam em memoria (LRU). O cache existe para
# mexer na sensibilidade sem reler o disco — da MESMA imagem. Sem teto, uma
# sessao com dezenas de fotos de 40 MP guardava 160 MB de RGBA por foto ate
# fechar o programa (auditoria de 13/10/2026).
MAX_DECODED_CACHE = 4


class Cv2ImageImporter(IImageImporter):
    """Importa PNG/JPG/WEBP com PyMuPDF-livre: Pillow decodifica, numpy faz a
    mascara, OpenCV tira o contorno externo. Faca rapida e confiavel (sem IA).

    Cache em memoria do array decodificado (por caminho/mtime/tamanho) para que
    mudar a sensibilidade re-detecte sem reler o disco. WEBP e normalizado para
    um PNG em cache, pois o fitz (render/impressao) nao abre WEBP.
    """

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self._cache_dir = (
            Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "printnest_img_cache"
        )
        self._decoded: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._render_paths: dict[tuple, str] = {}

    def import_image(
        self,
        path: str,
        *,
        sensitivity: float = 50.0,
        ignore_white: bool = True,
    ) -> ImportedImage:
        try:
            fmt = FileFormat.from_path(path)
        except ValueError as exc:
            raise ImageImportError(f"Formato de imagem nao suportado: {path}") from exc
        if not fmt.is_image:
            raise ImageImportError(f"Nao e uma imagem: {path}")

        rgba = self._decode(path)
        dpi = self._read_dpi(path)
        height, width = rgba.shape[:2]
        size = Size(width / dpi * MM_PER_INCH, height / dpi * MM_PER_INCH)

        has_alpha = bool(rgba[:, :, 3].min() < _ALPHA_OPAQUE)
        image_kind = ImageKind.IMAGE_ALPHA if has_alpha else ImageKind.IMAGE_OPAQUE
        # detecta TODOS os desenhos separados (maior primeiro); o maior vira o
        # contorno principal e os demais viram raw_contours (facas adicionais).
        contours = self.detect_contours(
            rgba, dpi, sensitivity=sensitivity, ignore_white=ignore_white
        )
        if contours:
            contour = contours[0]
            extras = tuple(contours[1:])
        else:
            contour = self._full_rect(size.width, size.height)
            extras = ()

        stem = Path(path).stem or "imagem"
        art_id = f"{stem}#{self._short_hash(path)}"
        artwork = ImageArtwork(
            id=art_id,
            name=stem,
            file_format=fmt,
            size=size,
            kind=ArtKind.RASTER,
            cut_contour=contour,
            dpi=dpi,
            image_kind=image_kind,
            raw_contour=contour,
            raw_contours=extras,
        )
        return ImportedImage(artwork, self._render_path(path, fmt, rgba))

    # ---- decodificacao / metadados ----
    def _decode(self, path: str) -> np.ndarray:
        key = self._file_key(path)
        cached = self._decoded.get(key)
        if cached is not None:
            self._decoded.move_to_end(key)
            return cached
        # abrir_imagem: EXIF aplicado, 16 bits escalado, erro em portugues para
        # imagem grande demais — a MESMA abertura do preview e da impressao
        im = abrir_imagem(path)
        try:
            rgba = np.array(im.convert("RGBA"))
        except MemoryError as exc:
            raise ImageImportError(
                f"Sem memória para abrir a imagem ({im.width} x {im.height} px). "
                f"Feche outros programas ou reduza a resolução.\n\n{path}"
            ) from exc
        except (OSError, ValueError) as exc:
            raise ImageImportError(f"Falha ao ler a imagem: {path}") from exc
        finally:
            im.close()
        if rgba.ndim != 3 or rgba.shape[2] != 4:
            raise ImageImportError(f"Imagem sem formato esperado: {path}")
        self._decoded[key] = rgba
        while len(self._decoded) > MAX_DECODED_CACHE:
            self._decoded.popitem(last=False)
        return rgba

    @staticmethod
    def _read_dpi(path: str) -> float:
        try:
            with Image.open(path) as im:
                dpi = im.info.get("dpi")
        except (OSError, ValueError):
            dpi = None
        if isinstance(dpi, (tuple, list)) and dpi:
            value = float(dpi[0])
        elif isinstance(dpi, (int, float)):
            value = float(dpi)
        else:
            value = 0.0
        return value if value > 1.0 else DEFAULT_DPI

    def detect_contour_from_png(
        self, data: bytes, dpi: float, *, sensitivity: float = 50.0, ignore_white: bool = True
    ) -> CutContour:
        """Detecta o contorno a partir de um PNG em bytes (ex.: pagina de PDF
        rasterizada). Reaproveita a mesma deteccao das imagens."""
        import io

        with Image.open(io.BytesIO(data)) as im:
            rgba = np.array(im.convert("RGBA"))
        return self.detect_contour(
            rgba, dpi, sensitivity=sensitivity, ignore_white=ignore_white
        )

    def detect_contour(
        self,
        rgba: np.ndarray,
        dpi: float,
        *,
        sensitivity: float = 50.0,
        ignore_white: bool = True,
    ) -> CutContour:
        """Detecta o contorno externo de um array RGBA (reutilizavel: imagem ou
        pagina de PDF rasterizada). Devolve a faca em milimetros."""
        height, width = rgba.shape[:2]
        has_alpha = bool(rgba[:, :, 3].min() < _ALPHA_OPAQUE)
        mask = self._mask_reduzida(rgba, has_alpha, sensitivity, ignore_white)
        return self._contour(mask, width, height, dpi)

    # ---- mascara de conteudo ----
    def _mask_reduzida(
        self, rgba: np.ndarray, has_alpha: bool, sensitivity: float, ignore_white: bool
    ) -> np.ndarray:
        """Mascara JA no tamanho de deteccao (lado maior <= MAX_DETECT_SIDE).

        A mascara de imagem grande era montada na resolucao CHEIA e so depois
        reduzida: numa foto de 40 MP isso alocava 2,16 GB de float64 para jogar
        fora 98% dos pixels (auditoria de 13/10/2026). Reduzir o RGBA ANTES,
        com o mesmo vizinho-mais-proximo e o mesmo tamanho que _contours_multi
        usaria na mascara, da a mesma mascara — os pixels amostrados sao os
        mesmos. A cor de fundo continua estimada na borda da imagem CHEIA."""
        height, width = rgba.shape[:2]
        longest = max(width, height)
        bg = None
        moldura = (0, 0, 0, 0)
        if ignore_white and not has_alpha:
            moldura = self._moldura_fina(rgba[:, :, :3])
            cima, baixo, esq, dir_ = moldura
            bg = self._background_color(
                rgba[cima:height - baixo, esq:width - dir_, :3]
            )
        scale = 1.0
        if longest > MAX_DETECT_SIDE:
            scale = MAX_DETECT_SIDE / longest
            rgba = cv2.resize(
                rgba, (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=cv2.INTER_NEAREST,
            )
        mask = self._mask(rgba, has_alpha, sensitivity, ignore_white, bg)
        if any(moldura):
            # a moldura e fundo: sem apagar, ela ligaria todo o desenho num
            # retangulo encostado nas 4 bordas
            cima, baixo, esq, dir_ = (math.ceil(v * scale) for v in moldura)
            mh, mw = mask.shape
            mask[:cima, :] = 0
            mask[mh - baixo:, :] = 0
            mask[:, :esq] = 0
            mask[:, mw - dir_:] = 0
        return mask

    @staticmethod
    def _moldura_fina(rgb: np.ndarray) -> tuple[int, int, int, int]:
        """Espessura (cima, baixo, esq, dir) de uma moldura fina na borda.

        Relato real (13/10/2026): um PNG veio com uma linha preta de 1px em
        volta, invisivel na tela. O fundo era estimado SO pela borda de 1px, ou
        seja, pela moldura: "fundo preto", todo o branco virava arte e a faca
        saia um retangulo. Linha da borda que e uniforme e DIFERENTE do que vem
        logo depois e moldura; descasca ate poucos px. Arte que encosta na
        borda nao e uniforme na linha (desenho + fundo) e fica intacta."""
        h, w = rgb.shape[:2]
        limite = max(4, min(12, min(h, w) // 100))
        if min(h, w) <= 4 * limite:
            return (0, 0, 0, 0)

        def linha(lado: str, d: int) -> np.ndarray:
            if lado == "cima":
                return rgb[d, :, :]
            if lado == "baixo":
                return rgb[h - 1 - d, :, :]
            if lado == "esq":
                return rgb[:, d, :]
            return rgb[:, w - 1 - d, :]

        def uniforme(px: np.ndarray) -> np.ndarray | None:
            cor = np.median(px, axis=0)
            perto = np.abs(px.astype(np.int16) - cor).max(axis=1) <= 24
            return cor if perto.mean() >= 0.97 else None

        espessuras = []
        for lado in ("cima", "baixo", "esq", "dir"):
            d = 0
            while d < limite:
                cor = uniforme(linha(lado, d))
                if cor is None:
                    break
                # referencia ALEM da espessura maxima: logo depois da linha
                # ainda pode ser moldura (moldura de 3px "parecia" fundo)
                dentro = np.median(
                    np.concatenate([linha(lado, k) for k in range(limite, 2 * limite)]),
                    axis=0,
                )
                if np.abs(cor - dentro).max() <= 24:
                    break  # a linha e igual ao que vem depois: e fundo, nao moldura
                d += 1
            espessuras.append(d)
        return tuple(espessuras)

    def _mask(
        self, rgba: np.ndarray, has_alpha: bool, sensitivity: float, ignore_white: bool,
        bg: np.ndarray | None = None,
    ) -> np.ndarray:
        s = max(0.0, min(100.0, float(sensitivity)))
        if has_alpha:
            cutoff = int(round(255 * (1 - s / 100.0)))
            cutoff = max(1, min(254, cutoff))
            return (rgba[:, :, 3] >= cutoff).astype(np.uint8)
        if not ignore_white:
            return np.ones(rgba.shape[:2], dtype=np.uint8)  # arte inteira (retangulo)
        # Remove o fundo automaticamente: estima a cor de fundo pela borda da
        # imagem e marca como conteudo todo pixel que se afasta dela. Funciona
        # para fundo branco, escuro ou colorido (nao so branco). Para fundo
        # branco e equivalente ao criterio antigo (distancia ao branco).
        rgb = rgba[:, :, :3].astype(np.int16)
        if bg is None:
            bg = self._background_color(rgb)
        tol = (s / 100.0) * 55.0  # 0 (s=0) .. 55 (s=100)
        diff = np.abs(rgb - bg).max(axis=2)
        return (diff > tol).astype(np.uint8)

    @staticmethod
    def _background_color(rgb: np.ndarray) -> np.ndarray:
        """Cor de fundo estimada pela mediana dos pixels da borda (1 px)."""
        border = np.concatenate(
            [rgb[0, :, :], rgb[-1, :, :], rgb[:, 0, :], rgb[:, -1, :]], axis=0
        )
        return np.median(border, axis=0)

    # ---- contorno externo ----
    def _contour(self, mask: np.ndarray, width: int, height: int, dpi: float) -> CutContour:
        """Maior contorno (compat.: PDF rasterizado, faca unica)."""
        multi = self._contours_multi(mask, width, height, dpi)
        return multi[0] if multi else self._full_rect(
            width * MM_PER_INCH / dpi, height * MM_PER_INCH / dpi
        )

    def _contours_multi(
        self, mask: np.ndarray, width: int, height: int, dpi: float
    ) -> list[CutContour]:
        """TODOS os desenhos separados na imagem (maior primeiro), filtrando
        ruido por area. Uma folha com N adesivos -> N contornos."""
        mm_per_px = MM_PER_INCH / dpi
        scale = 1.0
        detect = mask
        longest = max(width, height)
        if longest > MAX_DETECT_SIDE:
            scale = MAX_DETECT_SIDE / longest
            detect = cv2.resize(
                mask, (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=cv2.INTER_NEAREST,
            )
        elif longest < MIN_DETECT_SIDE:
            # sub-pixel: amplia a mascara suavizando os degraus dos pixels; o
            # contorno sai da CURVA real, nao da escadinha (limiar re-binariza)
            scale = min(UPSCALE_MAX, MIN_DETECT_SIDE / longest)
            big = cv2.resize(
                mask * 255,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_CUBIC,
            )
            detect = (big >= 128).astype(np.uint8)
        mm_per_detect = mm_per_px / scale

        found, _ = cv2.findContours(detect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not found:
            return []
        # filtro por area ABSOLUTA (mm^2): pega elementos pequenos reais mas
        # ignora ruido, sem depender do tamanho da imagem. cv2.contourArea vem
        # em pixels da mascara de deteccao -> converte com mm_per_detect^2.
        min_area_px = MIN_DESIGN_MM2 / (mm_per_detect * mm_per_detect)
        big = [c for c in found if cv2.contourArea(c) >= min_area_px]
        if not big:  # nada passou -> mantem ao menos o maior (desenho unico)
            big = [max(found, key=cv2.contourArea)]
        big.sort(key=cv2.contourArea, reverse=True)
        epsilon = max(1.0, SIMPLIFY_MM / mm_per_detect)
        out: list[CutContour] = []
        for cnt in big[:MAX_DESIGNS]:
            approx = cv2.approxPolyDP(cnt, epsilon, True).reshape(-1, 2)
            if len(approx) < 3:
                continue
            out.append(CutContour(
                [Point2D(float(c) * mm_per_detect, float(r) * mm_per_detect)
                 for c, r in approx]
            ))
        return out

    def detect_contours(
        self,
        rgba: np.ndarray,
        dpi: float,
        *,
        sensitivity: float = 50.0,
        ignore_white: bool = True,
    ) -> list[CutContour]:
        """Todos os contornos (desenhos separados) de um RGBA, maior primeiro."""
        height, width = rgba.shape[:2]
        has_alpha = bool(rgba[:, :, 3].min() < _ALPHA_OPAQUE)
        mask = self._mask_reduzida(rgba, has_alpha, sensitivity, ignore_white)
        return self._contours_multi(mask, width, height, dpi)

    @staticmethod
    def _full_rect(w_mm: float, h_mm: float) -> CutContour:
        return CutContour([
            Point2D(0.0, 0.0), Point2D(w_mm, 0.0),
            Point2D(w_mm, h_mm), Point2D(0.0, h_mm),
        ])

    # ---- caminho de renderizacao (webp -> png em cache) ----
    def _render_path(self, path: str, fmt: FileFormat, rgba: np.ndarray) -> str:
        if fmt is not FileFormat.WEBP:
            return str(Path(path).resolve())
        key = self._file_key(path)
        cached = self._render_paths.get(key)
        if cached is not None and Path(cached).exists():
            return cached
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        target = self._cache_dir / f"{self._short_hash(path)}.png"
        try:
            Image.fromarray(rgba, "RGBA").save(target)
        except OSError as exc:
            raise ImageImportError(f"Falha ao normalizar WEBP: {path}") from exc
        out = str(target)
        self._render_paths[key] = out
        return out

    # ---- chaves de cache ----
    @staticmethod
    def _file_key(path: str) -> tuple:
        p = Path(path)
        try:
            stat = p.stat()
            return (str(p.resolve()), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return (str(p.resolve()), 0, 0)

    @staticmethod
    def _short_hash(path: str) -> str:
        return hashlib.md5(str(Path(path).resolve()).encode("utf-8")).hexdigest()[:8]
