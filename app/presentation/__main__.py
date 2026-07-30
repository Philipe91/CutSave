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


_crash_file = None  # handle do crash.log: precisa viver enquanto o app viver

# Nome combinado com o AppMutex do installer/printnest.iss — mudar aqui exige
# mudar la (e so vale a partir da versao que JA tiver criado o mutex).
APP_MUTEX_NAME = "PrintNestAppMutex"
_app_mutexes: list = []  # handles vivos enquanto o processo viver


def _create_app_mutex() -> None:
    """Marca "estou aberto" de um jeito que o INSTALADOR consiga enxergar.

    A instancia unica do app usa QLocalServer, que o Inno Setup nao ve: quem
    instalasse a versao nova com o PrintNest aberto levava erro de arquivo em
    uso no meio da instalacao. Com o mutex, o instalador avisa antes e pede
    para fechar. Falhar aqui nunca pode impedir o app de abrir.

    Cria nos dois espacos de nomes: o "Global\\" e o que o instalador elevado
    enxerga de outra sessao, mas exige privilegio que usuario comum pode nao
    ter — por isso o local tambem, e o .iss verifica os dois."""
    if sys.platform != "win32":
        return
    import ctypes

    for nome in (f"Global\\{APP_MUTEX_NAME}", APP_MUTEX_NAME):
        with contextlib.suppress(Exception):
            handle = ctypes.windll.kernel32.CreateMutexW(None, False, nome)
            if handle:
                _app_mutexes.append(handle)


def _enable_crash_log(logs_dir: Path) -> None:
    """Grava a pilha Python em logs/crash.log quando o processo morre de forma
    violenta (segfault / corrupcao de heap do lado Qt). Esses tombos fecham a
    janela sem escrever NADA no printnest.log — sem isto so sobra o Visualizador
    de Eventos do Windows, que nao diz em que ponto do codigo estavamos."""
    global _crash_file
    import faulthandler

    with contextlib.suppress(OSError):
        _crash_file = (logs_dir / "crash.log").open("a", buffering=1, encoding="utf-8")
        faulthandler.enable(file=_crash_file, all_threads=True)


def _install_excepthook(logs_dir: Path) -> None:
    """Excecao nao tratada num slot do Qt precisa DEIXAR RASTRO.

    Sem isto, com console=False, o Qt so imprime no stderr que ninguem le: a
    acao simplesmente "nao acontece", o printnest.log fica limpo e o suporte
    nao tem por onde comecar. Aqui ela vira CRITICAL no log + um aviso em
    pt-BR que aponta a pasta dos logs.

    Avisa UMA vez por sessao: erro dentro de um paintEvent se repete a cada
    quadro, e uma fila de caixas seria pior que o proprio erro."""
    import logging
    import os
    import traceback

    anterior = sys.excepthook
    estado = {"avisou": False}

    def _hook(tipo, valor, tb) -> None:
        if issubclass(tipo, KeyboardInterrupt):
            anterior(tipo, valor, tb)  # Ctrl+C continua encerrando
            return
        detalhe = "".join(traceback.format_exception(tipo, valor, tb))
        logging.getLogger("printnest").critical("Erro nao tratado:\n%s", detalhe)
        if estado["avisou"] or os.environ.get("PYTEST_CURRENT_TEST"):
            return
        estado["avisou"] = True
        with contextlib.suppress(Exception):  # o aviso nunca pode virar 2o erro
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is None:
                return
            box = QMessageBox()
            box.setWindowTitle("PrintNest")
            box.setIcon(QMessageBox.Warning)
            box.setText("Ocorreu um erro inesperado.")
            box.setInformativeText(
                "O PrintNest continua aberto — salve o seu trabalho.\n"
                f"Os detalhes ficaram em:\n{logs_dir}"
            )
            box.setDetailedText(detalhe)
            box.addButton("Entendi", QMessageBox.AcceptRole)
            box.exec()

    sys.excepthook = _hook


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
    _enable_crash_log(paths.logs_dir)
    _install_excepthook(paths.logs_dir)
    _create_app_mutex()  # o instalador da proxima versao depende disto

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
