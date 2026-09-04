"""Compositor de PDF com pikepdf (licenca MPL, livre para uso comercial).

Substitui a escrita de PDF do PyMuPDF na migracao de licenca. Uma classe, um
contrato: paginas em mm com origem no TOPO-esquerda (a convencao do PrintNest
inteiro); a conversao para o espaco do PDF (pt, origem embaixo-esquerda) mora
toda aqui dentro.

- place_pdf_page: embute a pagina-fonte como Form XObject (vetores
  PRESERVADOS, sem rasterizar), com recorte (BBox) e rotacao 0/90/180/270 —
  a matriz de posicionamento foi validada pixel a pixel contra o motor
  antigo (sonda de 13/07: 0,04%% de divergencia, so antialiasing).
- place_image: embute PNG/JPG/WEBP; JPEG (RGB/cinza) entra passthrough (DCT,
  sem recomprimir); demais viram Flate, com SMask quando ha transparencia.
- draw_*: desenho vetorial via content stream (linhas, circulos e caminhos
  com Bezier) — a faca curva sai como UM caminho fechado por contorno.
"""

from __future__ import annotations

import io
import zlib
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name
from PIL import Image

MM2PT = 72.0 / 25.4
# fator do arco de circulo por Bezier (4 arcos de 90 graus)
_K = 0.5522847498307936

# modo do Pillow -> espaco de cor do PDF (e quantos canais ele tem)
_DEVICE_DO_MODO = {
    "RGB": Name.DeviceRGB,
    "L": Name.DeviceGray,
    "CMYK": Name.DeviceCMYK,
}
_N_DO_MODO = {"RGB": 3, "L": 1, "CMYK": 4}
# assinatura do espaco de cor no cabecalho ICC (bytes 16..20) -> modo Pillow
_ESPACO_ICC = {b"RGB ": "RGB", b"CMYK": "CMYK", b"GRAY": "L"}


def _espaco_do_perfil(icc: bytes) -> str | None:
    """Espaco de cor declarado no cabecalho do perfil ICC, ou None.

    Serve para nao colar num XObject um perfil que nao corresponde aos canais
    da imagem — o leitor descarta a imagem inteira quando isso acontece."""
    if not icc or len(icc) < 20:
        return None
    return _ESPACO_ICC.get(bytes(icc[16:20]))


def bbox_normalizada(caixa) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) com x0<=x1 e y0<=y1, sempre.

    O PDF NAO exige que as caixas venham ordenadas: escrever a MediaBox como
    [0 297 210 0] e legal, e varios geradores (inclusive exportacoes de
    Corel/Illustrator) fazem isso. Como o leitor normaliza sozinho, o arquivo
    abre certo em qualquer visualizador e ninguem desconfia.

    A matriz de encaixe, porem, calcula a largura como x1-x0: com a caixa
    invertida isso da NEGATIVO, a escala fica negativa e a arte entra
    ESPELHADA no PDF de impressao -- enquanto a faca, que nao passa por aqui,
    sai correta. O resultado e material impresso ao contrario das marcas de
    registro, que so aparece depois de cortar. Relatado em 31/07/2026.
    """
    x0, y0, x1, y1 = (float(v) for v in caixa)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _f(v: float) -> str:
    """Numero em ate 4 casas (0,0001pt = 0,000035mm), sem zeros a direita."""
    return f"{v:.4f}".rstrip("0").rstrip(".")


class PdfWriter:
    """Monta um PDF pagina a pagina e salva em arquivo ou bytes."""

    def __init__(self) -> None:
        self._pdf = pikepdf.new()
        self._sources: dict[str, pikepdf.Pdf] = {}
        self._xobjects: dict = {}   # (path, pagina, clip) -> form xobject
        self._images: dict = {}     # path -> image xobject
        self._pages: list[dict] = []
        self._cur: dict | None = None
        self._cmyk_marcas = False  # ver usar_marcas_cmyk()

    # ---- paginas ----
    def new_page(self, width_mm: float, height_mm: float) -> None:
        page = self._pdf.add_blank_page(
            page_size=(width_mm * MM2PT, height_mm * MM2PT)
        )
        self._cur = {
            "page": page,
            "h_pt": height_mm * MM2PT,
            "ops": [],
            "names": {},
        }
        self._pages.append(self._cur)

    # ---- conversao topo-esquerda (mm) -> PDF (pt, baixo-esquerda) ----
    def _pt(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        return x_mm * MM2PT, self._cur["h_pt"] - y_mm * MM2PT

    # ---- paginas de outros PDFs (vetor preservado) ----
    def place_pdf_page(
        self,
        src_path: str,
        page_index: int,
        x_mm: float,
        y_mm: float,
        w_mm: float,
        h_mm: float,
        *,
        rotate: int = 0,
        mirror: str = "",
        clip_pdf_pt: tuple[float, float, float, float] | None = None,
    ) -> None:
        """Posiciona a pagina-fonte no retangulo destino (topo-esquerda, mm).

        clip_pdf_pt: regiao da FONTE a usar, em coords PDF cruas (pt); a
        regiao e mapeada exatamente no retangulo destino (contrato do antigo
        show_pdf_page com clip)."""
        xo, bbox = self._form_xobject(src_path, page_index, clip_pdf_pt)
        name = self._resource_name(xo)
        m = self._placement_matrix(
            bbox, x_mm * MM2PT, self._cur["h_pt"] - (y_mm + h_mm) * MM2PT,
            w_mm * MM2PT, h_mm * MM2PT, rotate % 360, mirror,
        )
        self._cur["ops"].append(
            f"q {' '.join(_f(v) for v in m)} cm {name} Do Q\n"
        )

    def _form_xobject(self, src_path: str, page_index: int, clip):
        key = (src_path, page_index, clip)
        cached = self._xobjects.get(key)
        if cached is not None:
            return cached
        src = self._sources.get(src_path)
        if src is None:
            src = pikepdf.open(src_path)
            self._sources[src_path] = src
        xo = self._pdf.copy_foreign(src.pages[page_index].as_form_xobject())
        if clip is not None:
            xo.BBox = Array([float(v) for v in clip])
        bbox = bbox_normalizada(xo.BBox)
        self._xobjects[key] = (xo, bbox)
        return xo, bbox

    def _resource_name(self, xo) -> str:
        names = self._cur["names"]
        cached = names.get(id(xo))
        if cached is None:
            cached = str(self._cur["page"].add_resource(xo, Name.XObject))
            names[id(xo)] = cached
        return cached

    @staticmethod
    def _compor(externa, interna):
        """Matriz que aplica `interna` e depois `externa` (mesma convencao do
        operador `cm` do PDF: (a,b,c,d,e,f) leva (x,y) em
        (a*x + c*y + e, b*x + d*y + f))."""
        ai, bi, ci, di, ei, fi = interna
        ao, bo, co, do, eo, fo = externa
        return (
            ai * ao + bi * co, ai * bo + bi * do,
            ci * ao + di * co, ci * bo + di * do,
            ei * ao + fi * co + eo, ei * bo + fi * do + fo,
        )

    @staticmethod
    def _espelho_na_origem(bbox, mirror: str):
        """Reflexao DENTRO da caixa de origem, antes do giro.

        Vale a ordem canonica do PrintNest (a mesma de
        `crop_and_rotate_contour`): **espelhar primeiro, girar depois**. As duas
        ordens dao resultados diferentes em peca girada, e arte e faca precisam
        concordar — senao a mesa corta fora do impresso."""
        bx0, by0, bx1, by1 = bbox
        m = (mirror or "").lower()
        a = -1.0 if "h" in m else 1.0
        d = -1.0 if "v" in m else 1.0
        e = (bx0 + bx1) if "h" in m else 0.0
        f = (by0 + by1) if "v" in m else 0.0
        return (a, 0.0, 0.0, d, e, f)

    @staticmethod
    def _placement_matrix(bbox, x, y, w, h, rot, mirror: str = ""):
        """Matriz cm que mapeia a regiao bbox no retangulo destino (canto
        inferior-esquerdo x,y em pt), girando no MESMO sentido do canvas.

        O canvas gira a arte com QTransform().rotate(+angulo), que no Qt e
        HORARIO. Ate 31/07/2026 esta matriz girava no sentido contrario: a peca
        caia no lugar e no tamanho certos (o retangulo destino e o mesmo nos
        dois sentidos), mas a ARTE saia 180 graus virada em relacao ao que a
        tela mostrava — so em pecas com 90 ou 270. Relatado em producao com a
        impressao saindo de cabeca para baixo enquanto a faca saia certa.
        """
        if mirror:
            # o espelho entra ANTES do giro, composto por fora: a matriz de
            # rotacao abaixo fica intocada (ela foi estabilizada em 31/07 e a
            # escala negativa dela so pode nascer de um pedido EXPLICITO de
            # espelho, nunca de uma caixa de pagina mal ordenada — quem impede
            # isso e `bbox_normalizada`).
            return PdfWriter._compor(
                PdfWriter._placement_matrix(bbox, x, y, w, h, rot),
                PdfWriter._espelho_na_origem(bbox, mirror),
            )
        bx0, by0, bx1, by1 = bbox
        bw, bh = bx1 - bx0, by1 - by0
        if rot == 90:  # horario
            sx, sy = h / bw, w / bh
            return (0, -sx, sy, 0, x - sy * by0, y + h + sx * bx0)
        if rot == 180:
            sx, sy = w / bw, h / bh
            return (-sx, 0, 0, -sy, x + w + sx * bx0, y + h + sy * by0)
        if rot == 270:  # horario
            sx, sy = h / bw, w / bh
            return (0, sx, -sy, 0, x + w + sy * by0, y - sx * bx0)
        sx, sy = w / bw, h / bh
        return (sx, 0, 0, sy, x - sx * bx0, y - sy * by0)

    # ---- imagens raster ----
    def place_image(
        self, img_path: str, x_mm: float, y_mm: float, w_mm: float, h_mm: float,
        *, rotate: int = 0, mirror: str = "",
    ) -> None:
        xo = self._image_xobject(img_path)
        name = self._resource_name(xo)
        m = self._placement_matrix(
            (0.0, 0.0, 1.0, 1.0),
            x_mm * MM2PT, self._cur["h_pt"] - (y_mm + h_mm) * MM2PT,
            w_mm * MM2PT, h_mm * MM2PT, rotate % 360, mirror,
        )
        self._cur["ops"].append(
            f"q {' '.join(_f(v) for v in m)} cm {name} Do Q\n"
        )

    def _image_xobject(self, path: str):
        """Imagem embutida NO ESPACO DE COR EM QUE ELA ENTROU.

        Ate 03/09/2026 toda imagem virava DeviceRGB: um JPEG CMYK de grafica
        era convertido pela formula ingenua do Pillow (ciano 100% virava
        RGB 0,255,255 em vez de ~0,158,224) e o RIP re-separava esse RGB em
        tres tintas — o impresso nao tinha nada a ver com a arte. E um JPEG
        com perfil embutido (Adobe RGB, ProPhoto) perdia o perfil e passava a
        ser lido como sRGB, que desloca a cor inteira. Relatado em producao.

        Agora: CMYK sai CMYK, cinza sai cinza, e o perfil do cliente viaja
        junto como /ICCBased.
        """
        cached = self._images.get(path)
        if cached is not None:
            return cached
        suffix = Path(path).suffix.lower()
        pil = Image.open(path)
        pil.load()
        icc = pil.info.get("icc_profile")
        if suffix in (".jpg", ".jpeg") and pil.mode in ("RGB", "L", "CMYK"):
            # JPEG sem alpha: embute o arquivo ORIGINAL (DCT), sem recomprimir
            xo = pikepdf.Stream(self._pdf, Path(path).read_bytes())
            campos = dict(
                Type=Name.XObject, Subtype=Name.Image,
                Width=pil.width, Height=pil.height,
                ColorSpace=self._colorspace(pil.mode, icc),
                BitsPerComponent=8, Filter=Name.DCTDecode,
            )
            if pil.mode == "CMYK" and pil.info.get("adobe"):
                # JPEG CMYK da Adobe guarda as tintas INVERTIDAS (marcador
                # APP14). Sem este /Decode a arte sai quase preta no PDF —
                # medido no arquivo de teste: ciano 100% renderizava (23,0,0).
                campos["Decode"] = Array([1, 0, 1, 0, 1, 0, 1, 0])
            xo.stream_dict = Dictionary(**campos)
        elif pil.mode == "CMYK":
            # CMYK que nao entra por DCT: recomprime em Flate, mas CONTINUA
            # com as quatro tintas (aqui o Pillow ja devolve nao-invertido).
            xo = pikepdf.Stream(self._pdf, zlib.compress(pil.tobytes()))
            xo.stream_dict = Dictionary(
                Type=Name.XObject, Subtype=Name.Image,
                Width=pil.width, Height=pil.height,
                ColorSpace=self._colorspace("CMYK", icc),
                BitsPerComponent=8, Filter=Name.FlateDecode,
            )
        else:
            has_alpha = pil.mode in ("RGBA", "LA", "PA") or "transparency" in pil.info
            rgba = pil.convert("RGBA") if has_alpha else None
            # cinza continua cinza (1 canal em vez de 3): sem alpha e sem
            # paleta, abrir para RGB so inchava o arquivo e tirava a garantia
            # de que a arte cinza imprime em UMA tinta
            cinza = rgba is None and pil.mode in ("L", "1")
            base = pil.convert("L") if cinza else (rgba or pil).convert("RGB")
            xo = pikepdf.Stream(self._pdf, zlib.compress(base.tobytes()))
            xo.stream_dict = Dictionary(
                Type=Name.XObject, Subtype=Name.Image,
                Width=base.width, Height=base.height,
                ColorSpace=self._colorspace("L" if cinza else "RGB", icc),
                BitsPerComponent=8, Filter=Name.FlateDecode,
            )
            if rgba is not None:
                smask = pikepdf.Stream(
                    self._pdf, zlib.compress(rgba.getchannel("A").tobytes())
                )
                smask.stream_dict = Dictionary(
                    Type=Name.XObject, Subtype=Name.Image,
                    Width=rgba.width, Height=rgba.height,
                    ColorSpace=Name.DeviceGray, BitsPerComponent=8,
                    Filter=Name.FlateDecode,
                )
                xo.SMask = smask
        self._images[path] = xo
        return xo

    def _colorspace(self, modo: str, icc: bytes | None):
        """Espaco de cor do PDF para um modo do Pillow, levando o perfil do
        arquivo quando ele existe e CONFERE com o modo.

        O perfil so entra se o cabecalho ICC declarar o mesmo espaco da
        imagem: perfil trocado (um CMYK colado numa imagem RGB) faz o leitor
        recusar a imagem inteira. Nao batendo, vale o Device — pior que o
        perfil certo, melhor que arquivo que nao abre."""
        device = _DEVICE_DO_MODO[modo]
        if not icc or _espaco_do_perfil(icc) != modo:
            return device
        perfil = pikepdf.Stream(self._pdf, icc)
        perfil.stream_dict = Dictionary(N=_N_DO_MODO[modo], Alternate=device)
        return Array([Name.ICCBased, perfil])

    # ---- espaco de cor das marcas que o PrintNest desenha ----
    def usar_marcas_cmyk(self) -> None:
        """Desenha marcas/facas em K puro (DeviceCMYK 0 0 0 1) em vez de RGB.

        QA-F2A-03: marca de registro em '0 0 0 rg' vira PRETO COMPOSTO no RIP
        (quatro tintas). Composto sai fora de registro e o sensor optico da
        mesa de corte erra a leitura — a marca precisa ser so o canal K. Em
        documento CMYK isso tambem evita misturar objeto RGB num arquivo que
        o resto do fluxo trata como CMYK."""
        self._cmyk_marcas = True

    def _cor(self, color, *, traco: bool) -> str:
        """Operador de cor para o content stream, no espaco das marcas."""
        r, g, b = color
        if not self._cmyk_marcas:
            return f"{_f(r)} {_f(g)} {_f(b)} {'RG' if traco else 'rg'}"
        k = 1.0 - max(r, g, b)
        if k >= 1.0:  # preto puro: SO o canal K (o caso das marcas)
            c = m = y = 0.0
        else:
            c = (1.0 - r - k) / (1.0 - k)
            m = (1.0 - g - k) / (1.0 - k)
            y = (1.0 - b - k) / (1.0 - k)
        return f"{_f(c)} {_f(m)} {_f(y)} {_f(k)} {'K' if traco else 'k'}"

    def copiar_output_intents(self, origem: str) -> bool:
        """Traz o OutputIntent do PDF de origem para o documento de saida.

        O OutputIntent e quem diz QUAL CMYK e aquele CMYK (Coated FOGRA39,
        SWOP, o perfil da grafica...). Sem ele o RIP adivinha o perfil de
        destino, e adivinhar errado desloca a cor da chapa inteira.

        A origem fica em self._sources ate o close(): o pikepdf le o objeto
        copiado de forma preguicosa, e fechar o arquivo antes do save gravaria
        um intent vazio. Devolve True se copiou."""
        try:
            src = self._sources.get(origem)
            if src is None:
                src = pikepdf.open(origem)
                self._sources[origem] = src
            intents = src.Root.get("/OutputIntents")
            if intents is None or len(intents) == 0:
                return False
            # copy_foreign so aceita objeto INDIRETO: o array em si costuma ser
            # direto, entao cada intent e copiado de um em um.
            copiados = [self._pdf.copy_foreign(oi) for oi in intents.as_list()]
            if not copiados:
                return False
            self._pdf.Root.OutputIntents = Array(copiados)
        except Exception:
            return False  # origem sem intent legivel: segue sem, como antes
        return True

    # ---- desenho vetorial (coords topo-esquerda em mm) ----
    def draw_line(
        self, p1_mm, p2_mm, *, width_pt: float = 1.0, color=(0, 0, 0)
    ) -> None:
        x1, y1 = self._pt(*p1_mm)
        x2, y2 = self._pt(*p2_mm)
        self._cur["ops"].append(
            f"q {self._cor(color, traco=True)} {_f(width_pt)} w "
            f"{_f(x1)} {_f(y1)} m {_f(x2)} {_f(y2)} l S Q\n"
        )

    def draw_circle(
        self, center_mm, radius_mm: float, *, color=(0, 0, 0), fill=None,
        width_pt: float = 1.0,
    ) -> None:
        cx, cy = self._pt(*center_mm)
        rr = radius_mm * MM2PT
        k = _K * rr
        ops = [f"q {self._cor(color, traco=True)} {_f(width_pt)} w"]
        if fill is not None:
            ops.append(self._cor(fill, traco=False))
        ops.append(
            f"{_f(cx + rr)} {_f(cy)} m "
            f"{_f(cx + rr)} {_f(cy + k)} {_f(cx + k)} {_f(cy + rr)} {_f(cx)} {_f(cy + rr)} c "
            f"{_f(cx - k)} {_f(cy + rr)} {_f(cx - rr)} {_f(cy + k)} {_f(cx - rr)} {_f(cy)} c "
            f"{_f(cx - rr)} {_f(cy - k)} {_f(cx - k)} {_f(cy - rr)} {_f(cx)} {_f(cy - rr)} c "
            f"{_f(cx + k)} {_f(cy - rr)} {_f(cx + rr)} {_f(cy - k)} {_f(cx + rr)} {_f(cy)} c"
        )
        ops.append("b Q" if fill is not None else "s Q")
        self._cur["ops"].append(" ".join(ops) + "\n")

    def draw_polyline(
        self, points_mm, *, close: bool = False, width_pt: float = 1.0,
        color=(0, 0, 0),
    ) -> None:
        if len(points_mm) < 2:
            return
        pts = [self._pt(x, y) for x, y in points_mm]
        body = f"{_f(pts[0][0])} {_f(pts[0][1])} m " + " ".join(
            f"{_f(x)} {_f(y)} l" for x, y in pts[1:]
        )
        end = "h S Q" if close else "S Q"
        self._cur["ops"].append(
            f"q {self._cor(color, traco=True)} {_f(width_pt)} w {body} {end}\n"
        )

    def draw_bezier_path(
        self, segments_mm, *, close: bool = True, width_pt: float = 1.0,
        color=(0, 0, 0),
    ) -> None:
        """UM caminho continuo de Beziers: segments_mm = [(p0, c1, c2, p1)].
        Fecha e traceja como um unico objeto (a maquina corta sem levantar)."""
        if not segments_mm:
            return
        p0 = self._pt(*segments_mm[0][0])
        body = [f"{_f(p0[0])} {_f(p0[1])} m"]
        for _p0, c1, c2, p1 in segments_mm:
            a = self._pt(*c1)
            bb = self._pt(*c2)
            c = self._pt(*p1)
            body.append(
                f"{_f(a[0])} {_f(a[1])} {_f(bb[0])} {_f(bb[1])} "
                f"{_f(c[0])} {_f(c[1])} c"
            )
        end = "h S Q" if close else "S Q"
        self._cur["ops"].append(
            f"q {self._cor(color, traco=True)} {_f(width_pt)} w "
            + " ".join(body) + f" {end}\n"
        )

    def draw_rect_filled(self, x_mm, y_mm, w_mm, h_mm, color=(0, 0, 0)) -> None:
        x, y = self._pt(x_mm, y_mm + h_mm)  # canto inferior-esquerdo
        self._cur["ops"].append(
            f"q {self._cor(color, traco=False)} {_f(x)} {_f(y)} "
            f"{_f(w_mm * MM2PT)} {_f(h_mm * MM2PT)} re f Q\n"
        )

    # ---- saida ----
    def _flush(self) -> None:
        for entry in self._pages:
            if entry["ops"]:
                entry["page"].contents_add(
                    "".join(entry["ops"]).encode("latin-1")
                )
                entry["ops"] = []
        # o PDF do cliente se assina como PrintNest (antes saia o nome do
        # motor de terceiros)
        self._pdf.docinfo[Name.Producer] = "PrintNest"

    def save(self, path: str) -> None:
        self._flush()
        self._pdf.save(path)

    def save_bytes(self) -> bytes:
        self._flush()
        buf = io.BytesIO()
        self._pdf.save(buf)
        return buf.getvalue()

    def close(self) -> None:
        for src in self._sources.values():
            src.close()
        self._sources.clear()
        self._pdf.close()

    def __enter__(self) -> PdfWriter:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
