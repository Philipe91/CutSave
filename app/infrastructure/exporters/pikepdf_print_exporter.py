from __future__ import annotations

import contextlib
import io
import math
import os
from collections.abc import Callable, Sequence
from pathlib import Path

from app.application.dto.print_placement import PrintSheet
from app.application.ports.print_pdf_exporter import IPrintPdfExporter
from app.infrastructure.color_space import origem_e_cmyk
from app.infrastructure.exporters.pdf_writer import PdfWriter, bbox_normalizada
from app.infrastructure.pdfium_boxes import PDFIUM_LOCK, open_pdf, regiao_pdf
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


class ExportacaoCancelada(PrintExportError):
    """O operador cancelou pela janela de acompanhamento. Nao e falha: a UI
    mostra um aviso curto, nao um dialogo de erro. Nenhum arquivo fica."""

    def __init__(self) -> None:
        super().__init__("Exportação cancelada.")


def _temporario_ao_lado(alvo: str) -> str:
    """Caminho temporario na MESMA pasta do alvo (os.replace so e atomico
    dentro do mesmo volume)."""
    p = Path(alvo)
    return str(p.with_name(f"{p.name}.{os.getpid()}.parcial"))


def _apagar(caminho: str | None) -> None:
    if caminho:
        with contextlib.suppress(OSError):
            Path(caminho).unlink()


def _is_image_source(path: str) -> bool:
    return Path(path).suffix.lower() in _IMAGE_SUFFIXES


_srgb: bytes | None = None
_srgb_lido = False


def _perfil_srgb() -> bytes | None:
    """Bytes do perfil sRGB para marcar a imagem exportada (None se o Pillow
    desta instalacao vier sem littleCMS). Montado uma vez so."""
    global _srgb, _srgb_lido
    if not _srgb_lido:
        _srgb_lido = True
        try:
            from PIL import ImageCms

            _srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        except Exception:
            _srgb = None
    return _srgb


def _no_espaco_de_saida(pil, fmt: str, color_space: str, icc_path: str | None):
    """(imagem, bytes do perfil) no espaco de cor pedido para a exportacao.

    CMYK so em JPEG — PNG nao guarda CMYK, e o pedido cai para RGB em vez de
    virar erro. Conversao que falha (perfil corrompido, Pillow sem littleCMS)
    tambem cai para RGB: entregar a chapa em RGB e melhor do que nao entregar
    chapa nenhuma."""
    if (color_space or "rgb").lower() == "cmyk" and fmt == "jpeg":
        convertida, perfil = _para_cmyk(pil, icc_path)
        if convertida is not None:
            return convertida, perfil
    return pil, _perfil_srgb()


def _para_cmyk(pil, icc_path: str | None):
    """Converte a imagem RGB para CMYK com gerenciamento de cor.

    Colorimetrico relativo COM compensacao de ponto preto: e o que mantem a
    imagem sem estourar as sombras na conversao para tinta, e o padrao que as
    graficas esperam. (None, None) quando nao da para converter."""
    from app.infrastructure.color_profiles import caminho_do_perfil_padrao

    destino = icc_path or caminho_do_perfil_padrao()
    if not destino:
        return None, None
    try:
        from PIL import ImageCms

        origem = ImageCms.createProfile("sRGB")
        perfil = ImageCms.getOpenProfile(destino)
        convertida = ImageCms.profileToProfile(
            pil, origem, perfil, outputMode="CMYK",
            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
            flags=ImageCms.Flags.BLACKPOINTCOMPENSATION,
        )
        if convertida is None:
            return None, None
        return convertida, perfil.tobytes()
    except Exception:
        return None, None  # perfil ilegivel: exporta em RGB, sem quebrar


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

    @staticmethod
    def _trabalho_e_cmyk(sheets: Sequence[PrintSheet]) -> bool:
        """Alguma peca desta exportacao esta em CMYK?"""
        return any(
            origem_e_cmyk(pl.source_path, pl.source_page)
            for sheet in sheets
            for pl in sheet.placements
        )

    @staticmethod
    def _herdar_output_intent(writer: PdfWriter, sheets: Sequence[PrintSheet]) -> None:
        """Traz o OutputIntent da primeira origem que tiver um."""
        for sheet in sheets:
            for pl in sheet.placements:
                if _is_image_source(pl.source_path):
                    continue
                if writer.copiar_output_intents(pl.source_path):
                    return

    def _build_writer(
        self, sheets: Sequence[PrintSheet], *, imagens_em_rgb: bool = False
    ) -> PdfWriter:
        writer = PdfWriter(imagens_em_rgb=imagens_em_rgb)
        clips: dict = {}  # (path, pagina, box, crop) -> clip em pt (ou None)
        # Espaco de cor do trabalho: com arte CMYK as marcas do PrintNest saem
        # em K puro e o OutputIntent da origem vem junto. Sem isso o arquivo
        # vira hibrido (arte CMYK + marcas RGB, sem perfil de destino) e o RIP
        # decide sozinho como converter — foi o que deixou a chapa impressa
        # com a cor trocada em relacao a arte (relatado em 03/09/2026).
        if self._trabalho_e_cmyk(sheets):
            writer.usar_marcas_cmyk()
            self._herdar_output_intent(writer, sheets)
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
        # grava ao lado e so troca no fim: falha no meio (disco cheio, pasta
        # de rede que caiu) deixava um PDF truncado POR CIMA do arquivo bom que
        # ja estava la (auditoria de 13/10/2026)
        temporario = _temporario_ao_lado(output_path)
        try:
            writer.save(temporario)
            os.replace(temporario, output_path)
        except Exception as exc:
            _apagar(temporario)
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
        color_space: str = "rgb",
        icc_path: str | None = None,
        quality: int = 95,
        cancelado: Callable[[], bool] | None = None,
    ) -> list[str]:
        """Rasteriza o documento de impressao: uma imagem por chapa, no DPI
        dado. Com mais de uma chapa, gera arquivos numerados (..._01, _02).
        Retorna os caminhos gerados.

        color_space: 'rgb' (padrao) ou 'cmyk'. Em CMYK a imagem e convertida
        com gerenciamento de cor para 'icc_path' (ou o perfil padrao da
        maquina) e o perfil vai EMBUTIDO no arquivo. So vale para JPEG: PNG
        nao guarda CMYK, e pedir CMYK em PNG exporta em RGB em vez de recusar
        — o arquivo e do cliente e ele pediu a chapa, nao uma negativa.

        ATENCAO ao que esta opcao NAO faz: o pdfium so rasteriza em RGB,
        entao o CMYK aqui e uma CONVERSAO (CMYK->RGB->CMYK), nao o CMYK
        original da arte. Tinta pura nao sobrevive ao ida e volta (K puro
        vira preto de quatro cores). Para cor identica a da arte, o caminho e
        exportar em PDF, que preserva as tintas byte a byte. O ganho aqui e
        outro e real: sem esta opcao o RIP fazia essa mesma conversao as
        cegas, com um perfil que ninguem escolheu.

        O arquivo do cliente SEMPRE e gravado — a decisao de exportar e dele
        (06/08). PrintExportError so em falha de verdade: memoria que nao deu
        ou lado maior do que o formato guarda.

        'progresso' recebe (fracao 0..1, texto) e e chamado na MESMA thread.

        'cancelado' e consultado antes de cada chapa e de cada faixa (a janela
        de acompanhamento liga o botao Cancelar nele). Cancelou: levanta
        ExportacaoCancelada e apaga TUDO que esta exportacao ja gravou —
        inclusive chapas anteriores inteiras. Exportacao cancelada nao deixa
        arquivo: meia serie na pasta do cliente vira chapa faltando na
        producao sem ninguem perceber."""
        import pypdfium2 as pdfium

        def _parar() -> bool:
            return bool(cancelado and cancelado())

        fmt = image_format.lower()
        if fmt == "jpg":
            fmt = "jpeg"
        ext = Path(output_path).suffix or ("." + ("jpg" if fmt == "jpeg" else fmt))
        stem = str(Path(output_path).with_suffix(""))
        if progresso:
            progresso(0.0, "Montando o documento…")
        # imagens_em_rgb: este documento existe so para o pdfium rasterizar.
        # Imagem CMYK entra ja convertida para sRGB (uma vez, com o perfil
        # dela) em vez de /ICCBased de 4 canais, que o pdfium converte pixel
        # a pixel para cada copia em cada faixa — 40 copias de um JPEG CMYK
        # a 300 DPI passavam de 10min (11/09/2026). A cor e a mesma.
        writer = self._build_writer(sheets, imagens_em_rgb=True)
        try:
            data = writer.save_bytes()
        finally:
            writer.close()
        # generated: SO o que esta exportacao gravou (ja trocado no lugar).
        # Arquivo de exportacao anterior que ainda nao foi regravado nao e
        # nosso: cancelar no meio da serie nao pode apagar o _02 de ontem.
        generated: list[str] = []
        temporario: str | None = None
        with PDFIUM_LOCK:  # pdfium não é thread-safe (worker + UI ao vivo)
            try:
                doc = pdfium.PdfDocument(io.BytesIO(data))
            except Exception as exc:
                raise PrintExportError(f"Falha ao gerar imagem: {output_path}") from exc
            try:
                total = len(doc)
                multi = total > 1
                for index in range(total):
                    if _parar():
                        raise ExportacaoCancelada()
                    page = doc[index]
                    target = f"{stem}_{index + 1:02d}{ext}" if multi else output_path
                    rotulo = f"Chapa {index + 1} de {total}" if multi else "Exportando"

                    def _passo(fr: float, etapa: str = "", _i=index, _r=rotulo) -> None:
                        if progresso:
                            # etapa (converter/gravar) e o que o operador ve
                            # nos ~20s finais; em serie, a chapa vem junto
                            if etapa:
                                texto = f"{_r} · {etapa}" if multi else etapa
                            else:
                                texto = _r
                            progresso((_i + fr) / total, texto)

                    pil = self._rasterizar_pagina(page, dpi, fmt, _passo, _parar)
                    try:
                        em_cmyk = (color_space or "rgb").lower() == "cmyk" and fmt == "jpeg"
                        _passo(0.96, "Convertendo para CMYK…" if em_cmyk else "")
                        # dpi GRAVADO no arquivo: sem ele o RIP/Corel abre a
                        # 96dpi e a chapa de 19,7cm vira 92cm (teste real
                        # 16/07 — regressão da migração PyMuPDF->pdfium)
                        #
                        # O arquivo tem que DIZER em que espaco de cor ele
                        # esta: sem perfil embutido cada RIP assume um
                        # diferente e a mesma chapa imprime diferente em cada
                        # maquina (03/09/2026). Em CMYK converte e embute o
                        # perfil de destino; em RGB embute o sRGB.
                        pil, icc = _no_espaco_de_saida(pil, fmt, color_space, icc_path)
                        extra = {"icc_profile": icc} if icc else {}
                        _passo(0.98, "Gravando arquivo…")
                        # grava ao lado e troca no fim: falha no meio nao deixa
                        # imagem truncada por cima da chapa boa que ja existia
                        temporario = _temporario_ao_lado(target)
                        try:
                            if fmt == "jpeg":
                                pil.save(temporario, format="JPEG",
                                         quality=int(quality),
                                         dpi=(dpi, dpi), **extra)
                            else:
                                pil.save(temporario, format=fmt.upper(),
                                         dpi=(dpi, dpi), **extra)
                            os.replace(temporario, target)
                        except Exception as exc:
                            raise PrintExportError(
                                f"Falha ao gerar imagem: {target}"
                            ) from exc
                        temporario = None
                    finally:
                        pil.close()
                    generated.append(target)
                    _passo(1.0)
            except BaseException:
                # cancelou ou falhou: nada desta exportacao fica — o parcial e
                # as chapas ja prontas. Meia serie na pasta do cliente vira
                # chapa faltando na producao sem ninguem perceber.
                _apagar(temporario)
                for caminho in generated:
                    _apagar(caminho)
                raise
            finally:
                doc.close()
        return generated

    @staticmethod
    def _rasterizar_pagina(page, dpi: int, fmt: str, passo, parar=None):
        """Rasteriza UMA pagina em RGB, em faixas. Devolve a imagem.

        'parar' (opcional) e consultado antes de cada faixa: True levanta
        ExportacaoCancelada — uma faixa de 300 DPI leva ~5s, entao o Cancelar
        responde nesse prazo sem precisar interromper o pdfium no meio.

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
                if parar and parar():
                    raise ExportacaoCancelada()
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
                # a MESMA regiao do tamanho importado e do preview (antes: apara
                # ou a MediaBox inteira, mesmo com CropBox menor — 13/10/2026).
                # Coords cruas, sem /Rotate: o giro da pagina e do PdfWriter.
                rect = regiao_pdf(page, box)
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
