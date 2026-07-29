"""Tour de boas-vindas — o "tutor" dentro do PrintNest.

Na PRIMEIRA abertura (e depois em Ajuda → Tour de boas-vindas), um guia passo a
passo escurece a tela, ilumina o controle da vez e explica em 1-2 frases o que
fazer — o operador aprende o fluxo inteiro (adicionar → gerar faca → exportar)
sem manual e sem vídeo.

Camada 100% visual: um QWidget-overlay por cima da janela; nada de lógica do
app é alterada. O "já vi" fica em QSettings (mesmo escopo do Theme Engine).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QRect, QSettings, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QRegion
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
    """Um passo do tour: alvo (widget ou None = centro), título e texto.

    `espera` transforma o passo em MÃO NA MASSA: em vez do botão "Próximo",
    o véu abre um buraco CLICÁVEL sobre o alvo e o passo só avança quando o
    sinal dispara (ou seja, quando o aluno faz de verdade). Recebe um sinal já
    ligado ao widget, por exemplo `window._btn_place.clicked`.

    `quando` filtra esse sinal: o passo só avança se a função devolver True.
    Serve para exigir a escolha CERTA e não qualquer mexida. Um combo dispara
    currentIndexChanged em qualquer opção; com `quando` o tutorial só segue
    quando o aluno escolheu a que foi pedida.
    """

    target: QWidget | None
    title: str
    text: str
    espera: object | None = None
    quando: object | None = None


def tour_done() -> bool:
    return str(QSettings(_ORG, _APP).value(_DONE_KEY, "")) == "1"


def mark_tour_done() -> None:
    QSettings(_ORG, _APP).setValue(_DONE_KEY, "1")


class TourOverlay(QWidget):
    """Véu escuro com "janela" iluminando o alvo + balão explicativo."""

    def __init__(
        self, window: QWidget, steps: list[TourStep], *, mark_done: bool = True
    ) -> None:
        super().__init__(window)
        self._steps = [s for s in steps if s.target is None or s.target is not None]
        self._index = 0
        # mark_done=False: os tutoriais do menu Tutoriais reusam este overlay mas
        # NAO podem marcar o tour de boas-vindas como visto — quem abriu um
        # tutorial de recurso continua recebendo o tour na primeira abertura.
        self._mark_done = mark_done
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(window.rect())
        # o overlay e filho da janela, mas filho NAO acompanha o resize do pai
        # sozinho: sem isto, redimensionar no meio do tour deixava o veu do
        # tamanho antigo (faixa clara na borda e furo fora de lugar)
        window.installEventFilter(self)

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
        # passo mão na massa não tem "Próximo" (o aluno tem de fazer), mas
        # precisa de saída: sem isto, um controle que não abriu prenderia o
        # tutorial para sempre
        self._skip_step = QPushButton("Pular este passo")
        self._skip_step.clicked.connect(self.advance)
        self._next = QPushButton("Próximo")
        self._next.setProperty("accent", "true")
        self._next.clicked.connect(self.advance)
        row.addWidget(self._dots)
        row.addStretch()
        row.addWidget(self._skip)
        row.addWidget(self._skip_step)
        row.addWidget(self._next)
        lay.addLayout(row)

        self._conexao = None  # sinal do passo mão na massa, para desconectar
        self._apply_step()
        self.show()
        self.raise_()

    # ---- fluxo ----
    def advance(self) -> None:
        self._desconectar()
        self._index += 1
        if self._index >= len(self._steps):
            self._finish()
            return
        self._apply_step()

    def _avancar_se(self, *_args) -> None:
        """Avança só quando o passo pediu a escolha CERTA (TourStep.quando).

        O `*_args` existe porque o sinal costuma mandar o valor junto
        (currentIndexChanged manda o índice) e o slot precisa aceitar."""
        quando = self._steps[self._index].quando
        if quando is None or quando():
            self.advance()

    def _desconectar(self) -> None:
        """Solta o sinal do passo mão na massa (senão ele avançaria de novo
        num passo posterior, ou depois do tutorial fechado)."""
        if self._conexao is None:
            return
        sinal, slot = self._conexao
        self._conexao = None
        with contextlib.suppress(RuntimeError, TypeError):  # widget destruído / já solto
            sinal.disconnect(slot)

    def _finish(self) -> None:
        self._desconectar()
        self.clearMask()
        if self._mark_done:
            mark_tour_done()
        parent = self.parentWidget()
        if parent is not None:
            parent.removeEventFilter(self)
        self.hide()
        self.deleteLater()

    def eventFilter(self, obj, event):  # noqa: N802
        """Acompanha o resize da janela (ver installEventFilter no __init__)."""
        if obj is self.parentWidget() and event.type() == QEvent.Resize:
            self.setGeometry(obj.rect())
        return super().eventFilter(obj, event)

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
        interativo = step.espera is not None
        self._next.setVisible(not interativo)
        self._skip_step.setVisible(interativo)
        if interativo:
            slot = self.advance if step.quando is None else self._avancar_se
            self._conexao = (step.espera, slot)
            step.espera.connect(slot)
        self._card.adjustSize()
        self._place_card()
        self._aplicar_mascara()
        self.update()

    def _aplicar_mascara(self) -> None:
        """No passo mão na massa, RECORTA o buraco para fora do overlay: o
        clique atravessa e chega no controle de verdade. Nos passos narrados o
        véu continua inteiro (clicar em qualquer lugar avança)."""
        hole = self._current_hole()
        if self._steps[self._index].espera is None or hole is None:
            self.clearMask()
            return
        self.setMask(QRegion(self.rect()).subtracted(QRegion(hole)))

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
        self._aplicar_mascara()  # o buraco clicável muda de lugar com o layout

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # clicar fora do balão avança (comportamento padrão de tours) — MENOS
        # no passo mão na massa, onde avançar sem fazer mataria o exercício
        if self._steps[self._index].espera is not None:
            return
        if not self._card.geometry().contains(event.position().toPoint()):
            self.advance()
