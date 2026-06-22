from __future__ import annotations

from app.domain.model.layout import Layout


def format_layout(layout: Layout) -> str:
    """Preview logico (texto) do layout de nesting, sem interface grafica."""
    material = layout.material
    lines = [
        f"Material: {material.width:.0f}mm | margem {material.margin:.0f}mm | "
        f"espacamento {material.spacing:.0f}mm",
        f"Pecas: {layout.item_count} | comprimento usado: {layout.used_length:.1f}mm",
    ]
    last_y = None
    row = 0
    for item in layout.items:
        if last_y is None or item.position.y != last_y:
            row += 1
            last_y = item.position.y
            lines.append(f"  -- linha {row} (y={item.position.y:.1f}mm) --")
        lines.append(f"    {item.artwork_id}: x={item.position.x:.1f} y={item.position.y:.1f}")
    return "\n".join(lines)
