"""Barra de status inferior (estilo CorelDRAW/Affinity).

Mostra, da esquerda para a direita: quantidade de peças e de chapas, área
utilizada (%), e — alinhados a direita — posição do cursor (mm), zoom e modo
de visualização. Atualizado pela janela conforme a produção e o mouse mudam.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QLabel, QProgressBar, QStatusBar

from app.presentation import icons, theme, units

_ICONE = 14


class _IconeDeStatus(QLabel):
    """Icone da barra que se re-renderiza sozinho.

    Antes o pixmap era feito uma vez na montagem: trocar para o tema escuro
    deixava os icones no cinza do tema claro, e num monitor secundario com
    outra escala o pixmap do principal saia borrado (13/10/2026). Agora guarda
    o NOME do icone e repinta na troca de tema e de escala do monitor."""

    def __init__(self, icon_name: str) -> None:
        super().__init__()
        self._icon_name = icon_name
        self.refresh()

    def refresh(self) -> None:
        self.setPixmap(icons.pixmap(
            self._icon_name, theme.TEXT_MUTED, _ICONE,
            dpr=self.devicePixelRatioF(),
        ))

    def changeEvent(self, event) -> None:  # noqa: N802
        # setPixmap nao gera nova troca de paleta: sem laco
        if event.type() in (QEvent.PaletteChange,
                            QEvent.ApplicationPaletteChange,
                            QEvent.DevicePixelRatioChange):
            self.refresh()
        super().changeEvent(event)


class StatusBarController:
    """Cria e atualiza os campos da QStatusBar."""

    def __init__(self, status_bar: QStatusBar) -> None:
        self._bar = status_bar
        self._icones: list[_IconeDeStatus] = []
        self._pieces = self._add_left("layers", "0 peças")
        self._sheets = self._add_left("file-text", "0 chapas")
        self._area = self._add_left("grid-3x3", "0%")
        # permanentes (direita)
        self._mode = self._add_right("eye", "—")
        self._zoom = self._add_right("maximize", "100%")
        self._cursor = self._add_right("ruler", units.fmt_xy(0.0, 0.0))
        # Progresso de tarefa longa (exportacao). Fica escondido ate comecar:
        # sem ele a exportacao de uma chapa pesada parecia travamento.
        self._task = QLabel("")
        self._task.setProperty("role", "caption")
        self._task.setContentsMargins(2, 0, theme.SPACE_SM, 0)
        self._task.hide()
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedWidth(140)
        self._progress.setFixedHeight(10)
        self._progress.setContentsMargins(0, 0, theme.SPACE_MD, 0)
        self._progress.hide()
        self._bar.addWidget(self._task)
        self._bar.addWidget(self._progress)

    def _add_left(self, icon_name: str, text: str) -> QLabel:
        ico = _IconeDeStatus(icon_name)
        self._icones.append(ico)
        label = QLabel(text)
        label.setProperty("role", "caption")
        label.setContentsMargins(2, 0, theme.SPACE_MD, 0)
        self._bar.addWidget(ico)
        self._bar.addWidget(label)
        return label

    def _add_right(self, icon_name: str, text: str) -> QLabel:
        ico = _IconeDeStatus(icon_name)
        self._icones.append(ico)
        label = QLabel(text)
        label.setProperty("role", "caption")
        label.setContentsMargins(2, 0, theme.SPACE_MD, 0)
        self._bar.addPermanentWidget(ico)
        self._bar.addPermanentWidget(label)
        return label

    def refresh_icons(self) -> None:
        """Re-renderiza os icones na cor do tema atual (troca de tema)."""
        for ico in self._icones:
            ico.refresh()

    # ---- atualizacoes ----
    def set_production(self, pieces: int, sheets: int) -> None:
        self._pieces.setText(f"{pieces} peça(s)")
        self._sheets.setText(f"{sheets} chapa(s)")

    def set_area(self, pct: float) -> None:
        self._area.setText(f"{pct:.0f}% usado")

    def set_zoom(self, factor: float) -> None:
        self._zoom.setText(f"{factor * 100:.0f}%")

    def set_cursor(self, x: float, y: float) -> None:
        self._cursor.setText(units.fmt_xy(x, y))

    def set_mode(self, text: str) -> None:
        self._mode.setText(text)

    # ---- progresso de tarefa longa ----
    def start_progress(self, text: str = "") -> None:
        """Mostra o progresso em modo indeterminado (ainda sem fração)."""
        self._task.setText(text)
        self._task.setVisible(bool(text))
        self._progress.setRange(0, 0)  # indeterminado ate a primeira fracao
        self._progress.show()
        self._repaint()

    def set_progress(self, fraction: float, text: str = "") -> None:
        """Atualiza o progresso (0..1). Repinta na hora, sem processEvents:
        processar eventos aqui reentraria na janela no meio da exportacao."""
        if text and text != self._task.text():
            self._task.setText(text)
            self._task.setVisible(True)
        pct = max(0, min(100, int(round(fraction * 100))))
        if pct <= 0:
            self._progress.setRange(0, 0)
        else:
            if self._progress.maximum() == 0:
                self._progress.setRange(0, 100)
            self._progress.setValue(pct)
        self._repaint()

    def end_progress(self) -> None:
        self._progress.hide()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._task.clear()
        self._task.hide()
        self._repaint()

    def _repaint(self) -> None:
        for w in (self._task, self._progress):
            if w.isVisible():
                w.repaint()
