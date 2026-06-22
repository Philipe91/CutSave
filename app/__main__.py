from __future__ import annotations

import sys

from app import __version__
from app.shared.config import AppPaths, SettingsStore
from app.shared.errors import PrintNestError
from app.shared.logging import get_logger, setup_logging


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada (Composition Root). Inicializa paths, config e logs."""
    paths = AppPaths.default().ensure()
    try:
        settings = SettingsStore(paths.config_file).load_or_create()
    except PrintNestError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    setup_logging(settings.log_level, paths.logs_dir)
    log = get_logger("app")
    log.info("PrintNest %s iniciado", __version__)
    log.info("Idioma: %s | Nivel de log: %s", settings.language, settings.log_level)
    log.info("Diretorio base: %s", paths.home)
    log.info("Inicializacao concluida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
