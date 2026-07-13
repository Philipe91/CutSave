"""Tour de boas-vindas — o "tutor" dentro do PrintNest.

Na PRIMEIRA abertura (e depois em Ajuda → Tour de boas-vindas), um guia passo a
passo escurece a tela, ilumina o controle da vez e explica em 1-2 frases o que
fazer — o operador aprende o fluxo inteiro (adicionar → gerar faca → exportar)
sem manual e sem vídeo.

Camada 100% visual: um QWidget-overlay por cima da janela; nada de lógica do
app é alterada. O "já vi" fica em QSettings (mesmo escopo do Theme Engine).
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, QSettings, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.presentation import theme

_ORG, _APP = "PrintNest", "PrintNestPremium"
_DONE_KEY = "tour/concluido"


@dataclass
class TourStep:
    """Um passo do tour: alvo (widget ou None = centro), título e texto."""

    target: QWidget | None
    title: str
    text: str


def tour_done() -> bool:
    return str(QSettings(_ORG, _APP).value(_DONE_KEY, "")) == "1"


def mark_tour_done() -> None:
    QSettings(_ORG, _APP).setValue(_DONE_KEY, "1")


class TourOverlay(QWidget):
    """Véu escuro com "janela" iluminando o alvo + balão explicativo."""

    def __init__(self, window: QWidget, steps: list[TourStep]) -> None:
        super().__init__(window)
        self._steps = [s for s in steps if s.target is None or s.target is not None]
        self._index = 0
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(window.rect())

        # balão (card) com título, texto, progresso e botões
        self._card = QFrame(self)
        self._card.setObjectName("tourCard")
        self._card.setStyleSheet(
            f"#tourCard {{ background: {theme.SURFACE}; border: 1px solid "
            f"{theme.BORDER_STRONG}; border-radius: {theme.RADIUS_CARD}px; }}"
        )
        lay = QVBoxLayout(self._card)
        lay.setContentsMargins(theme.SPACE_LG, theme.SPACE_MD,
                               theme.SPACE_LG, theme.SPACE_MD)
        lay.setSpacing(theme.SPACE_SM)
        self._title = QLabel()
        self._title.setProperty("role", "sectionTitle")
        self._body = QLabel()
        self._body.setWordWrap(True)
        self._body.setProperty("role", "caption")
        self._body.setMinimumWidth(300)
        self._dots = QLabel()
        self._dots.setProperty("role", "hint")
        lay.addWidget(self._title)
        lay.addWidget(self._body)
        row = QHBoxLayout()
        row.setSpacing(theme.SPACE_SM)
        self._skip = QPushButton("Pular tour")
        self._skip.clicked.connect(self._finish)
        self._next = QPushButton("Próximo")
        self._next.setProperty("accent", "true")
        self._next.clicked.connect(self.advance)
        row.addWidget(self._dots)
        row.addStretch()
        row.addWidget(self._skip)
        row.addWidget(self._next)
        lay.addLayout(row)

        self._apply_step()
        self.show()
        self.raise_()

    # ---- fluxo ----
    def advance(self) -> None:
        self._index += 1
        if self._index >= len(self._steps):
            self._finish()
            return
        self._apply_step()

    def _finish(self) -> None:
        mark_tour_done()
        self.hide()
        self.deleteLater()

    # ---- desenho ----
    def _current_hole(self) -> QRect | None:
        step = self._steps[self._index]
        if step.target is None or not step.target.isVisible():
            return None
        top_left = step.target.mapTo(self.parentWidget(), step.target.rect().topLeft())
        r = QRect(top_left, step.target.rect().size())
        return r.adjusted(-6, -6, 6, 6)

    def _apply_step(self) -> None:
        step = self._steps[self._index]
        self._title.setText(step.title)
        self._body.setText(step.text)
        self._dots.setText(f"{self._index + 1} de {len(self._steps)}")
        self._next.setText(
            "Concluir" if self._index == len(self._steps) - 1 else "Próximo"
        )
        self._card.adjustSize()
        self._place_card()
        self.update()

    def _place_card(self) -> None:
        area = self.rect()
        hole = self._current_hole()
        card = self._card.sizeHint()
        margin = theme.SPACE_LG
        if hole is None:
            x = (area.width() - card.width()) // 2
            y = (area.height() - card.height()) // 2
        else:
            # abaixo do alvo; se não couber, acima; sempre dentro da janela
            x = min(max(hole.left(), margin), area.width() - card.width() - margin)
            y = hole.bottom() + margin
            if y + card.height() > area.height() - margin:
                y = max(margin, hole.top() - card.height() - margin)
        self._card.move(int(x), int(y))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        veil = QPainterPath()
        veil.addRect(self.rect())
        hole = self._current_hole()
        if hole is not None:
            buraco = QPainterPath()
            buraco.addRoundedRect(hole, 10, 10)
            veil = veil.subtracted(buraco)
        painter.fillPath(veil, QColor(0, 0, 0, 150))
        if hole is not None:
            painter.setPen(QColor(theme.ACCENT))
            painter.drawRoundedRect(hole, 10, 10)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_card()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # clicar fora do balão avança (comportamento padrão de tours)
        if not self._card.geometry().contains(event.position().toPoint()):
            self.advance()
