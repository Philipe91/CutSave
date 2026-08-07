"""Avisos inteligentes: gera mensagens a partir do estado da produção.

Logica PURA (sem Qt), fácil de testar. A interface decide como mostrar (faixa
Alert ou Toast). O nivel e uma string ('info'|'success'|'warning'|'error') que
a UI mapeia para AlertLevel.

Principio: o software nunca falha em silencio. Cada situacao ambigua vira um
aviso claro e, quando possível, acionavel.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.footprint import artwork_footprint
from app.domain.model.artwork import Artwork
from app.domain.model.image_artwork import ImageArtwork
from app.domain.model.material import Material

# Limiar de pontos acima do qual um contorno e considerado "desenho" (não retângulo).
_CONTOUR_POINTS = 5


@dataclass(frozen=True)
class Notice:
    level: str   # 'info' | 'success' | 'warning' | 'error'
    text: str
    code: str    # identificador estavel (para testes e deduplicacao)


def has_traced_image(artworks: Sequence[Artwork]) -> bool:
    """Ha alguma imagem cujo contorno detectado e um desenho (não um retângulo)?"""
    for art in artworks:
        if (
            isinstance(art, ImageArtwork)
            and art.raw_contour is not None
            and len(art.raw_contour.points) > _CONTOUR_POINTS
        ):
            return True
    return False


def oversized_pieces(
    artworks: Sequence[Artwork],
    material: Material,
    *,
    pode_girar: bool = False,
) -> list[str]:
    """Nomes das peças que não cabem na largura útil da chapa.

    Com o giro automático ligado (pode_girar), uma peça que não cabe em pé mas
    cabe deitada NÃO é peça grande demais — o encaixe vai virá-la sozinho.
    Avisar mesmo assim era alarme falso: o cliente lia "não cabe" enquanto a
    peça entrava normalmente (relato de 07/08)."""
    usable = material.usable_width
    too_big = []
    for art in artworks:
        fp = artwork_footprint(art)
        largura = min(fp.width, fp.height) if pode_girar else fp.width
        if largura > usable + 1e-6:
            too_big.append(art.name)
    return too_big


def production_notices(
    *,
    shared_faca: bool,
    artworks: Sequence[Artwork],
    material: Material,
    pode_girar: bool = False,
) -> list[Notice]:
    """Avisos a exibir após montar a produção (faixa Alert)."""
    notices: list[Notice] = []
    if shared_faca and has_traced_image(artworks):
        notices.append(
            Notice(
                "warning",
                "Faca compartilhada transforma o contorno das imagens em um "
                "retângulo. Use 'Faca por peça' para seguir o desenho.",
                "shared_faca_image",
            )
        )
    big = oversized_pieces(artworks, material, pode_girar=pode_girar)
    if big:
        nomes = ", ".join(big[:3]) + ("..." if len(big) > 3 else "")
        # com o giro ligado, mandar "gire a peça" seria conselho vazio: ela já
        # foi girada e mesmo assim não coube
        saida = (
            "Aumente a chapa ou reduza a peça."
            if pode_girar
            else "Aumente a chapa ou gire/reduza a peça."
        )
        notices.append(
            Notice(
                "warning",
                f"Peça maior que a largura útil da chapa: {nomes}. {saida}",
                "oversized",
            )
        )
    return notices


# ---- mensagens pontuais (usadas em ações especificas) ----
NO_SELECTION = Notice("info", "Nenhuma peça selecionada.", "no_selection")
EXPORT_NO_CUT = Notice(
    "warning", "Nada para exportar: nenhuma faca/corte nas chapas.", "export_no_cut"
)


def missing_file(name: str) -> Notice:
    return Notice("error", f"Arquivo não encontrado: {name}. Use 'Substituir'.", "missing_file")
