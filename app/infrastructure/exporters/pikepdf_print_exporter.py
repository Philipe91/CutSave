from __future__ import annotations

import io
import math
from collections.abc import Callable, Sequence
from pathlib import Path

from app.application.dto.print_placement import PrintSheet
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.infrastructure.exporters.pdf_writer import PdfWriter, bbox_normalizada
from app.infrastructure.pdfium_boxes import PDFIUM_LOCK, open_pdf, raw_box, trim_clip_pdf
from app.infrastructure.pdfium_knife import knife_free_pdf
from app.shared.errors import PrintExportError

MM2PT = 72.0 / 25.4
PT2MM = 25.4 / 72.0
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# --- Rasterizacao em DPI alto -------------------------------------------
# Bug de 06/08/2026: chapa pesada (imagem + vetor) exportada em JPEG a 500 DPI
# saia com PECAS INTEIRAS FALTANDO, sem erro nenhum. O pdfium nao levanta
# excecao quando nao consegue alocar o buffer de um objeto: ele desiste
# daquele objeto e devolve o bitmap com buracos. A 400 DPI a mesma chapa
# saia inteira. Daí as tres travas abaixo: limite antes de comecar,
# rasterizacao em faixas (reduz o pico) e conferencia do resultado contra um
# render de referencia — NUNCA gravar arquivo com buraco.
_JPEG_LADO_MAX_PX = 65_500       # limite do proprio formato JPEG
_PNG_LADO_MAX_PX = 200_000       # limite pratico do PNG
_ORCAMENTO_PX_PADRAO = 250_000_000
_FRACAO_RAM = 0.35               # da RAM livre que aceitamos ocupar
_BYTES_POR_PX = 3                # imagem final em RGB
_FAIXA_LIMIAR_PX = 120_000_000   # abaixo disso: rasteriza de uma vez so
_FAIXA_ALVO_PX = 60_000_000      # ~240 MB por faixa no pdfium (BGRA)

# Nao existe conferencia do resultado, de proposito. Uma versao anterior
# comparava a imagem com um render de referencia e avisava quando achava area
# em branco — e acusou falha num arquivo INTEIRO, exportado a 290 DPI
# (06/08/2026). Aviso que erra queima a confianca em todos os outros avisos do
# programa, entao a heuristica saiu. O que sobra e o que e fato: o peso da
# exportacao (mostrado como nivel, antes de comecar) e o limite do formato.
NIVEIS = ("rapido", "normal", "demorado", "muito_demorado")
_ROTULO_NIVEL = {
    "rapido": "Rápido",
    "normal": "Normal",
    "demorado": "Demorado",
    "muito_demorado": "Bem demorado",
    "impossivel": "Grande demais para o formato",
}


def _is_image_source(path: str) -> bool:
    return Path(path).suffix.lower() in _IMAGE_SUFFIXES


def _ram_livre_bytes() -> int | None:
    """RAM fisica livre (bytes) no Windows. None quando nao da para saber."""
    try:
        import ctypes

        class _Status(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = _Status()
        st.dwLength = ctypes.sizeof(_Status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return None
        return int(st.ullAvailPhys)
    except Exception:
        return None


def _orcamento_px() -> int:
    """Quantos pixels a imagem final pode ter sem estourar a memoria."""
    livre = _ram_livre_bytes()
    if not livre:
        return _ORCAMENTO_PX_PADRAO
    return max(40_000_000, int(livre * _FRACAO_RAM) // _BYTES_POR_PX)


def _lado_maximo(image_format: str) -> int:
    fmt = (image_format or "png").lower()
    return _JPEG_LADO_MAX_PX if fmt in ("jpg", "jpeg") else _PNG_LADO_MAX_PX


def tamanho_em_pixels(largura_mm: float, altura_mm: float, dpi: int) -> tuple[int, int]:
    """Quantos pixels a imagem vai ter neste DPI."""
    escala = max(int(dpi), 1) / 25.4
    return max(1, round(largura_mm * escala)), max(1, round(altura_mm * escala))


def peso_exportacao(
    largura_mm: float, altura_mm: float, dpi: int, image_format: str = "png"
) -> tuple[str, str, str]:
    """Quanto esta exportacao vai pesar: (nivel, rotulo, tamanho).

    nivel: 'rapido' | 'normal' | 'demorado' | 'muito_demorado' | 'impossivel'.

    Fala de TEMPO, nunca de arquivo errado. Prometer defeito que pode nao
    acontecer custa a confianca do cliente em todo o resto que o programa diz
    (decisao de 06/08). 'impossivel' nao e palpite: o JPEG nao guarda lado
    maior que 65.535 px, entao nao existe arquivo para gravar."""
    w_px, h_px = tamanho_em_pixels(largura_mm, altura_mm, dpi)
    tamanho = f"{w_px:,} × {h_px:,} px".replace(",", ".")
    if max(w_px, h_px) > _lado_maximo(image_format):
        return "impossivel", _ROTULO_NIVEL["impossivel"], tamanho
    total = w_px * h_px
    orcamento = _orcamento_px()
    if total <= orcamento * 0.25:
        nivel = "rapido"
    elif total <= orcamento * 0.5:
        nivel = "normal"
    elif total <= orcamento:
        nivel = "demorado"
    else:
        nivel = "muito_demorado"
    return nivel, _ROTULO_NIVEL[nivel], tamanho


def _texto_sem_memoria(largura_mm: float, altura_mm: float, dpi: int, fmt: str) -> str:
    """Falhou de verdade: nao houve memoria para montar a imagem."""
    return (
        f"Não houve memória para montar esta chapa a {dpi} DPI "
        f"({largura_mm / 10:.1f} × {altura_mm / 10:.1f} cm).\n\n"
        "Feche outros programas e tente de novo, ou exporte em uma "
        "resolução menor."
    )


class PikePdfPrintExporter(IPrintPdfExporter):
    """Gera o PDF de impressao (uma pagina por chapa), preservando vetores.

    Substitui o exportador PyMuPDF (migracao de licenca AGPL -> livre):
    cada pagina-fonte entra como Form XObject (sem rasterizar), com o mesmo
    recorte (caixa escolhida menos o recorte de borda) e rotacao. A
    exportacao em imagem rasteriza esse mesmo documento com o pdfium.
    """

    def _build_writer(self, sheets: Sequence[PrintSheet]) -> PdfWriter:
        writer = PdfWriter()
        clips: dict = {}  # (path, pagina, box, crop) -> clip em pt (ou None)
        try:
            for sheet in sheets:
                writer.new_page(sheet.size.width, sheet.size.height)
                for pl in sheet.placements:
                    if _is_image_source(pl.source_path):
                        writer.place_image(
                            pl.source_path,
                            pl.position.x, pl.position.y,
                            pl.size.width, pl.size.height,
                            rotate=pl.rotate, mirror=pl.mirror,
                        )
                        continue
                    # impressão SEM a linha magenta da faca (cópia limpa)
                    src = knife_free_pdf(pl.source_path)
                    key = (src, pl.source_page, pl.box, pl.crop_mm)
                    if key not in clips:
                        clips[key] = self._source_clip(*key)
                    writer.place_pdf_page(
                        src, pl.source_page,
                        pl.position.x, pl.position.y,
                        pl.size.width, pl.size.height,
                        rotate=pl.rotate, mirror=pl.mirror, clip_pdf_pt=clips[key],
                    )
                for circle in sheet.circles:
                    writer.draw_circle(
                        (circle.center.x, circle.center.y),
                        circle.diameter / 2,
                        color=(0, 0, 0), fill=(0, 0, 0),
                    )
                for line in sheet.lines:
                    writer.draw_line(
                        (line.start.x, line.start.y),
                        (line.end.x, line.end.y),
                        width_pt=line.width * MM2PT,
                        color=(0, 0, 0),
                    )
                for rect in sheet.rects:  # quadrados de registro: PRETO solido
                    half = rect.size / 2
                    writer.draw_rect_filled(
                        rect.center.x - half, rect.center.y - half,
                        rect.size, rect.size, color=(0, 0, 0),
                    )
        except Exception as exc:
            writer.close()
            if isinstance(exc, PrintExportError):
                raise
            raise PrintExportError(
                "Falha ao compor o documento de impressao."
            ) from exc
        return writer

    def export(self, sheets: Sequence[PrintSheet], output_path: str) -> None:
        writer = self._build_writer(sheets)
        try:
            writer.save(output_path)
        except Exception as exc:
            raise PrintExportError(
                f"Falha ao gerar PDF de impressao: {output_path}"
            ) from exc
        finally:
            writer.close()

    def export_image(
        self,
        sheets: Sequence[PrintSheet],
        output_path: str,
        *,
        dpi: int = 150,
        image_format: str = "png",
        progresso: Callable[[float, str], None] | None = None,
    ) -> list[str]:
        """Rasteriza o documento de impressao: uma imagem por chapa, no DPI
        dado. Com mais de uma chapa, gera arquivos numerados (..._01, _02).
        Retorna os caminhos gerados.

        O arquivo do cliente SEMPRE e gravado — a decisao de exportar e dele
        (06/08). PrintExportError so em falha de verdade: memoria que nao deu
        ou lado maior do que o formato guarda.

        'progresso' recebe (fracao 0..1, texto) e e chamado na MESMA thread."""
        import pypdfium2 as pdfium

        fmt = image_format.lower()
        if fmt == "jpg":
            fmt = "jpeg"
        ext = Path(output_path).suffix or ("." + ("jpg" if fmt == "jpeg" else fmt))
        stem = str(Path(output_path).with_suffix(""))
        if progresso:
            progresso(0.0, "Montando o documento…")
        writer = self._build_writer(sheets)
        try:
            data = writer.save_bytes()
        finally:
            writer.close()
        generated: list[str] = []
        with PDFIUM_LOCK:  # pdfium não é thread-safe (worker + UI ao vivo)
            try:
                doc = pdfium.PdfDocument(io.BytesIO(data))
            except Exception as exc:
                raise PrintExportError(f"Falha ao gerar imagem: {output_path}") from exc
            try:
                total = len(doc)
                multi = total > 1
                for index in range(total):
                    page = doc[index]
                    target = f"{stem}_{index + 1:02d}{ext}" if multi else output_path
                    rotulo = f"Chapa {index + 1} de {total}" if multi else "Exportando"

                    def _passo(fr: float, _i=index, _r=rotulo) -> None:
                        if progresso:
                            progresso((_i + fr) / total, _r)

                    pil = self._rasterizar_pagina(page, dpi, fmt, _passo)
                    try:
                        _passo(0.97)
                        # dpi GRAVADO no arquivo: sem ele o RIP/Corel abre a
                        # 96dpi e a chapa de 19,7cm vira 92cm (teste real
                        # 16/07 — regressão da migração PyMuPDF->pdfium)
                        try:
                            if fmt == "jpeg":
                                pil.save(target, format="JPEG", quality=95, dpi=(dpi, dpi))
                            else:
                                pil.save(target, format=fmt.upper(), dpi=(dpi, dpi))
                        except Exception as exc:
                            raise PrintExportError(
                                f"Falha ao gerar imagem: {target}"
                            ) from exc
                    finally:
                        pil.close()
                    generated.append(target)
                    _passo(1.0)
            finally:
                doc.close()
        return generated

    @staticmethod
    def _rasterizar_pagina(page, dpi: int, fmt: str, passo):
        """Rasteriza UMA pagina em RGB, em faixas. Devolve a imagem.

        NAO recusa por causa do DPI: quem decide exportar e o dono do arquivo
        (06/08). So levanta PrintExportError quando nao ha imagem nenhuma para
        entregar — memoria que nao deu, ou lado maior do que o formato guarda."""
        from PIL import Image

        w_pt, h_pt = page.get_size()
        largura_mm, altura_mm = w_pt * PT2MM, h_pt * PT2MM

        escala = dpi / 72.0
        w_px = max(1, round(w_pt * escala))
        h_px = max(1, round(h_pt * escala))
        total_px = w_px * h_px
        # unico caso sem saida: o formato nao guarda um lado desse tamanho, e
        # nao existe arquivo para gravar. Aqui recusar e o certo.
        if max(w_px, h_px) > _lado_maximo(fmt):
            raise PrintExportError(
                f"A imagem ficaria com {w_px:,} × {h_px:,} px".replace(",", ".")
                + ".\n\nO formato JPEG não guarda imagem com lado maior que "
                "65.535 px. Reduza a resolução ou exporte em PNG."
            )

        if total_px <= _FAIXA_LIMIAR_PX:
            altura_faixa = h_px  # cabe de uma vez: caminho rapido de sempre
        else:
            altura_faixa = max(1, min(h_px, int(_FAIXA_ALVO_PX // max(1, w_px))))
        n_faixas = math.ceil(h_px / altura_faixa)

        try:
            canvas = Image.new("RGB", (w_px, h_px), (255, 255, 255))
        except (MemoryError, OSError) as exc:
            raise PrintExportError(
                _texto_sem_memoria(largura_mm, altura_mm, dpi, fmt)
            ) from exc

        try:
            for i in range(n_faixas):
                y0 = i * altura_faixa
                y1 = min(h_px, y0 + altura_faixa)
                # crop do pdfium = quanto cortar de (esquerda, baixo, direita, topo)
                corte = (0.0, (h_px - y1) / escala, 0.0, y0 / escala)
                try:
                    bmp = page.render(scale=escala, crop=corte)
                    try:
                        faixa = bmp.to_pil().convert("RGB")
                    finally:
                        bmp.close()
                except (MemoryError, OSError) as exc:
                    raise PrintExportError(
                        _texto_sem_memoria(largura_mm, altura_mm, dpi, fmt)
                    ) from exc
                try:
                    if faixa.size != (w_px, y1 - y0):
                        # o pdfium arredonda a altura da faixa PARA CIMA (pede
                        # 253, devolve 254). Cortar a sobra mantem o pixel
                        # alinhado; redimensionar reamostra a faixa inteira e
                        # o resultado deixa de bater com o de uma tacada so.
                        if faixa.width >= w_px and faixa.height >= y1 - y0:
                            ajustada = faixa.crop((0, 0, w_px, y1 - y0))
                        else:  # sobrou faixa menor que o esperado: nao deveria
                            ajustada = faixa.resize((w_px, y1 - y0), Image.BILINEAR)
                        faixa.close()
                        faixa = ajustada
                    canvas.paste(faixa, (0, y0))
                finally:
                    faixa.close()
                passo(0.95 * (i + 1) / n_faixas)
        except BaseException:
            canvas.close()
            raise

        return canvas

    @staticmethod
    def _source_clip(path: str, page_index: int, box: str, crop_mm: float):
        """Recorte da origem em coords PDF cruas (pt): caixa escolhida
        (midia/apara) menos o recorte de borda. None = pagina inteira."""
        with PDFIUM_LOCK:  # pdfium não é thread-safe (worker + UI ao vivo)
            doc = open_pdf(path)
            try:
                page = doc[page_index]
                rect = trim_clip_pdf(page, box)
                if rect is None:
                    rect = raw_box(page, "MediaBox")
                    if rect is None:
                        w, h = page.get_size()
                        rect = (0.0, 0.0, w, h)
                # caixa do PDF pode vir com as coordenadas trocadas (ex.:
                # [0 297 210 0]) — e legal, e o leitor normaliza sozinho. Aqui
                # nao: sem ordenar, x1-x0 fica negativo, o recorte de borda e
                # ignorado em silencio e a arte sai ESPELHADA na impressao.
                rect = bbox_normalizada(rect)
                if crop_mm > 0:
                    crop_pt = crop_mm * MM2PT
                    x0, y0, x1, y1 = rect
                    if (x1 - x0) > 2 * crop_pt and (y1 - y0) > 2 * crop_pt:
                        rect = (x0 + crop_pt, y0 + crop_pt, x1 - crop_pt, y1 - crop_pt)
                return tuple(rect)
            finally:
                doc.close()
