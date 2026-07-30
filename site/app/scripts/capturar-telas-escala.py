"""Recaptura so a tela de escala (varias chapas) com zoom legivel."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import shots  # noqa: E402  (reusa build_window/make_project/pump/save)


def main():
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtWidgets import QApplication

    from app.presentation.themes import apply_startup

    shots.APP = QApplication(sys.argv)
    apply_startup(shots.APP)

    win = shots.build_window()
    win.resize(1760, 990)
    win.show()
    shots.pump(800)

    proj = shots.make_project(
        "amostra-escala", shots.ARTES_ESCALA, {"material_height": 2000.0}
    )
    win.open_project(proj)
    shots.pump(1500)
    win.generate(blocking=True)
    shots.pump(6000)
    win._organize()
    shots.pump(6000)
    win._view_mode.setCurrentIndex(win._view_mode.findData("print"))
    shots.pump(1500)

    # enquadra so as 3 primeiras chapas: as pecas ficam legiveis
    rect = None
    for item in win._piece_items:
        r = item.sceneBoundingRect()
        rect = r if rect is None else rect.united(r)
    alvo = QRectF(rect.left() - 60, rect.top() - 90,
                  rect.width() * 0.53, rect.height() + 180)
    win._view.fitInView(alvo, Qt.KeepAspectRatio)
    shots.pump(2000)
    shots.save(win, "g2-escala.png")

    (HERE / "log2.txt").write_text("\n".join(shots.LOG), encoding="utf-8")
    os._exit(0)


if __name__ == "__main__":
    main()
