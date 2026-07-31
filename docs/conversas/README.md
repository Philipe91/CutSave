# Conversas com o Claude

Toda conversa fica registrada aqui, automaticamente, ao fim de cada sessão.

## Como funciona

Um hook `SessionEnd` (em `.claude/settings.json`) chama
`tools/salvar_conversa.py`, que lê o transcrito da sessão e escreve um markdown
nesta pasta. Não depende de ninguém lembrar de salvar.

**Nome do arquivo:** `AAAA-MM-DD-<8 primeiros caracteres da sessão>.md`

**O que entra:** o que você escreveu, o que o Claude respondeu, e a lista das
ferramentas usadas com a contagem de cada uma.

**O que não entra:** o resultado bruto de cada comando e de cada leitura de
arquivo. É de propósito — o transcrito completo de uma sessão longa passa de
80 MB, e ninguém relê isso. O caminho do transcrito bruto fica anotado no
cabeçalho de cada arquivo, caso um dia você precise do detalhe.

Textos muito longos são cortados no meio, preservando começo e fim, com a
marca de quantos caracteres foram omitidos.

## Refazer na mão

Se um arquivo se perder, ou para converter uma sessão específica:

```powershell
echo '{"session_id":"COLE-O-ID-AQUI"}' | .venv\Scripts\python.exe tools\salvar_conversa.py
```

Os transcritos brutos ficam em
`%USERPROFILE%\.claude\projects\c--projetos-Cutph\`.

> **Atenção ao prazo de validade.** O Claude Code apaga transcritos antigos
> depois de um tempo (30 dias por padrão, ajustável em `cleanupPeriodDays`).
> Os markdowns daqui não são apagados — mas se um transcrito bruto sumir, não
> dá para gerar o markdown dele depois. Por isso o histórico foi convertido de
> uma vez em 31/07/2026, cobrindo desde 25/06.

## Marcos do projeto

Para achar rápido as conversas que decidiram alguma coisa:

| Data | O que aconteceu |
|---|---|
| 25/06 | primeira sessão registrada |
| 15–16/07 | faca do cliente, cartelas |
| 20–24/07 | Modo Corte, nesting true-shape, QA Master |
| 27–28/07 | redesign do painel Peça, travamento com PDF grande |
| 30/07 | **auditoria, release candidate e lançamento da 1.0.0** |
| 31/07 | pós-lançamento, kit de teste, esta regra |

Os relatórios formais da release estão em [`../qa/`](../qa/) — estes arquivos
são o bastidor, não a documentação oficial.
