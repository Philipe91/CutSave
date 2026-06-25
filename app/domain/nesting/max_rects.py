"""MaxRects: empacotamento por retangulos livres (max aproveitamento de chapa).

Implementa o algoritmo MaxRects (Jukka Jylanki) com a heuristica Best Short
Side Fit (BSSF): mantem a lista de retangulos LIVRES da chapa e, para cada peca,
escolhe o espaco livre que sobra mais justo, dividindo o espaco restante. Assim
pecas de tamanhos diferentes preenchem os vaos (ao contrario do grid simples,
que so empilha em linhas e desperdica os buracos).

Mesma interface do GridPacker (pack / pack_sheets), entao e plugavel no
RunGridNestingUseCase sem mexer no resto do motor. NAO rotaciona as pecas (o
desenho/exportacao ainda nao honram rotacao por peca) e usa espacamento >= 0
(negativo = sobreposicao nao se aplica ao MaxRects; tratado como 0).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.geometry import Point2D
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.domain.nesting.grid import NestingPiece

_EPS = 1e-6


@dataclass
class _Rect:
    x: float
    y: float
    w: float
    h: float


class _MaxRectsBin:
    """Uma chapa (bin) de largura x altura fixas; insere retangulos sem sobrepor."""

    def __init__(self, width: float, height: float) -> None:
        self._free: list[_Rect] = [_Rect(0.0, 0.0, width, height)]

    def insert(self, w: float, h: float) -> _Rect | None:
        """Posiciona um retangulo w x h pela heuristica Bottom-Left: o espaco que
        deixa a peca mais EMBAIXO (menor topo), depois mais a esquerda. Minimiza a
        altura usada (otimo para a chapa) e empacota denso. Retorna o retangulo
        posicionado (coords locais) ou None se nao couber em lugar nenhum."""
        best = None
        best_score = (float("inf"), float("inf"))
        for fr in self._free:
            if fr.w + _EPS >= w and fr.h + _EPS >= h:
                score = (fr.y + h, fr.x)  # topo da peca, depois x (bottom-left)
                if score < best_score:
                    best_score = score
                    best = _Rect(fr.x, fr.y, w, h)
        if best is None:
            return None
        self._place(best)
        return best

    def _place(self, used: _Rect) -> None:
        novos: list[_Rect] = []
        for fr in self._free:
            novos.extend(self._split(fr, used))
        self._free = novos
        self._prune()

    @staticmethod
    def _split(fr: _Rect, used: _Rect) -> list[_Rect]:
        """Divide um retangulo livre ao redor do retangulo usado (estilo MaxRects).
        Se nao houver intersecao, devolve o proprio retangulo intacto."""
        # sem intersecao -> intacto
        if (
            used.x >= fr.x + fr.w - _EPS
            or used.x + used.w <= fr.x + _EPS
            or used.y >= fr.y + fr.h - _EPS
            or used.y + used.h <= fr.y + _EPS
        ):
            return [fr]
        out: list[_Rect] = []
        # faixa acima do usado
        if used.y > fr.y + _EPS:
            out.append(_Rect(fr.x, fr.y, fr.w, used.y - fr.y))
        # faixa abaixo do usado
        if used.y + used.h < fr.y + fr.h - _EPS:
            out.append(_Rect(fr.x, used.y + used.h, fr.w, fr.y + fr.h - (used.y + used.h)))
        # faixa a esquerda do usado
        if used.x > fr.x + _EPS:
            out.append(_Rect(fr.x, fr.y, used.x - fr.x, fr.h))
        # faixa a direita do usado
        if used.x + used.w < fr.x + fr.w - _EPS:
            out.append(_Rect(used.x + used.w, fr.y, fr.x + fr.w - (used.x + used.w), fr.h))
        return out

    def _prune(self) -> None:
        """Remove retangulos livres contidos em outros (deduplica o espaco)."""
        keep: list[_Rect] = []
        for i, a in enumerate(self._free):
            if a.w <= _EPS or a.h <= _EPS:
                continue
            contido = False
            for j, b in enumerate(self._free):
                # contido em b (e, se identicos, mantem so o de menor indice)
                if i != j and self._contains(b, a) and not (self._contains(a, b) and j < i):
                    contido = True
                    break
            if not contido:
                keep.append(a)
        self._free = keep

    @staticmethod
    def _contains(outer: _Rect, inner: _Rect) -> bool:
        return (
            inner.x + _EPS >= outer.x
            and inner.y + _EPS >= outer.y
            and inner.x + inner.w <= outer.x + outer.w + _EPS
            and inner.y + inner.h <= outer.y + outer.h + _EPS
        )


class MaxRectsPacker:
    """Empacotador MaxRects: mesma interface do GridPacker, mais aproveitamento.

    pack(pieces, material) -> uma chapa aberta (cresce conforme o conteudo).
    pack_sheets(pieces, material, sheet_length) -> varias chapas de altura fixa.
    """

    @staticmethod
    def _ordered(pieces: Sequence[NestingPiece]) -> list[NestingPiece]:
        # peca maior primeiro (maior lado, depois area): melhora o encaixe.
        return sorted(
            pieces,
            key=lambda p: (max(p.size.width, p.size.height), p.size.width * p.size.height),
            reverse=True,
        )

    def pack(self, pieces: Sequence[NestingPiece], material: Material) -> Layout:
        sp = max(0.0, material.spacing)
        spy = max(0.0, material.spacing_y)
        margin = material.margin
        bin_w = material.usable_width
        ordered = self._ordered(pieces)
        # chapa aberta: altura generosa (soma das alturas) garante caber tudo.
        total_h = sum(p.size.height + spy for p in ordered) + 1.0
        bin_ = _MaxRectsBin(bin_w, max(total_h, 1.0))
        placed: list[PlacedItem] = []
        max_bottom = 0.0
        for piece in ordered:
            rect = bin_.insert(piece.size.width + sp, piece.size.height + spy)
            if rect is None:  # nao deveria ocorrer (altura generosa); empilha abaixo
                rect = _Rect(0.0, max_bottom, piece.size.width, piece.size.height)
            placed.append(PlacedItem(piece.artwork_id, Point2D(margin + rect.x, margin + rect.y)))
            max_bottom = max(max_bottom, rect.y + piece.size.height)
        used_length = (max_bottom + 2 * margin) if placed else 0.0
        return Layout(material=material, items=placed, used_length=used_length)

    def pack_sheets(
        self,
        pieces: Sequence[NestingPiece],
        material: Material,
        sheet_length: float,
    ) -> list[Layout]:
        if sheet_length <= 0:
            return [self.pack(pieces, material)]

        sp = max(0.0, material.spacing)
        spy = max(0.0, material.spacing_y)
        margin = material.margin
        bin_w = material.usable_width
        bin_h = max(sheet_length - 2 * margin, 1.0)

        remaining = self._ordered(pieces)
        sheets: list[Layout] = []
        # trava de seguranca: nunca mais voltas que pecas (evita loop infinito).
        for _ in range(len(remaining) + 1):
            if not remaining:
                break
            bin_ = _MaxRectsBin(bin_w, bin_h)
            placed: list[PlacedItem] = []
            leftover: list[NestingPiece] = []
            for piece in remaining:
                rect = bin_.insert(piece.size.width + sp, piece.size.height + spy)
                if rect is None:
                    leftover.append(piece)
                else:
                    placed.append(
                        PlacedItem(piece.artwork_id, Point2D(margin + rect.x, margin + rect.y))
                    )
            if not placed:
                # nenhuma peca coube numa chapa vazia (maior que a chapa):
                # coloca a primeira assim mesmo (como o grid faz) e segue.
                big = remaining[0]
                placed.append(PlacedItem(big.artwork_id, Point2D(margin, margin)))
                leftover = list(remaining[1:])
            sheets.append(Layout(material, placed, sheet_length))
            remaining = leftover
        return sheets
