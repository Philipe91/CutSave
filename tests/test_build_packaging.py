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


def test_spec_configura_a_tela_de_abertura():
    """Splash nativa do PyInstaller (tela de abertura na descompactacao)."""
    spec = (ROOT / "PrintNest.spec").read_text(encoding="utf-8")
    assert "Splash(" in spec, "splash nativa nao configurada no spec"
    assert "assets/splash.png" in spec
    # a splash nativa depende do Tcl/Tk: tkinter NAO pode voltar aos excludes
    # (checa a ENTRADA da lista, com virgula; o comentario do spec cita o nome)
    assert '"tkinter",' not in spec


def test_spec_empacota_o_arquivo_de_exemplo_do_tutorial():
    """O tutorial guiado depende do PDF de exemplo. Se ele nao for junto no
    .exe, o tutorial abre mandando clicar em algo que nao existe — e isso so
    apareceria na maquina de quem instalou, nunca rodando do codigo.

    Reproduz a mesma varredura do spec (assets/**, menos .py) em vez de
    confiar no olho: e assim que da para saber ANTES de empacotar."""
    exemplo = ROOT / "assets" / "exemplo" / "exemplo-printnest.pdf"
    assert exemplo.exists(), "assets/exemplo/exemplo-printnest.pdf sumiu do repo"

    datas = [
        p for p in (ROOT / "assets").rglob("*")
        if p.is_file() and p.suffix.lower() != ".py"
    ]
    assert exemplo in datas, "o spec nao levaria o exemplo para o executavel"

    # o .gitignore tem *.pdf global (arte de cliente): sem a excecao, um clone
    # limpo sai sem o exemplo e a build gera um .exe quebrado
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!assets/exemplo/*.pdf" in gitignore, "excecao do .gitignore sumiu"


def test_build_bat_gera_a_splash():
    bat = (ROOT / "build.bat").read_text(encoding="utf-8")
    assert "make_splash.py" in bat
    assert (ROOT / "assets" / "make_splash.py").exists()
