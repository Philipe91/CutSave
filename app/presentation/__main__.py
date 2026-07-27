from __future__ import annotations

import contextlib
import sys
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QEventLoop, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import __version__
from app.application.use_cases.export_dxf import ExportDxfUseCase
from app.application.use_cases.export_print_pdf import ExportPrintPdfUseCase
from app.application.use_cases.import_image import ImportImageUseCase
from app.application.use_cases.import_pdf import ImportPdfUseCase
from app.application.use_cases.run_production_pipeline import RunProductionPipelineUseCase
from app.infrastructure.exporters.dxf_exporter import DxfExporter
from app.infrastructure.exporters.pikepdf_print_exporter import PikePdfPrintExporter
from app.infrastructure.importers.cv2_image_importer import Cv2ImageImporter
from app.infrastructure.importers.pdfium_importer import PdfiumImporter
from app.infrastructure.rendering.pdfium_renderer import PdfiumPageRenderer
from app.presentation import theme
from app.presentation.main_window import MainWindow
from app.presentation.single_instance import forward_to_running, start_server
from app.shared.config import AppPaths, SettingsStore
from app.shared.logging import setup_logging
from app.shared.resources import resource_path

_FILE_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".webp")

# tempo minimo que a tela de abertura fica visivel (estilo Corel/Photoshop).
# A janela ja e montada por tras; se ficar pronta antes disso, seguramos o
# restante para o cliente ver a marca. Nao ATRASA o trabalho, so o "aparecer".
_SPLASH_MIN_MS = 3000


def _file_args(argv: list[str]) -> list[str]:
    """Caminhos de arquivo passados na linha de comando (ignora flags)."""
    return [
        a for a in argv[1:]
        if not a.startswith("-") and Path(a).suffix.lower() in _FILE_EXTS
    ]


def _cut_mode_arg(argv: list[str]) -> str | None:
    """Caminho apos --modo-corte (macro do CorelDRAW), "" se a flag veio sem
    arquivo, None se a flag nao veio. Distinguir "" de None importa: flag
    sozinha ainda abre o dialogo do Modo Corte, so que vazio."""
    if "--modo-corte" not in argv:
        return None
    index = argv.index("--modo-corte")
    if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
        return argv[index + 1]
    return ""


def _close_pyi_splash() -> None:
    """Fecha a tela de abertura NATIVA do PyInstaller (a que aparece durante a
    descompactacao do .exe). O modulo pyi_splash so existe no executavel
    empacotado; rodando do fonte, nao faz nada."""
    try:
        import pyi_splash  # type: ignore
    except ModuleNotFoundError:
        return
    with contextlib.suppress(Exception):
        pyi_splash.close()


def _make_splash(app: QApplication):
    """Tela de abertura do app (estilo Corel/Photoshop): cobre o tempo de
    montagem da janela principal. Usa o MESMO asset da splash nativa, entao a
    troca e continua. Retorna None se o asset faltar (nunca trava a abertura)."""
    splash_file = resource_path("assets/splash.png")
    if not splash_file.exists():
        return None
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QSplashScreen

    pix = QPixmap(str(splash_file))
    if pix.isNull():
        return None
    splash = QSplashScreen(pix)
    splash.showMessage(
        f"PrintNest {__version__}  ·  Carregando…",
        Qt.AlignBottom | Qt.AlignHCenter, Qt.white,
    )
    splash.show()
    app.processEvents()  # garante que pinte ANTES do trabalho pesado a seguir
    splash._shown_at = QElapsedTimer()
    splash._shown_at.start()
    return splash


def _hold_splash(splash) -> None:
    """Mantem a tela de abertura visivel ate completar _SPLASH_MIN_MS desde que
    ela surgiu. Usa um loop de eventos (nao trava a UI): a splash segue pintada
    e responsiva durante a espera."""
    if splash is None:
        return
    remaining = _SPLASH_MIN_MS - splash._shown_at.elapsed()
    if remaining > 0:
        loop = QEventLoop()
        QTimer.singleShot(int(remaining), loop.quit)
        loop.exec()


def main() -> int:
    paths = AppPaths.default().ensure()
    store = SettingsStore(paths.config_file)
    settings = store.load_or_create()
    setup_logging(settings.log_level, paths.logs_dir)

    app = QApplication(sys.argv)
    # a splash NATIVA (descompactacao do exe) ja cumpriu o papel: a partir daqui
    # quem assume a espera e a QSplashScreen do fluxo normal (ou o proprio
    # dialogo de ativacao). Fechar aqui evita ela ficar atras desses.
    _close_pyi_splash()

    # Modo Corte direto (macro do CorelDRAW): processo proprio, FORA da
    # instancia unica — abre so o dialogo por cima do Corel (como o eCut) e
    # nao mexe na sessao de impressao que estiver aberta.
    cut_pdf = _cut_mode_arg(sys.argv)

    # instância única: se o PrintNest já estiver aberto, entrega os arquivos
    # (ex.: vindos da macro do CorelDRAW) para a sessao atual e encerra.
    file_args = _file_args(sys.argv)
    if cut_pdf is None and forward_to_running(file_args):
        return 0
    # "aqui estou": grava o caminho do executavel para integracoes externas
    # (a macro do CorelDRAW le este arquivo — o cliente nunca configura nada)
    if getattr(sys, "frozen", False):
        with contextlib.suppress(OSError):
            (paths.home / "printnest_path.txt").write_text(
                sys.executable, encoding="utf-8"
            )
    # Theme Engine: restaura o tema salvo do usuário (claro/escuro/midnight/
    # carbon/auto + acento + ajustes) e aplica o QSS global. Entrypoints sem
    # preferências (ex.: License Studio) continuam usando theme.apply(app).
    from app.presentation.themes import apply_startup
    apply_startup(app)
    # icone da janela: .ico multi-tamanho (só o simbolo, nitido em 16/32px);
    # cai para a PNG se o .ico não existir
    icon_file = resource_path("assets/printnest.ico")
    if not icon_file.exists():  # .ico e gerado/ignorado no git; cai no simbolo quadrado
        icon_file = resource_path("assets/printnest_symbol.png")
    app_icon = QIcon(str(icon_file)) if icon_file.exists() else None
    if app_icon is not None:
        app.setWindowIcon(app_icon)

    # licenciamento: no executavel empacotado, sem licenca valida o app NAO
    # abre (mostra a ativacao; fechar = sair). Rodando do fonte (dev/testes)
    # nao trava. A garantia de 7 dias e comercial, nao vive aqui.
    if getattr(sys, "frozen", False):
        from app.licensing.manager import LicenseManager
        from app.presentation.licensing_dialog import ActivationDialog

        lic = LicenseManager(paths)
        if not lic.is_licensed():
            dlg = ActivationDialog(lic, blocking=True)
            if app_icon is not None:
                dlg.setWindowIcon(app_icon)
            dlg.exec()
            if not lic.is_licensed():
                return 0  # nao ativou -> encerra

    if cut_pdf is not None:
        # so o dialogo do Modo Corte, sem MainWindow: parte mais rapido e o
        # operador continua "no Corel" — importa o PDF exportado pela macro
        # e ja comeca a organizar sozinho.
        from app.presentation.cut_mode_dialog import CutModeDialog

        dialog = CutModeDialog()
        if app_icon is not None:
            dialog.setWindowIcon(app_icon)
        dialog.show()
        if cut_pdf:
            dialog.open_with_file(cut_pdf)
        return app.exec()

    # tela de abertura enquanto a janela e montada (fluxo normal so — nao entra
    # no --modo-corte, que ja retornou acima, nem no --selftest, que nem chega
    # na GUI). Some sozinha quando a janela aparece (splash.finish).
    splash = _make_splash(app)

    pipeline = RunProductionPipelineUseCase(
        ImportPdfUseCase(PdfiumImporter()),
        image_uc=ImportImageUseCase(Cv2ImageImporter(paths.cache_dir)),
    )
    window = MainWindow(
        pipeline,
        ExportPrintPdfUseCase(PikePdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PdfiumPageRenderer(),
        store,
        settings,
    )
    if app_icon is not None:
        window.setWindowIcon(app_icon)  # garante a logo na barra de título

    # primeira instância: escuta caminhos de outras chamadas (CorelDRAW/CLI).
    # guarda a referência no app para não ser coletado pelo GC.
    app._ipc_server = start_server(window.open_external_files)

    # janela ja montada por tras da splash; segura o restante dos ~3s antes de
    # revelar (a tela de abertura fica visivel o tempo combinado).
    _hold_splash(splash)

    # abre MAXIMIZADO: na primeira execução a janela vinha num tamanho solto
    # e o cliente "ficava perdido" (beta 13/07). Padrão de software gráfico:
    # ocupa o monitor inteiro; o usuário restaura/redimensiona se quiser.
    window.showMaximized()
    if splash is not None:
        splash.finish(window)  # some quando a janela ja esta na tela
    if file_args:  # arquivos passados na linha de comando -> abre já na sessao
        window.open_external_files(file_args)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
