"""Testes da configuracao de empacotamento (Etapa 2 - build de producao).

Nao geram a build (isso e feito por build.bat); validam os artefatos de
configuracao e o self-test do ponto de entrada do executavel.
"""

import subprocess
import sys
from pathlib import Path

from app.shared.resources import resource_path

ROOT = Path(__file__).resolve().parents[1]


def test_resource_path_no_dev_aponta_para_a_raiz():
    assert resource_path("assets/printnest.ico") == ROOT / "assets" / "printnest.ico"


def test_resource_path_usa_meipass_no_executavel(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_path("assets/printnest.ico") == tmp_path / "assets" / "printnest.ico"


def test_arquivos_de_build_existem():
    for name in ("PrintNest.spec", "build.bat", "clean.bat", "printnest_main.py"):
        assert (ROOT / name).exists(), f"faltando {name}"


def test_spec_empacota_o_icone_e_o_entrypoint():
    spec = (ROOT / "PrintNest.spec").read_text(encoding="utf-8")
    assert "printnest_main.py" in spec
    assert "printnest.ico" in spec
    assert "console=False" in spec  # janela (windowed), sem console


def test_build_bat_usa_o_spec():
    bat = (ROOT / "build.bat").read_text(encoding="utf-8")
    assert "PrintNest.spec" in bat


def test_selftest_do_entrypoint_passa():
    """Roda o mesmo self-test que valida o executavel, mas via Python do dev."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "printnest_main.py"), "--selftest"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SELFTEST OK" in proc.stdout
