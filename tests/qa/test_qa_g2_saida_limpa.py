"""QA G2 — a suite tem que sair LIMPA, nao so verde.

POR QUE ESTE TESTE EXISTE
-------------------------
O relatorio de assercoes e o codigo de saida do processo sao duas evidencias
INDEPENDENTES, e a suite ja mentiu nas duas direcoes:

  - Verde e sujo: os modulos do Modo Corte fecham com "12 passed" e o processo
    morre em seguida com 0xC0000005 (SIGSEGV / exit 139). Quem le so o resumo
    do pytest conclui que esta tudo bem.
  - Sujo e verde: o desarme do QA-11 (pytest_unconfigure -> TerminateProcess)
    existe justamente para o exit code NAO mentir quando o Qt crasha no
    detach das DLLs. Se o crash acontece ANTES desse desarme, ele nao protege.

Um crash no encerramento nao e ruido de teste: e um objeto C++ sendo liberado
fora de ordem.

NAO CONFUNDA COM O CRASH DO EXECUTAVEL. Sao dois defeitos distintos:
  - este (BUG-QA-1): 0xC0000005, acesso invalido, so na suite, causa provada
    (eventos DeferredDelete nunca drenados — ver tests/conftest.py). FECHADO.
  - o do cliente: 0xC0000374, corrupcao de heap, no .exe, SEM reprodutor e sem
    causa provada. Continua ABERTO e rastreado a parte.
Corrigir um nao corrige o outro.

COMO FUNCIONA
-------------
Cada modulo roda em um PROCESSO SEPARADO. Processo separado e a unica forma de
observar o codigo de saida de um modulo: rodando tudo junto, o primeiro crash
derruba a sessao inteira e some com o resto. Exigimos as DUAS coisas:

  1. JUnit verde  -> assercoes passaram, e passaram em quantidade > 0
  2. returncode 0 -> o processo terminou de pe

O item 2 e o que este arquivo acrescenta. O item 1 esta aqui para o teste nao
passar vazio: um modulo que nao coleta nada tambem sai com 0.
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Modulos que exercitam o Modo Corte de ponta a ponta (dialogo, entrada e
# manipulacao). Sao os que hoje reproduzem o BUG-QA-1. Ao corrigir o defeito,
# NAO remova nenhum daqui: e esta lista que impede a regressao voltar calada.
MODULOS = [
    "tests/presentation/test_cut_mode_dialog.py",
    "tests/presentation/test_cut_mode_entry.py",
    "tests/presentation/test_cut_mode_manip.py",
]


def _rodar_modulo(modulo: str, junit: str) -> subprocess.CompletedProcess:
    """Roda UM modulo em processo separado, com relatorio JUnit em disco.

    -p no:cacheprovider: o subprocesso nao mexe no .pytest_cache do processo
    que o chamou (senao o cache de 'ultimos que falharam' vira lixo).
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            modulo,
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junit-xml={junit}",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )


def _ler_junit(caminho: str) -> tuple[int, int, int]:
    """Devolve (testes, falhas, erros) somando os <testsuite> do relatorio."""
    raiz = ET.parse(caminho).getroot()
    suites = raiz.iter("testsuite")
    testes = falhas = erros = 0
    for s in suites:
        testes += int(s.get("tests", 0))
        falhas += int(s.get("failures", 0))
        erros += int(s.get("errors", 0))
    return testes, falhas, erros


@pytest.mark.parametrize("modulo", MODULOS)
def test_modulo_do_modo_corte_sai_limpo(modulo, tmp_path):
    junit = str(tmp_path / "junit.xml")
    proc = _rodar_modulo(modulo, junit)

    assert os.path.exists(junit), (
        f"{modulo}: o pytest nem chegou a escrever o JUnit.\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    testes, falhas, erros = _ler_junit(junit)

    assert testes > 0, f"{modulo}: nenhum teste coletado — gate passando vazio."
    assert falhas == 0 and erros == 0, (
        f"{modulo}: {falhas} falha(s) e {erros} erro(s).\n{proc.stdout}"
    )

    # A partir daqui as assercoes passaram. O que sobra e o processo em si.
    assert proc.returncode == 0, (
        f"{modulo}: {testes} teste(s) passaram, mas o PROCESSO morreu com "
        f"returncode={proc.returncode} "
        f"(139/0xC0000005 = acesso invalido de memoria no encerramento).\n"
        f"Verde no relatorio nao basta: um objeto C++ esta sendo liberado fora "
        f"de ordem, e o mesmo defeito derruba o .exe do cliente.\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
