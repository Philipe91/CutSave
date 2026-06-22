from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.domain.model.artwork import Artwork
from app.domain.model.material import Material
from app.shared.errors import ValidationError


@dataclass
class Project:
    """Aggregate root da sessao de trabalho.

    Mutavel por natureza: acumula artes e mantem o material selecionado ao
    longo da operacao. As demais entidades sao value objects imutaveis.
    """

    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
    material: Material | None = None
    artworks: list[Artwork] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("Project requer nome.")

    def add_artwork(self, artwork: Artwork) -> None:
        if self.get_artwork(artwork.id) is not None:
            raise ValidationError(f"Artwork duplicada no projeto: {artwork.id}")
        self.artworks.append(artwork)

    def remove_artwork(self, artwork_id: str) -> None:
        artwork = self.get_artwork(artwork_id)
        if artwork is None:
            raise ValidationError(f"Artwork inexistente: {artwork_id}")
        self.artworks.remove(artwork)

    def get_artwork(self, artwork_id: str) -> Artwork | None:
        return next((a for a in self.artworks if a.id == artwork_id), None)

    def set_material(self, material: Material) -> None:
        self.material = material
