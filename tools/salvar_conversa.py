"""Salva a conversa do Claude Code como markdown legivel em docs/conversas/.

Chamado por um hook SessionEnd (ver .claude/settings.json). Recebe o JSON do
hook na entrada padrao, acha o transcrito .jsonl da sessao e escreve um .md com
o que foi dito — texto do usuario e do assistente, mais a lista de ferramentas
usadas.

Por que nao copiar o .jsonl cru: um transcrito pode passar de 80 MB (todo
resultado de ferramenta vai junto). O markdown fica em dezenas de KB e e o que
alguem consegue reler daqui a seis meses.

Nunca derruba a sessao: qualquer erro vira saida silenciosa com codigo 0.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "docs" / "conversas"
# textos maiores que isso sao cortados no meio (mantem inicio e fim)
LIMITE_TEXTO = 4000


def _achar_transcrito(dados: dict) -> Path | None:
    """O hook manda transcript_path; se nao vier, procura pelo session_id."""
    caminho = dados.get("transcript_path")
    if caminho and Path(caminho).exists():
        return Path(caminho)
    sid = dados.get("session_id")
    if not sid:
        return None
    base = Path.home() / ".claude" / "projects"
    candidatos = list(base.glob(f"*/{sid}.jsonl"))
    return candidatos[0] if candidatos else None


def _texto(conteudo) -> tuple[str, list[str]]:
    """Extrai o texto e os nomes das ferramentas de um bloco de conteudo."""
    if isinstance(conteudo, str):
        return conteudo, []
    partes: list[str] = []
    ferramentas: list[str] = []
    for bloco in conteudo or []:
        if not isinstance(bloco, dict):
            continue
        tipo = bloco.get("type")
        if tipo == "text":
            partes.append(bloco.get("text", ""))
        elif tipo == "tool_use":
            ferramentas.append(str(bloco.get("name", "?")))
    return "\n".join(p for p in partes if p.strip()), ferramentas


def _encurtar(texto: str) -> str:
    if len(texto) <= LIMITE_TEXTO:
        return texto
    corte = LIMITE_TEXTO // 2
    omitido = len(texto) - LIMITE_TEXTO
    return f"{texto[:corte]}\n\n*[... {omitido} caracteres omitidos ...]*\n\n{texto[-corte:]}"


def main() -> int:
    try:
        dados = json.loads(sys.stdin.read() or "{}")
    except Exception:
        dados = {}

    origem = _achar_transcrito(dados)
    if origem is None:
        return 0

    linhas: list[str] = []
    ferramentas_usadas: dict[str, int] = {}
    primeira_data = None
    turnos = 0

    with origem.open(encoding="utf-8", errors="ignore") as fh:
        for linha in fh:
            try:
                item = json.loads(linha)
            except Exception:
                continue
            papel = (item.get("message") or {}).get("role") or item.get("type")
            conteudo = (item.get("message") or {}).get("content")
            if papel not in ("user", "assistant"):
                continue
            texto, ferramentas = _texto(conteudo)
            for f in ferramentas:
                ferramentas_usadas[f] = ferramentas_usadas.get(f, 0) + 1
            if primeira_data is None:
                primeira_data = item.get("timestamp")
            if not texto.strip():
                continue
            # ecos de ferramenta e lembretes do sistema nao sao conversa
            if texto.lstrip().startswith(("<system-reminder", "<local-command")):
                continue
            turnos += 1
            quem = "Philipe" if papel == "user" else "Claude"
            linhas.append(f"### {quem}\n\n{_encurtar(texto.strip())}\n")

    if not linhas:
        return 0

    sid = dados.get("session_id") or origem.stem
    try:
        quando = datetime.fromisoformat(str(primeira_data).replace("Z", "+00:00"))
    except Exception:
        quando = datetime.fromtimestamp(origem.stat().st_mtime)
    dia = quando.strftime("%Y-%m-%d")

    DESTINO.mkdir(parents=True, exist_ok=True)
    saida = DESTINO / f"{dia}-{sid[:8]}.md"

    topo = [
        f"# Conversa de {quando.strftime('%d/%m/%Y')}",
        "",
        f"- **Sessao:** `{sid}`",
        f"- **Inicio:** {quando.strftime('%d/%m/%Y %H:%M')}",
        f"- **Mensagens:** {turnos}",
        f"- **Transcrito bruto:** `{origem}`",
    ]
    if ferramentas_usadas:
        maiores = sorted(ferramentas_usadas.items(), key=lambda kv: -kv[1])[:8]
        topo.append(
            "- **Ferramentas:** "
            + ", ".join(f"{nome} ({n}x)" for nome, n in maiores)
        )
    topo += ["", "---", ""]

    saida.write_text("\n".join(topo) + "\n".join(linhas), encoding="utf-8")
    print(json.dumps({"systemMessage": f"Conversa salva em {saida.name}"}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)  # nunca atrapalhar o fim da sessao
