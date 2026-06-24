"""Avisos inteligentes: gera mensagens a partir do estado da producao.

Logica PURA (sem Qt), facil de testar. A interface decide como mostrar (faixa
Alert ou Toast). O nivel e uma string ('info'|'success'|'warning'|'error') que
a UI mapeia para AlertLevel.

Principio: o software nunca falha em silencio. Cada situacao ambigua vira um
aviso claro e, quando possivel, acionavel.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.footprint import artwork_footprint
from app.domain.model.artwork import Artwork
from app.domain.model.image_artwork import ImageArtwork
from app.domain.model.material import Material

# Limiar de pontos acima do qual um contorno e considerado "desenho" (nao retangulo).
_CONTOUR_POINTS = 5


@dataclass(frozen=True)
class Notice:
    level: str   # 'info' | 'success' | 'warning' | 'error'
    text: str
    code: str    # identificador estavel (para testes e deduplicacao)


def has_traced_image(artworks: Sequence[Artwork]) -> bool:
    """Ha alguma imagem cujo contorno detectado e um desenho (nao um retangulo)?"""
    for art in artworks:
        if (
            isinstance(art, ImageArtwork)
            and art.raw_contour is not None
            and len(art.raw_contour.points) > _CONTOUR_POINTS
        ):
            return True
    return False


def oversized_pieces(artworks: Sequence[Artwork], material: Material) -> list[str]:
    """Nomes das pecas que nao cabem na largura util da chapa."""
    usable = material.usable_width
    too_big = []
    for art in artworks:
        if artwork_footprint(art).width > usable + 1e-6:
            too_big.append(art.name)
    return too_big


def production_notices(
    *,
    shared_faca: bool,
    artworks: Sequence[Artwork],
    material: Material,
) -> list[Notice]:
    """Avisos a exibir apos montar a producao (faixa Alert)."""
    notices: list[Notice] = []
    if shared_faca and has_traced_image(artworks):
        notices.append(
            Notice(
                "warning",
                "Faca compartilhada transforma o contorno das imagens em um "
                "retangulo. Use 'Faca por peca' para seguir o desenho.",
                "shared_faca_image",
            )
        )
    big = oversized_pieces(artworks, material)
    if big:
        nomes = ", ".join(big[:3]) + ("..." if len(big) > 3 else "")
        notices.append(
            Notice(
                "warning",
                f"Peca maior que a largura util da chapa: {nomes}. "
                "Aumente a chapa ou gire/reduza a peca.",
                "oversized",
            )
        )
    return notices


# ---- mensagens pontuais (usadas em acoes especificas) ----
NO_SELECTION = Notice("info", "Nenhuma peca selecionada.", "no_selection")
EXPORT_NO_CUT = Notice(
    "warning", "Nada para exportar: nenhuma faca/corte nas chapas.", "export_no_cut"
)


def missing_file(name: str) -> Notice:
    return Notice("error", f"Arquivo nao encontrado: {name}. Use 'Substituir'.", "missing_file")
