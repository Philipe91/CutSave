"""Ponte COM com o CorelDRAW: importa um arquivo na pagina ativa.

E o caminho de volta do Modo Corte ("Enviar p/ Corel", estilo Apply do
eCut): o dialogo grava o SVG do layout organizado e esta ponte manda o
Corel importar — o operador segue manipulando as curvas por la.

COMO importa: rodando a funcao ImportarDoPrintNest da macro PrintNest.bas
via GMSManager.RunMacro. O Layer.Import chamado DIRETO por COM falha no
marshalling dos parametros opcionais (testado no Corel 2023 em 21/07, por
Dispatch tipado, tardio e Invoke cru); de dentro do VBA funciona nativo —
entao a ponte pede para a propria macro importar.

Conexao por Dispatch (nao GetActiveObject: o Corel nao se registra no ROT):
com o Corel aberto, anexa na instancia que esta rodando.
"""

from __future__ import annotations

from app.shared.errors import PrintNestError

# ProgIDs por ordem de preferencia: versionado (2024 = .25) e generico.
_PROGIDS = ("CorelDRAW.Application.25", "CorelDRAW.Application")

# Onde a macro PrintNest pode morar: no CLIENTE o instalador poe o
# PrintNest.gms na pasta GMS (projeto "PrintNest"); na maquina de
# desenvolvimento o modulo vive no GlobalMacros.
_GMS_PROJECTS = ("PrintNest", "GlobalMacros")


class CorelBridgeError(PrintNestError):
    """CorelDRAW indisponivel ou falha ao importar o arquivo nele."""


def _connect():
    try:
        import win32com.client
    except ImportError as exc:  # instalacao sem pywin32: erro claro
        raise CorelBridgeError(
            "Integracao com o CorelDRAW indisponivel nesta instalacao (pywin32)."
        ) from exc
    for progid in _PROGIDS:
        try:
            return win32com.client.Dispatch(progid)
        except Exception:  # noqa: S112 - tenta o proximo ProgID
            continue
    raise CorelBridgeError(
        "CorelDRAW nao encontrado — abra o Corel e tente de novo."
    )


def send_file_to_corel(path: str) -> None:
    """Importa 'path' no documento ativo do CorelDRAW via a macro PrintNest.
    Lanca CorelBridgeError com mensagem amigavel se o Corel nao estiver
    acessivel ou a macro nao estiver instalada/atualizada."""
    app = _connect()
    ok = False
    erro: Exception | None = None
    for project in _GMS_PROJECTS:
        try:
            ok = app.GMSManager.RunMacro(project, "PrintNest.ImportarDoPrintNest", path)
        except Exception as exc:  # projeto ausente nesta instalacao: tenta o outro
            erro = exc
            continue
        if ok:
            return
    if erro is not None and not ok:
        raise CorelBridgeError(
            "A macro do PrintNest nao respondeu no CorelDRAW — rode o "
            "instalador do plugin (ou importe o PrintNest.bas) e tente de novo."
        ) from erro
    raise CorelBridgeError(
        "O CorelDRAW nao conseguiu importar o arranjo (plugin PrintNest "
        "desatualizado? Reinstale o plugin)."
    )
