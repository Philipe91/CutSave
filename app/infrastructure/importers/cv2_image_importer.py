from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.application.ports.image_importer import IImageImporter, ImportedImage
from app.domain.geometry import Point2D, Size
from app.domain.model.artwork import ArtKind, FileFormat
from app.domain.model.cut_contour import CutContour
from app.domain.model.image_artwork import ImageArtwork, ImageKind
from app.shared.errors import ImageImportError

MM_PER_INCH = 25.4
DEFAULT_DPI = 96.0
# Lado maximo (px) da mascara antes do findContours: limita o custo em imagens grandes.
MAX_DETECT_SIDE = 1000
# Tolerancia de simplificacao do contorno (mm): remove pontos redundantes.
SIMPLIFY_MM = 0.3
# Alpha minimo (0-255) para considerar um pixel opaco ao classificar a imagem.
_ALPHA_OPAQUE = 250


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
        self._decoded: dict[tuple, np.ndarray] = {}
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
        mask = self._mask(rgba, has_alpha, sensitivity, ignore_white)
        contour = self._contour(mask, width, height, dpi)

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
        )
        return ImportedImage(artwork, self._render_path(path, fmt, rgba))

    # ---- decodificacao / metadados ----
    def _decode(self, path: str) -> np.ndarray:
        key = self._file_key(path)
        cached = self._decoded.get(key)
        if cached is not None:
            return cached
        try:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im)
                rgba = np.array(im.convert("RGBA"))
        except (OSError, ValueError) as exc:
            raise ImageImportError(f"Falha ao ler a imagem: {path}") from exc
        if rgba.ndim != 3 or rgba.shape[2] != 4:
            raise ImageImportError(f"Imagem sem formato esperado: {path}")
        self._decoded[key] = rgba
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

    # ---- mascara de conteudo ----
    def _mask(
        self, rgba: np.ndarray, has_alpha: bool, sensitivity: float, ignore_white: bool
    ) -> np.ndarray:
        s = max(0.0, min(100.0, float(sensitivity)))
        if has_alpha:
            cutoff = int(round(255 * (1 - s / 100.0)))
            cutoff = max(1, min(254, cutoff))
            return (rgba[:, :, 3] >= cutoff).astype(np.uint8)
        if not ignore_white:
            return np.ones(rgba.shape[:2], dtype=np.uint8)  # arte inteira (retangulo)
        white_cutoff = 255 - (s / 100.0) * 55.0  # 255 (s=0) .. 200 (s=100)
        min_channel = rgba[:, :, :3].min(axis=2)
        return (min_channel < white_cutoff).astype(np.uint8)

    # ---- contorno externo ----
    def _contour(self, mask: np.ndarray, width: int, height: int, dpi: float) -> CutContour:
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
        mm_per_detect = mm_per_px / scale

        contours, _ = cv2.findContours(detect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return self._full_rect(width * mm_per_px, height * mm_per_px)
        biggest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(biggest) <= 0:
            return self._full_rect(width * mm_per_px, height * mm_per_px)

        epsilon = max(1.0, SIMPLIFY_MM / mm_per_detect)
        approx = cv2.approxPolyDP(biggest, epsilon, True).reshape(-1, 2)
        if len(approx) < 3:
            return self._full_rect(width * mm_per_px, height * mm_per_px)
        points = [Point2D(float(c) * mm_per_detect, float(r) * mm_per_detect) for c, r in approx]
        return CutContour(points)

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
