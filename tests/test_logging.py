import logging

from app.shared.logging import get_logger, setup_logging


def test_setup_grava_arquivo_de_log(tmp_path):
    setup_logging("INFO", tmp_path)
    get_logger("teste").info("mensagem de teste")
    for handler in logging.getLogger().handlers:
        handler.flush()
    log_file = tmp_path / "printnest.log"
    assert log_file.exists()
    assert "mensagem de teste" in log_file.read_text(encoding="utf-8")


def test_setup_e_idempotente(tmp_path):
    setup_logging("INFO", tmp_path)
    setup_logging("DEBUG", tmp_path)
    root = logging.getLogger()
    assert len(root.handlers) == 2  # console + arquivo, sem duplicar
    assert root.level == logging.DEBUG
