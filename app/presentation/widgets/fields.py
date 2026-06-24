"""Campos de formulario e metricas com espacamento consistente.

- ``labeled(text, widget)``: monta uma coluna [rotulo discreto] + [controle],
  usada para padronizar os ajustes (sem repetir QLabel solto por toda parte).
- ``MeasureField``: exibe uma metrica somente-leitura (rotulo + valor em
  destaque), no estilo das paletas de medida do CorelDRAW/Affinity.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def labeled(text: str, widget: QWidget) -> QWidget:
    """Empacota um controle com um rotulo-legenda acima dele."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    caption = QLabel(text)
    caption.setProperty("role", "caption")
    lay.addWidget(caption)
    lay.addWidget(widget)
    return box


class MeasureField(QWidget):
    """Metrica somente-leitura: um rotulo pequeno e um valor em destaque."""

    def __init__(self, label: str, value: str = "—") -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        self._caption = QLabel(label)
        self._caption.setProperty("role", "caption")
        self._value = QLabel(value)
        self._value.setProperty("role", "metricValue")
        lay.addWidget(self._caption)
        lay.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_label(self, label: str) -> None:
        self._caption.setText(label)
