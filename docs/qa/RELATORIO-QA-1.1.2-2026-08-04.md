# PrintNest Pro — relatório de QA 1.1.2

Data da execução: 04/08/2026
Branch: `release/1.1.2`
Commit: `8c736a3`
Ambiente: Windows 10 Pro 64 bits `10.0.19045`, Python `3.10.11`, pytest `9.1.1`, PySide6 `6.11.1`
Bateria: `docs/qa/BATERIA-DE-TESTES-1.1.1-2026-08-04.md`
Rodada anterior: `docs/qa/RELATORIO-QA-1.1.1-2026-08-04.md` (**reprovada**)

---

## Resumo executivo

O bloqueio da rodada anterior foi removido. **BUG-QA-1 está fechado com causa
provada**, não contornado nem silenciado: o gate G2 passou de reprovado a
aprovado, e agora tem um teste permanente que o vigia.

A execução coletou **1.039 testes: 1.034 aprovados, 5 `xfail`, zero falhas e
zero erros**. Os **18 módulos** de `tests/presentation` encerraram com **código
de saída zero** — na rodada anterior, dois deles derrubavam o processo.

**Esta rodada não aprova a venda.** O que ela aprova é a linha automatizada. Os
gates que exigem medição externa, instalação limpa e CorelDRAW real continuam
pendentes, e o **fechamento inesperado do executável (`0xc0000374`) segue em
aberto** — é um defeito diferente do que foi corrigido aqui.

---

## Resultado automatizado

| Grupo | Testes | Aprovados | Falhas | Erros | Xfail | Tempo JUnit | Processo |
|---|---:|---:|---:|---:|---:|---:|---|
| Base sem `tests/presentation` | 712 | 707 | 0 | 0 | 5 | 291,079 s | aprovado |
| Apresentação, 18 módulos isolados | 327 | 327 | 0 | 0 | 0 | 140,035 s | **18 aprovados, 0 com crash** |
| Total | **1.039** | **1.034** | **0** | **0** | **5** | 431,114 s | **aprovado** |

Comparação com a rodada 1.1.1:

| | 1.1.1 | 1.1.2 |
|---|---|---|
| Testes coletados | 1.030 | 1.039 (+9) |
| Módulos de apresentação | 16 | 18 (+2) |
| Módulos com crash de processo | **2** | **0** |
| Veredito da linha automatizada | reprovado | aprovado |

Os 9 testes a mais são todos novos e nascem desta correção: 3 do gate de saída
limpa, 4 do ciclo de vida da thread de encaixe e 2 do vazamento do diálogo.

**Nota metodológica:** a suíte deste projeto não se auto-reporta. O processo
podia morrer no encerramento e o código de saída mentir, então o único número
válido é a **soma dos arquivos JUnit**, e `tests/presentation` precisa rodar
**módulo a módulo**. Foi assim que esta rodada foi medida.

---

## BUG-QA-1 — FECHADO

**Causa raiz (provada, não hipótese).**

As fixtures chamavam `deleteLater()` nos diálogos e **nada acontecia**.
`processEvents()` não entrega eventos `DeferredDelete`: eles só saem quando o
laço de eventos volta ao nível em que foram postados e, sem um `exec_()`
rodando, ele nunca volta. As janelas ficavam na fila indefinidamente.

Resultado: **33 janelas de topo chegavam vivas** ao `pytest_sessionfinish`, que
as fechava todas de uma vez — e aí o processo morria.

Isso explica os três fatos que a rodada anterior registrou sem conseguir
encaixar: só o Modo Corte (é quem acumula diálogos pesados), cumulativo a
partir do 8.º teste, e cada teste sozinho passando.

**Onde o crash acontecia.** Instrumentado: dentro do `pytest_sessionfinish` —
ou seja, **antes** do desarme que já existia no `pytest_unconfigure`. Por isso
aquele desarme, escrito exatamente para essa classe de falha, nunca protegeu.

**Correção.** Uma linha em `tests/conftest.py`:
`QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)` na fixture
autouse por teste.

| | antes | depois |
|---|---|---|
| Janelas de topo vivas no fim do módulo | 33 | **0** |
| `returncode` | 3221225477 (`0xC0000005`) | **0** |

**Hipóteses que foram testadas e falharam** (registradas para ninguém repetir):

1. Ciclo de vida da `_NestThread` — corrigido como defeito próprio, **não era
   a causa**; o crash persistiu com a correção aplicada.
2. A hipótese da própria rodada 1.1.1 (`deleteLater()` sem drenar) — estava
   certa no espírito, mas a primeira tentativa de testá-la usou
   `processEvents()`, que **não** drena `DeferredDelete`, e por isso deu
   negativo. O acerto veio ao usar `sendPostedEvents` explicitamente.

**Teste permanente** (o que a rodada 1.1.1 pediu):
`tests/qa/test_qa_g2_saida_limpa.py` roda cada módulo do Modo Corte em
subprocesso e exige as **duas evidências independentes** — JUnit verde (com
`testes > 0`, para não passar vazio) **e** `returncode == 0`. Antes da correção
ele ficava vermelho em 2 dos 3 módulos e verde no terceiro: não é um teste que
sempre acusa.

---

## Correções que entraram nesta versão

| Defeito | Arquivo | Teste que o trava |
|---|---|---|
| BUG-QA-1 (`0xC0000005` na suíte) | `tests/conftest.py` | `tests/qa/test_qa_g2_saida_limpa.py` |
| Diálogo do Modo Corte retido a cada abertura | `app/presentation/main_window.py` | `tests/presentation/test_cut_mode_vazamento.py` |
| Referência da thread de encaixe caindo cedo | `app/presentation/cut_mode_dialog.py` | `tests/presentation/test_cut_mode_thread.py` |

**Sobre o vazamento do diálogo.** `_open_cut_mode` criava o diálogo com pai
(a janela principal) e descartava a referência Python na hora. No Qt, quem tem
pai pertence ao C++: destruir o wrapper Python não destrói o objeto. Cada
abertura do Modo Corte deixava um diálogo inteiro vivo — cena, peças e
geometria — até o programa fechar. Medido: 4 aberturas, 4 diálogos vivos.
Corrigido com `deleteLater()` em `finally`.

Os dois testes de vazamento são deliberadamente opostos: um exige zero diálogos
retidos após 5 aberturas, o outro exige que o diálogo **esteja vivo** enquanto
o `exec()` não retornou — senão a correção poderia ser satisfeita destruindo
cedo demais, o que seria pior que o defeito.

**Sobre a `_nest_thread`.** Foi medido que no PySide6 a entrega do sinal `done`
é enfileirada para a thread principal, então a corrida é de milissegundos e não
há crash conhecido causado por ela. Mantida como defesa, com o escopo declarado
no código. **Não conte esta correção como parte do G2.**

---

## Correção de rumo: pyclipper, não GEOS

O relatório anterior e o dossiê descreviam o crash do executável como defeito
do **GEOS/Shapely**. Está errado, e o erro é meu.

`app/domain/nesting/true_shape.py` importa **`pyclipper`** e **não usa
shapely**. O `_subtract` que aparece na pilha do `crash.log` é pyclipper. GEOS
só existe na faca (`app/domain/cut/`), que não está naquela pilha.

Medida nova e relevante: **pyclipper solta o GIL** (2 threads em 0,62× do tempo
sequencial). Ou seja, enquanto o encaixe roda, a thread principal executa Python
de verdade ao mesmo tempo — inclusive coleta de lixo. A concorrência é real, não
teórica.

Documentação corrigida em `docs/qa/DOSSIE-PARA-BATERIA-DE-TESTES.md` e
`docs/arquitetura/ARQUITETURA.md`.

---

## `0xc0000374` — ABERTO, e é outro defeito

**Não confundir com o BUG-QA-1.** São defeitos distintos:

| | BUG-QA-1 | fechamento inesperado |
|---|---|---|
| Código | `0xC0000005` (acesso inválido) | `0xc0000374` (corrupção de heap) |
| Onde | só na suíte de testes | no executável, na mão do cliente |
| Causa | **provada** | **nenhuma** |
| Reprodutor | sim | **não** |
| Estado | **fechado** | **aberto** |

Corrigir um não corrige o outro, e a 1.1.2 **não deve ser apresentada como
solução do fechamento inesperado**.

**O que a investigação de 04/08 fez.** Tentativa dirigida de separar
encerramento, concorrência e compartilhamento de geometria: worker no pyclipper
com coleta de lixo agressiva na thread principal, em 4 modos (base, síncrono,
sem GC, com lock), 25 s cada. **Não reproduziu.** Um dos modos (sem GC) estava
metodologicamente furado — `gc.collect()` explícito roda mesmo com o coletor
desativado — e o resultado dele é descartado.

**Candidato mais forte hoje:** o vazamento do diálogo corrigido nesta versão.
Ele empilha memória e alonga as pausas de coleta exatamente onde o `crash.log`
de 04/08 flagrou a thread principal (coletando lixo dentro de `_open_cut_mode`,
enquanto o encaixe rodava no pyclipper). **Isso é coerência, não prova.** O
defeito permanece aberto até haver reprodução ou correção comprovada.

---

## Gates

| Gate | Estado | Evidência desta rodada |
|---|---|---|
| G1 — arte e faca | parcial | testes automatizados de posicionamento e exportação passaram; **amostras assimétricas e medição externa pendentes** |
| G2 — crash no Modo Corte | **aprovado** | causa provada e corrigida; 18/18 módulos com código de saída zero; teste permanente em subprocesso |
| G3 — estado por peça | parcial | giro, abas, undo/redo e round-trip automatizados passaram; **roteiro manual pendente** |
| G4 — primeira abertura | pendente | **exige instalação limpa em perfil novo** |
| G5 — CorelDRAW | pendente | **exige CorelDRAW real nas versões suportadas** |
| G6 — exportações | parcial | PDF, DXF, SVG e fluxos automatizados passaram; **validação externa dos artefatos pendente** |
| G7 — telas pequenas | parcial | testes Qt de layout passaram; **varredura visual em escalas reais pendente** |

---

## Riscos conhecidos mantidos (`xfail`)

Inalterados em relação à rodada anterior.

| ID | Área | Risco ainda presente |
|---|---|---|
| QA-F2A-03a | PDF de impressão | marcas de registro usam preto RGB, não K puro |
| QA-F2A-03b | PDF de impressão | operadores PDF das marcas não usam canal K |
| QA-F3-16b | Instância única | entrega pode perder caminhos no mesmo processo/thread |
| QA-F3-13b | Projeto/configuração | `ConfigError` pode escapar sem diálogo amigável ao salvar |
| QA-F3-15 | UI/zoom | zoom extremo não possui limite mínimo/máximo |

---

## Pendências rastreadas separadamente

Nenhuma destas foi resolvida nesta rodada, e nenhuma deve ser dada como
encerrada por causa dela.

1. **`0xc0000374` — fechamento inesperado do executável.** Sem reprodutor, sem
   causa provada. Aberto.
2. **`tests/presentation` rodada como pasta inteira ainda trava** (>10 min,
   estourou o tempo limite). Defeito pré-existente e separado do BUG-QA-1 — a
   correção do `DeferredDelete` não o resolveu. Por isso a medição válida
   continua sendo módulo a módulo.
3. **Gates manuais G1, G3, G4, G5, G6 e G7**, listados acima com o que falta em
   cada um.
4. **Apagar uma peça com várias cópias remove mais que a selecionada.**
   Relatado, não reproduzido em bancada.
5. **Rearrastar arquivo excluído traz faca e giro antigos.** Diagnosticado, não
   corrigido — falta decisão entre limpar o estado automaticamente ou oferecer
   um botão explícito.
6. **Macro do CorelDRAW não responde** em "Enviar p/ Corel"; **giro
   intermitente** e **falta de zoom** no Modo Corte.

---

## Artefato desta rodada

| | |
|---|---|
| Instalador | `dist_installer/PrintNest-Setup-1.1.2.exe` |
| Tamanho | 118,1 MB |
| SHA-256 | `1256a0b02ec3c9aa46902e0577d6cca041746e21bb64e44201f0e9f3f36213df` |
| Build gerada em | 04/08/2026 14:07:40 |
| Autoteste do executável | `SELFTEST OK` (peças=3, PDF, DXF, projeto e config gravados) |

O autoteste roda o pipeline completo no executável empacotado, não no código
fonte — é a evidência de que a build não quebrou no empacotamento.

**Não publicado.** O instalador não foi enviado a nenhum cliente, o manifesto
remoto **não foi alterado** e nenhuma release foi criada. Aguardando aprovação.

---

## Evidências

- `reports/1.1.2/core.xml` e `core.log`
- `reports/1.1.2/presentation/*.xml` e `*.log` (18 módulos)

---

## Veredito

**Linha automatizada: aprovada.** BUG-QA-1 fechado com causa provada, G2
aprovado, 1.039 testes verdes e 18/18 módulos com saída limpa.

**Pronto para vender: ainda não.** Faltam os gates manuais (G1, G3, G4, G6 e,
para o público CorelDRAW, G5), e o fechamento inesperado `0xc0000374` continua
em aberto — a decisão de lançar com ele em aberto é comercial, não técnica, e
precisa ser tomada sabendo que ele **não** foi corrigido nesta versão.
