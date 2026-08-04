> **RODADA SUPERADA — 04/08/2026.** Este arquivo fica como registro histórico da
> rodada que **reprovou**; nada aqui foi reescrito.
>
> O **BUG-QA-1 está FECHADO** com causa provada (eventos `DeferredDelete` nunca
> drenados — não era geometria) e o **G2 foi aprovado**. Ver
> `docs/qa/RELATORIO-QA-1.1.2-2026-08-04.md`.
>
> Duas ressalvas ao ler o que está abaixo:
> - o **fechamento inesperado do executável (`0xc0000374`) continua ABERTO**. É
>   um defeito **diferente** do `0xC0000005` descrito aqui, e não foi corrigido.
> - onde este relatório e o dossiê atribuíam o crash ao **GEOS/Shapely**, está
>   errado: o motor de encaixe usa **pyclipper**.

# PrintNest Pro - relatorio de QA 1.1.1

Data da execucao: 04/08/2026  
Branch: `release/1.0.1`  
Commit: `0ceefc3`  
Ambiente: Windows 10 Pro 64 bits `10.0.19045`, Python `3.10.11`, pytest `9.1.1`, PySide6 `6.11.1`  
Bateria: `docs/qa/BATERIA-DE-TESTES-1.1.1-2026-08-04.md`

## Resumo executivo

A linha de base automatizada coletou 1.030 testes. Foram 1.025 assercoes
aprovadas e 5 riscos conhecidos mantidos como `xfail`; nao houve falha de
assercao nem erro registrado nos arquivos JUnit.

Apesar disso, a execucao nao esta verde: 2 dos 16 modulos de apresentacao
encerraram o processo Python com violacao de acesso do Windows
(`0xC0000005`) depois de registrar 100% das assercoes como aprovadas. Os dois
modulos exercitam o Modo Corte, e o crash foi reproduzido em uma segunda
rodada.

Resultado da rodada: **reprovado**. O gate G2 (estabilidade do Modo Corte)
nao pode ser aprovado, e os gates que exigem verificacao manual, instalador e
CorelDRAW real ainda estao pendentes.

## Resultado automatizado

| Grupo | Testes | Aprovados | Falhas | Erros | Xfail | Tempo JUnit | Processo |
|---|---:|---:|---:|---:|---:|---:|---|
| Base sem `tests/presentation` | 709 | 704 | 0 | 0 | 5 | 265,236 s | aprovado |
| Apresentacao, 16 modulos isolados | 321 | 321 | 0 | 0 | 0 | 131,829 s | 14 aprovados, 2 com crash |
| Total | 1.030 | 1.025 | 0 | 0 | 5 | 397,065 s | reprovado |

Modulos que encerraram com `-1073741819` (`0xC0000005`):

- `tests/presentation/test_cut_mode_dialog.py`: 29/29 assercoes aprovadas;
- `tests/presentation/test_cut_mode_manip.py`: 12/12 assercoes aprovadas.

Cada modulo foi repetido com `PYTHONFAULTHANDLER=1` e `-X faulthandler`. O
crash se repetiu, mas nao produziu pilha Python, o que e compativel com falha
em codigo nativo/Qt durante o encerramento. Um teste individual de cada
arquivo encerrou com codigo zero; a falha aparece na execucao acumulada do
modulo.

## Riscos conhecidos (`xfail`)

| ID | Area | Risco ainda presente |
|---|---|---|
| QA-F2A-03a | PDF de impressao | marcas de registro usam preto RGB, nao K puro |
| QA-F2A-03b | PDF de impressao | operadores PDF das marcas nao usam canal K |
| QA-F3-16b | Instancia unica | entrega pode perder caminhos no mesmo processo/thread |
| QA-F3-13b | Projeto/configuracao | `ConfigError` pode escapar sem dialogo amigavel ao salvar configuracao |
| QA-F3-15 | UI/zoom | zoom extremo nao possui limite minimo/maximo |

## Gates

| Gate | Estado | Evidencia desta rodada |
|---|---|---|
| G1 - arte e faca | parcial | testes automatizados de posicionamento e exportacao passaram; amostras assimetricas e medicao externa pendentes |
| G2 - crash no Modo Corte | reprovado | dois modulos encerram com `0xC0000005`, reproduzido duas vezes |
| G3 - estado por peca | parcial | testes automatizados de giro, abas, undo/redo e round-trip passaram; roteiro manual pendente |
| G4 - primeira abertura | pendente | exige instalacao limpa e perfil novo |
| G5 - CorelDRAW | pendente | exige CorelDRAW real nas versoes suportadas |
| G6 - exportacoes | parcial | PDF, DXF, SVG e fluxos automatizados passaram; validacao externa dos artefatos pendente |
| G7 - telas pequenas | parcial | testes Qt de layout passaram; varredura visual em escalas reais pendente |

## BUG-QA-1 - processo cai ao encerrar modulos do Modo Corte

Severidade: alta para a confiabilidade da bateria; impacto no executavel real
ainda nao confirmado.  
Frente: F3 / G2  
Recorrencia: 2 de 2 repeticoes por modulo.

Passos:

```powershell
.venv\Scripts\python.exe -m pytest tests\presentation\test_cut_mode_dialog.py -q
.venv\Scripts\python.exe -m pytest tests\presentation\test_cut_mode_manip.py -q
```

Esperado: 100% dos testes aprovados e processo encerrado com codigo zero.

Obtido: os pontos chegam a 100%, mas o processo termina com
`-1073741819` (`0xC0000005`).

Diagnostico atual: o problema e cumulativo e ocorre no teardown. Os fixtures
chamam `CutModeDialog.deleteLater()` sem drenar explicitamente os eventos de
destruicao. Isso e uma hipotese forte para o crash, nao uma causa raiz ainda
comprovada. Tambem deve ser auditado o ciclo de vida dos objetos filhos Qt e
de `_NestThread`.

Teste permanente proposto: executar cada modulo do Modo Corte em subprocesso
e exigir simultaneamente relatorio JUnit verde e `returncode == 0`.

## Evidencias

- `reports/core.xml`
- `reports/presentation/test_cut_mode_dialog.xml`
- `reports/presentation/test_cut_mode_dialog-rerun.xml`
- `reports/presentation/test_cut_mode_dialog-rerun.log`
- `reports/presentation/test_cut_mode_manip.xml`
- `reports/presentation/test_cut_mode_manip-rerun.xml`
- `reports/presentation/test_cut_mode_manip-rerun.log`
- demais XML e logs em `reports/presentation/`

## Veredito

**Pronto para vender: nao, nesta rodada.**

O bloqueio imediato e o G2 reprovado. Mesmo depois de corrigir ou isolar o
crash de teardown, a aprovacao comercial ainda depende da execucao dos gates
G1, G3, G4 e G6 em seus cenarios manuais. Para o publico CorelDRAW, G5 tambem
e obrigatorio em maquina real.
