from __future__ import annotations

from dataclasses import dataclass

from app.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class Material:
    """Perfil de material. Todas as medidas em milimetros."""

    name: str
    width: float
    margin: float = 0.0
    spacing: float = 0.0
    default_offset: float = 0.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("Material requer nome.")
        if self.width <= 0:
            raise ValidationError("Largura do material deve ser positiva (mm).")
        if self.margin < 0 or self.spacing < 0:
            raise ValidationError("Margem e espacamento nao podem ser negativos (mm).")
        if 2 * self.margin >= self.width:
            raise ValidationError("Margens consomem toda a largura util do material.")

    @property
    def usable_width(self) -> float:
        """Largura disponivel para pecas, descontando as margens laterais."""
        return self.width - 2 * self.margin
