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

**Veredito: build tecnicamente validada; release ainda não aprovada e bloqueada
para publicação pelas validações pendentes.** O que esta rodada aprova é a
linha automatizada e o artefato. Sete gates que exigem medição externa,
instalação limpa e CorelDRAW real **não foram executados** — são gates abertos,
não defeitos — e o **fechamento inesperado do executável (`0xc0000374`) segue
em aberto, sem causa confirmada**, como defeito separado do que foi corrigido
aqui.

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

## Validação do instalador em máquina real (04/08/2026)

Executado nesta máquina, que tinha **PrintNest 1.0.0 instalado e licença
ativa**.

| Verificação | Resultado |
|---|---|
| Instalação silenciosa | `ExitCode 0`, 12 s |
| Versão registrada no Windows | 1.0.0 → **1.1.2** |
| `VERSAO.txt` instalado | 1.1.2 |
| **Licença preservada** | **SHA-256 idêntico antes e depois** |
| Configurações preservadas | `config.json` intacto |
| Conteúdo entregue | `.exe`, LEIA-ME, README, Tutor IA (PDF), Plugin CorelDRAW |
| Autoteste do binário instalado | **`SELFTEST OK`** em 7 s, rodando de `C:\Program Files` |
| Abertura da janela | **abriu**, título `PrintNest`, 30 threads |
| Fechamento | limpo, 0,8 s |

O autoteste rodou **logo depois da instalação**, que é exatamente o cenário do
`"Failed to load Python DLL"` visto em máquina de terceiro. Não reproduziu.

**Isto NÃO fecha o G4.** Foi uma **atualização por cima** de uma instalação
existente, não uma instalação limpa. O G4 exige máquina ou perfil de usuário
**sem PrintNest**, e continua pendente.

### Vazamento do Modo Corte — medição objetiva

30 aberturas e fechamentos consecutivos, mesmo harness, código antes e depois:

| | diálogos vivos | memória | por abertura |
|---|---:|---:|---:|
| Antes (`d73175f`) | **33** | +10,9 MB | +371 KB |
| Depois (`829a4b9`) | **0** | +0,1 MB | +3 KB |

Medido com o **Modo Corte vazio**, sem peças importadas. Com peças na cena o
acúmulo é maior, porque o que ficava retido incluía a geometria.

**Limite desta evidência:** a medição foi feita no código, em modo headless,
com o laço modal substituído. **O clique real na interface não foi
executado** — não tenho como operar a janela. Abrir e fechar o Modo Corte
várias vezes no programa instalado continua sendo verificação manual pendente.

---

## Evidências

- `reports/1.1.2/core.xml` e `core.log`
- `reports/1.1.2/presentation/*.xml` e `*.log` (18 módulos)
- Log da instalação silenciosa (temporário, fora do repositório)

---

## Matriz go/no-go

Três naturezas diferentes, que não podem ser somadas na mesma conta:

- **Validado** — foi executado e passou.
- **Gate aberto** — **não foi executado**. Não é defeito, não é falha, não
  entra em contagem de bug. É verificação pendente.
- **Bug aberto** — defeito conhecido, ainda sem correção comprovada.

| # | Item | Natureza | Evidência | Bloqueia publicar? |
|---|---|---|---|---|
| 1 | G2 — crash do Modo Corte na suíte | **validado** | causa provada, 18/18 saída zero, teste permanente | não |
| 2 | Suíte automatizada | **validado** | 1.039 testes, 0 falhas, 0 erros | não |
| 3 | Build e empacotamento | **validado** | `SELFTEST OK` no `.exe` instalado | não |
| 4 | Atualização por cima, licença preservada | **validado** | SHA-256 da licença idêntico | não |
| 5 | Vazamento do Modo Corte | **validado** | 33 → 0 diálogos; +10,9 → +0,1 MB | não |
| 6 | G4 — instalação limpa | **gate aberto** | houve só teste de atualização | **sim** |
| 7 | Modo Corte: abrir/fechar clicando | **gate aberto** | medido só em headless | **sim** |
| 8 | G1 — arte × faca com medição externa | **gate aberto** | não executado | **sim** |
| 9 | G3 — estado por peça, roteiro manual | **gate aberto** | não executado | **sim** |
| 10 | G5 — CorelDRAW real | **gate aberto** | não executado | **sim** |
| 11 | G6 — validação externa dos artefatos | **gate aberto** | não executado | **sim** |
| 12 | G7 — varredura visual em escalas reais | **gate aberto** | não executado | **sim** |
| 13 | **`0xc0000374` — fechamento inesperado** | **bug aberto** | sem reprodutor, **sem causa confirmada** | **sim** |
| 14 | `tests/presentation` como pasta trava | **bug aberto** | >10 min, estourou o limite | não (afeta só o QA) |

**Contagem desta rodada: zero falhas.** Os itens 6 a 12 são verificações que
ainda não rodaram — não são defeitos e não devem ser reportados como tal. Os
itens 13 e 14 são os únicos defeitos abertos, e nenhum dos dois foi introduzido
por esta versão.

---

## Veredito

### Build tecnicamente validada; release ainda não aprovada e bloqueada para publicação pelas validações pendentes

O que está provado: a correção faz o que promete, a suíte está verde de ponta a
ponta com saída limpa, o instalador funciona, a licença sobrevive à atualização
e o binário empacotado roda. **Nada falhou nesta rodada.**

O bloqueio para publicar vem de duas fontes distintas, e a distinção precisa
sobreviver a qualquer resumo:

1. **Sete gates que não foram executados** (itens 6 a 12). "Não testado" não é
   "testado e reprovado" — mas também não é "aprovado".
2. **Um bug aberto** (item 13, `0xc0000374`), **sem causa confirmada**.

Sobre o item 13: o vazamento corrigido nesta versão é **coerente** com o
`crash.log`, e nada além disso. **Não há prova de que seja a causa**, não há
reprodutor, e a 1.1.2 não deve ser apresentada como solução dele.

A decisão de publicar com o `0xc0000374` em aberto é **comercial, não
técnica**. Pode ser legítima — a 1.1.2 é melhor que a 1.1.1 em todos os
aspectos medidos — mas precisa ser tomada sabendo que o fechamento inesperado
não foi corrigido.

---

## Checklist para o Philipe executar

Dois testes. Os dois precisam de **outro computador**, sem PrintNest instalado.

Anote o resultado de cada linha; é isso que atualiza a matriz.

### Teste A — G4, instalação limpa

Precisa de um PC **que nunca teve PrintNest**. Se só houver um com PrintNest
instalado, desinstale primeiro **e apague `%APPDATA%\PrintNest`** — senão não é
instalação limpa, é atualização (foi esse o limite do teste feito aqui).

| # | Passo | O que tem que acontecer | OK? |
|---|---|---|---|
| A1 | Copiar `PrintNest-Setup-1.1.2.exe` para o PC | — | ☐ |
| A2 | Dar dois cliques no instalador | Aviso azul do Windows → "Mais informações" → "Executar assim mesmo" | ☐ |
| A3 | Avançar até o fim | **A caixa "executar agora" vem DESMARCADA.** Deixe assim | ☐ |
| A4 | **Esperar ~30 segundos** | (é o antivírus varrendo o arquivo novo) | ☐ |
| A5 | Abrir pelo atalho da área de trabalho | A janela abre. **Sem** "Failed to load Python DLL" | ☐ |
| A6 | Conferir Ajuda/rodapé ou `VERSAO.txt` | Diz **1.1.2** | ☐ |
| A7 | Ativar a licença | Ativa normalmente | ☐ |
| A8 | Importar 1 PDF, F5, Ctrl+E | Gera o PDF de impressão sem erro | ☐ |

**Se A5 falhar:** feche tudo, espere 1 minuto, abra de novo. Se abrir na
segunda, **anote** — é o defeito conhecido do antivírus, não é regressão.

### Teste B — Modo Corte, abrir e fechar clicando

No **mesmo PC do Teste A**, com o programa já aberto.

| # | Passo | O que observar | OK? |
|---|---|---|---|
| B1 | Ctrl+Shift+Esc → aba Detalhes → achar `PrintNest.exe` | Anote a **Memória** inicial: ______ MB | ☐ |
| B2 | Abrir o **Modo Corte**, importar 2 ou 3 arquivos, clicar **Organizar** | Organiza normalmente | ☐ |
| B3 | Fechar o Modo Corte | Fecha sem travar | ☐ |
| B4 | **Repetir B2 e B3 dez vezes** | Anote a memória a cada 2 voltas | ☐ |
| B5 | Comparar com B1 | **A memória não pode subir sem parar.** Subir e estabilizar é normal | ☐ |
| B6 | Continuar usando o programa por ~10 min | Não fecha sozinho | ☐ |

Memória por volta: 2:____ 4:____ 6:____ 8:____ 10:____ MB

**O que estamos procurando:** antes da correção, cada abertura deixava a janela
inteira na memória. Agora não deve deixar. Se a memória crescer sem parar,
**a correção não pegou no executável** e eu preciso saber.

**Se o programa fechar sozinho** em qualquer momento: é o `0xc0000374` (item
13). Anote o que estava fazendo e envie
`%APPDATA%\PrintNest\logs\crash.log`. **É esperado que possa acontecer** — não
foi corrigido nesta versão.

### O que estes dois testes fecham — e o que não fecham

Passando A e B, a matriz muda assim:

| Item | Vira |
|---|---|
| 6 — G4, instalação limpa | validado |
| 7 — Modo Corte clicando | validado |

**Continuam abertos, sem qualquer alteração:**

| Item | Por que A e B não o tocam |
|---|---|
| 8 — **G1** | exige imprimir e **medir com régua/paquímetro** se a faca cai sobre a arte, em peça assimétrica |
| 9 — **G3** | exige o roteiro manual de estado por peça (excluir, rearrastar, conferir faca e giro antigos) |
| 10 — **G5** | exige **CorelDRAW real** instalado, nas versões suportadas, com o plugin |
| 11 — **G6** | exige abrir os PDF/DXF exportados em **outro programa** e validar lá |
| 12 — **G7** | exige rodar em **telas pequenas e escalas de 125%/150%** conferindo visualmente |
| 13 — **`0xc0000374`** | segue aberto; B6 pode até flagrá-lo, mas não o corrige nem prova causa |

Ou seja: A e B **não liberam a publicação sozinhos**. Eles removem dois dos
sete gates. O veredito só muda para "aprovada para publicar" quando os sete
estiverem fechados e houver decisão explícita sobre o item 13.
