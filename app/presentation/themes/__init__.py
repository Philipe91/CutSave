"""Theme Engine do PrintNest — camada VISUAL desacoplada (QA/brief 09/07).

Uso:
    from app.presentation.themes import manager, apply_startup
    apply_startup(app)            # no entrypoint (restaura o tema salvo)
    manager().set_theme("dark")   # troca ao vivo
"""

from app.presentation.themes.manager import apply_startup, manager  # noqa: F401
