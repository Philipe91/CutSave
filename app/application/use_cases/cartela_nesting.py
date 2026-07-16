from __future__ import annotations

import math
from collections.abc import Sequence

from app.application.footprint import artwork_footprint
from app.domain.cut.cartela import CartelaGrid, build_cartela_grid
from app.domain.model.artwork import Artwork
from app.domain.model.layout import Layout
from app.domain.model.material import Material
from app.domain.model.placement import PlacedItem
from app.shared.errors import ValidationError


class CartelaNestingUseCase:
    """Nesting em CARTELAS (fluxo Mimaki + IECHO): encaixa as pecas cartela
    por cartela (cada cartela e uma mini-chapa) e carimba as cartelas na
    chapa, centradas. Mesmo contrato do RunGridNestingUseCase — o resto do
    sistema (preview, impressao, facas) nao percebe a diferenca.
    """

    def __init__(
        self,
        inner_uc,
        cell_w: float,
        cell_h: float,
        gutter: float = 0.0,
        cell_margin: float = 0.0,
    ) -> None:
        self._inner = inner_uc          # nesting real (MaxRects ou grade)
        self._cell_w = cell_w
        self._cell_h = cell_h
        self._gutter = gutter
        self._cell_margin = cell_margin  # respiro entre a peca e o corte da cartela

    def grid_for(self, material: Material, sheet_length: float) -> CartelaGrid:
        grid = build_cartela_grid(
            material.width, sheet_length, self._cell_w, self._cell_h, self._gutter
        )
        if grid is None:
            raise ValidationError(
                "A cartela nao cabe na chapa (confira largura/altura da "
                "cartela e o tamanho da chapa)."
            )
        return grid

    def execute_sheets(
        self,
        artworks: Sequence[Artwork],
        material: Material,
        sheet_length: float,
    ) -> list[Layout]:
        grid = self.grid_for(material, sheet_length)
        cart_material = Material(
            name=f"{material.name}/cartela",
            width=self._cell_w,
            margin=self._cell_margin,
            spacing=material.spacing,
            spacing_y=material.spacing_y,
        )
        # 1) enche cartelas como se fossem chapinhas de altura fixa
        cartelas = self._inner.execute_sheets(artworks, cart_material, self._cell_h)
        # 2) carimba K cartelas por chapa, cada uma no seu slot
        per_sheet = grid.per_sheet or len(cartelas)  # chapa aberta: todas numa
        sheets: list[Layout] = []
        for start in range(0, len(cartelas), max(1, per_sheet)):
            group = cartelas[start:start + per_sheet]
            items: list[PlacedItem] = []
            for slot, cartela in enumerate(group):
                ox, oy = grid.slot_origin(slot)
                items.extend(
                    PlacedItem(
                        it.artwork_id,
                        type(it.position)(ox + it.position.x, oy + it.position.y),
                    )
                    for it in self._centered_in_cell(cartela.items, artworks)
                )
            if sheet_length > 0:
                used = sheet_length
            else:
                rows = max(1, math.ceil(len(group) / grid.cols))
                used = grid.origin_y + rows * grid.cell_h + (rows - 1) * grid.gutter
            sheets.append(Layout(material=material, items=items, used_length=used))
        return sheets

    def _centered_in_cell(
        self, items: Sequence[PlacedItem], artworks: Sequence[Artwork]
    ) -> list[PlacedItem]:
        """CENTRALIZA o conteudo da cartela dentro do corte: o encaixe empacota
        no canto superior esquerdo e as linhas de refile sairiam descentradas
        em relacao as pecas (sobra toda de um lado so)."""
        items = list(items)
        if not items:
            return items
        by_id = {art.id: art for art in artworks}
        xs: list[float] = []
        ys: list[float] = []
        for it in items:
            art = by_id.get(it.artwork_id)
            if art is None:
                return items  # nao da pra medir: mantem como veio
            fp = artwork_footprint(art)
            xs.extend((it.position.x, it.position.x + (fp.max_x - fp.min_x)))
            ys.extend((it.position.y, it.position.y + (fp.max_y - fp.min_y)))
        dx = (self._cell_w - (max(xs) - min(xs))) / 2 - min(xs)
        dy = (self._cell_h - (max(ys) - min(ys))) / 2 - min(ys)
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return items
        return [
            PlacedItem(
                it.artwork_id,
                type(it.position)(it.position.x + dx, it.position.y + dy),
                it.rotation,
            )
            for it in items
        ]


class IdenticalCartelaNestingUseCase(CartelaNestingUseCase):
    """Cartelas IDENTICAS (fluxo classico da grafica): as quantidades da
    tabela definem o conteudo de UMA cartela; a chapa inteira e preenchida
    com copias exatas dela. A Mimaki precisa de UMA faca so (todas iguais)
    e o refile separa as copias com cortes retos centralizados.

    Se o conteudo nao couber numa unica cartela, cai no encaixe sequencial
    da classe mae (cartela por cartela, como antes) — nunca quebra.
    """

    _from_table = True

    def set_from_table(self, from_table: bool) -> None:
        """Origem das instancias: True = tabela (conteudo de 1 cartela);
        False = re-nesting da producao atual (conteudo ja replicado)."""
        self._from_table = bool(from_table)

    def execute_sheets(
        self,
        artworks: Sequence[Artwork],
        material: Material,
        sheet_length: float,
    ) -> list[Layout]:
        grid = self.grid_for(material, sheet_length)
        per = grid.per_sheet or grid.cols  # chapa aberta: uma fileira
        arts = list(artworks)
        if not self._from_table:
            arts = self._per_cartela_content(arts, per)
        cart_material = Material(
            name=f"{material.name}/cartela",
            width=self._cell_w,
            margin=self._cell_margin,
            spacing=material.spacing,
            spacing_y=material.spacing_y,
        )
        cartelas = self._inner.execute_sheets(arts, cart_material, self._cell_h)
        if len(cartelas) != 1:
            # nao coube numa cartela: encaixe sequencial classico (visivel no
            # preview — as cartelas deixam de ser identicas)
            return super().execute_sheets(artworks, material, sheet_length)
        # centraliza a cartela-base no corte ANTES de replicar: todas as
        # copias saem centradas e o refile corta com sobras simetricas
        base_items = self._centered_in_cell(cartelas[0].items, arts)
        items: list[PlacedItem] = []
        for slot in range(per):
            ox, oy = grid.slot_origin(slot)
            items.extend(
                PlacedItem(
                    it.artwork_id,
                    type(it.position)(ox + it.position.x, oy + it.position.y),
                    it.rotation,
                )
                for it in base_items
            )
        if sheet_length > 0:
            used = sheet_length
        else:
            rows = max(1, math.ceil(per / grid.cols))
            used = grid.origin_y + rows * grid.cell_h + (rows - 1) * grid.gutter
        return [Layout(material=material, items=items, used_length=used)]

    @staticmethod
    def _per_cartela_content(arts: list[Artwork], per: int) -> list[Artwork]:
        """Recupera o conteudo de UMA cartela a partir da producao replicada
        (a chapa carrega exatamente 'per' copias na ordem de carimbo). Se o
        cliente editou a chapa (apagou/duplicou peca), a repeticao exata some
        e segue com tudo — o encaixe sequencial assume."""
        if per <= 1 or not arts or len(arts) % per:
            return arts
        chunk = len(arts) // per
        ids = [a.id for a in arts]
        if ids == ids[:chunk] * per:
            return arts[:chunk]
        return arts
