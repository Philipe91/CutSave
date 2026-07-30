# RELATÓRIO EXECUTIVO — RELEASE CANDIDATE 1.0

**Registro oficial da RC.** Este documento é a referência para auditorias futuras
e para a preparação da 1.0.1.

| | |
|---|---|
| **Versão analisada** | 1.0.0 |
| **Data** | 30/07/2026 |
| **Commit analisado** | `1717043` (código) · `0f72bc5` (HEAD, inclui o checklist do A3) |
| **Branch** | `v1.3-redesign` |
| **Checklist utilizado** | `docs/qa/A3-VALIDACAO-MANUAL-RC-2026-07-30.md` |
| **Fase** | A3 concluído · A4 (rebuild + smoke) **não iniciado** |
| **Congelamento de código** | **ATIVO** |

**Como o A3 foi executado.** As 8 validações foram dirigidas por scripts que
constroem a `MainWindow`, o `CutModeDialog` e o `ActivationDialog` **reais**, com
o QSS do produto aplicado e **sem** a variável `PYTEST_CURRENT_TEST` — ou seja,
as caixas de diálogo abriram de verdade e foram capturadas, em vez de
curto-circuitadas pela guarda de testes. As validações visuais (V3/V4) foram
julgadas em imagens renderizadas dos widgets. As geométricas (V2) foram medidas
com o tema aplicado e conferidas em captura das telas forçadas à altura de um
notebook 1366×768 @125%.

**Limites desta execução — declarados.** O ambiente é `QT_QPA_PLATFORM=offscreen`,
que não carrega glifos: nas capturas o texto aparece como quadrados. Isso permite
julgar **layout e contraste** (a forma do glifo carrega a cor do texto), mas
**não** tipografia. Onde o conteúdo textual importava — a numeração dos passos da
Ativação — ele foi lido programaticamente do widget, não da imagem. O
`%APPDATA%\PrintNest` real do dono **não foi tocado**: o V8 rodou em diretório
temporário. Nada aqui substitui o A4, que é onde o binário compilado é exercido.

---

## 1. RESULTADO DAS VALIDAÇÕES

### V1 — Fechar a janela durante uma geração longa (C3)

**Status: ✔ APROVADO**

**Evidências.** Duas rodadas independentes com um PDF de **400 páginas**
(gerado a partir do exemplo do produto; o `exemplo-printnest.pdf` sozinho
rasteriza a 0,02 s/página e terminava antes do fechamento — a primeira tentativa
foi descartada por isso). O fechamento foi disparado **dentro da fase de
rasterização**, na página 120 de 400:

```
rodada 1: geracao em voo no close = True (progresso 120/400, fase de render = True)
rodada 1: fechou em 0.06s | thread ainda viva = False
rodada 2: geracao em voo no close = True (progresso 120/400, fase de render = True)
rodada 2: fechou em 0.08s | thread ainda viva = False
caixa exibida: "Há alterações não salvas neste trabalho."
```

**Observações.** O critério do checklist era **< 3 s**; o medido foi **0,06 s e
0,08 s** — duas ordens de grandeza de folga. A thread morreu nas duas rodadas
(`isRunning() == False`), o que descarta o "QThread destruído com a thread
rodando" que abortava o processo. A caixa de descarte apareceu corretamente.

**Impacto.** Elimina o cenário "o programa fechou sozinho" na máquina do cliente
— a assinatura que motivou toda a investigação do crash `0xc0000374`.

---

### V2 — Modo Corte e Ativação em tela apertada (C4, H2, H25)

**Status: ✔ APROVADO** (três sub-itens)

**Evidências.** Medição com o QSS do produto aplicado, e captura das duas telas
forçadas à altura de um notebook 1366×768 @125% (~545 px lógicos):

| Tela | Altura mínima | Cabe em 545? |
|---|---|---|
| Modo Corte | **534 px** | sim, 11 px de folga |
| Ativação | **509 px** | sim, 36 px de folga |

- `V2-modo-corte-545.png` — a 900×545 as **duas fileiras do rodapé aparecem
  inteiras** (3 botões à esquerda, 4 à direita, incluindo o de destaque). A barra
  de rolagem do painel de parâmetros é visível: a `QScrollArea` do C4 está
  absorvendo o aperto em vez de empurrar os botões para fora.
- `V2-ativacao-545.png` — a 533×545 todos os elementos aparecem, incluindo o
  botão "Ativar" e o botão do rodapé.
- Numeração lida **do widget**, não da imagem:
  `['1', '2', '3', '4']` — H25 corrigido.

**Observações.** A medição sem o tema aplicado dava 468 px para a Ativação e
506 px para o Modo Corte. Foi essa diferença (~28 a 117 px de padding do QSS) que
quase deixou o H2 passar como "não reproduz". Os testes automatizados de
geometria foram endurecidos no mesmo lote para aplicar `theme.apply()` antes de
medir.

**Impacto.** Destrava as duas telas mais críticas: o Modo Corte é o que a macro
do CorelDRAW abre **sem janela principal por trás** (operador sem saída visível),
e a Ativação é a primeira tela do produto pago.

---

### V3 — Texto do botão de destaque nos presets (C10)

**Status: ✔ APROVADO**

**Evidências.** `V3-V4-temas.png` — folha com **14 linhas** (todos os temas base
+ todos os presets), cada uma exibindo o botão de destaque com o texto na cor
derivada por luminância.

**Observações.** O comportamento novo é visível e correto: nos acentos claros
(cinza/Graphite, verde, turquesa, roxo) o texto saiu **escuro**; nos acentos
escuros continua branco. Nenhum botão apresentou texto "lavado" ou sumindo no
fundo. Sete presets reprovavam WCAG AA antes (Verde 2,28:1 · Turquesa 2,49 ·
Graphite 2,52 · Laranja 2,80 · Carbon 2,80 · Midnight 3,20 · Escuro 3,65).

**Impacto.** O botão `GERAR FACA` e os cabeçalhos de card ficam legíveis em todos
os presets que o app oferece. **Ponto que exige decisão comercial, não técnica:**
presets claros agora têm texto escuro no CTA — é a correção correta, mas é uma
mudança visual perceptível. Registrado para o dono aprovar a aparência.

---

### V4 — Tooltip nos temas escuros (C9)

**Status: ✔ APROVADO**

**Evidências.** Mesma folha `V3-V4-temas.png`, coluna da direita. O balão foi
renderizado com a **regra real do QSS do produto** (a string gerada por
`theme.build_app_qss()`, com o seletor `QToolTip` trocado por `QLabel`), não com
uma imitação escrita à mão.

**Observações.** A inversão está correta em todos os temas: nos temas escuros o
balão tem fundo claro com texto escuro; no tema claro, fundo escuro com texto
claro. Nenhum caso de branco-sobre-branco.

**Impacto.** Os 104 tooltips do app voltam a funcionar no modo escuro — que é
recurso vendido. Antes, todos apareciam como balões vazios (contraste 1,0:1).

---

### V5 — Perda de trabalho: abas e Modo Corte (C7, C8)

**Status: ✔ APROVADO** (dois sub-itens)

**Evidências — C7 (dirty por aba):** aba 1 suja → aba 2 criada → `Ctrl+S` na
aba 2 → fechar o app:

```
aba 1 suja? True
depois de salvar a aba 2 -> dirty da aba ativa: False
sessoes com dirty: [True, False]        <- o flag é POR ABA
caixa ao fechar: "Há trabalho não salvo em outra(s) aba(s)."
   informativo: "Fechar o PrintNest descarta o que não foi salvo."
   botões: ['Cancelar', 'Fechar mesmo assim']
```

**Evidências — C8 (descarte do arranjo):**

```
Esc com arranjo e SEM exportar  -> "Fechar o Modo Corte descarta o arranjo organizado."
                                   "O arranjo ainda não foi enviado ao Corel nem exportado."
                                   botões: ['Continuar aqui', 'Fechar mesmo assim']
Esc DEPOIS de exportar          -> nenhuma caixa (fecha direto)
```

**Observações.** Os botões estão em português e sem a opção "Salvar" no caso de
aba inativa — decisão deliberada: "Salvar" ali salvaria a aba errada. A ausência
de pergunta após exportar confirma que a flag `_work_exported` está sendo marcada
pelos dois caminhos (Corel e DXF).

**Impacto.** Fecha as duas rotas de perda silenciosa de trabalho. Na auditoria de
customer success, "perdi meu projeto" é baixa frequência e **gravidade máxima**
(vira reembolso).

---

### V6 — Exportação bloqueada durante a geração (H13a)

**Status: ✔ APROVADO**

**Evidências.** Produção pequena gerada primeiro (existe "resultado antigo"),
depois PDF de 400 páginas e nova geração:

```
antes da nova geracao: 9/9 exportacoes habilitadas
durante a geracao    : 0/9 habilitadas
tooltip durante      : "(Aguarde a geração terminar)"
depois               : 9/9 habilitadas
```

**Observações.** As 9 ações cobrem todos os caminhos de saída: Centro de
Exportação, PDF, DXF, DXF-N, faca PDF, imagem, cartelas, Mimaki e iECHO. O
tooltip mudou para o texto honesto — antes dizia "Gere a produção primeiro",
que era enganoso durante uma geração em curso.

**Impacto.** Impede a exportação silenciosa do resultado **anterior** no meio de
uma geração nova. Numa gráfica, isso é material caro impresso errado sem nenhum
aviso de que aconteceu.

---

### V7 — Canal de atualização respondendo (C6)

**Status: ✔ APROVADO**

**Evidências — com rede**, pela janela real (inclui a `QThread` da consulta):

```
versao do app        : 1.0.0
URL embutida         : https://gist.githubusercontent.com/Philipe91/
                       00110a87efa02d4256ea0755ac621236/raw/manifesto.json
URL efetiva da janela: (a mesma — o config do cliente não sobrescreve)
resposta em          : 0.10s
mensagem exibida     : "Você já está na versão mais recente (1.0.0)."
```

**Evidências — sem rede**, apontando para `192.0.2.1` (faixa TEST-NET-1 da RFC
5737, garantidamente sem rota — equivale a arrancar o cabo, sem mexer na rede da
máquina):

```
checar() devolveu None em 5.0s (timeout configurado: 5.0s)
```

**Evidências complementares** — os três cenários de versão pelo código do app:
`checar(URL, "1.0.0")` → `None` · `checar(URL, "0.9.0")` → `Novidade(versao='1.0.0')`
· `checar(URL, "1.1.0")` → `None`.

**Observações.** Nenhum texto de desenvolvedor apareceu. A resposta em 0,10 s
confirma que a URL raw **sem hash de revisão** segue o redirecionamento
corretamente. Offline, a consulta respeita o timeout de 5 s e devolve `None` sem
travar a janela — mas na interface esse `None` vira "você já está na versão mais
recente", que é o **H15**, já classificado para a 1.0.1. Comportamento esperado,
não reprovação.

**Impacto.** É a apólice de seguro do lançamento. Sem este canal, qualquer bug
pós-venda viraria reinstalação manual guiada por suporte, cliente por cliente — e
a própria 1.0.1 é entregue por ele.

---

### V8 — Integridade de dados: salvar e configuração (N1, N3)

**Status: ✔ APROVADO** (dois sub-itens)

**Evidências — N3 (config corrompido):**

```
config truncado para: '{"unit": "cm", "sheet_w'
app subiu com padroes                    : True
quebrado preservado como .corrompido     : True
config novo e valido                     : True
MainWindow construida apos o corrompido  : True
```

**Evidências — N1 (salvar atômico):**

```
salvou: True | .tmp deixado para tras: []
save interrompido no os.replace devolveu False
arquivo anterior intacto: True (980 bytes, tamanho inalterado)
usuario avisado: "Falha ao salvar o projeto: ...trabalho.printnest"
```

**Observações.** O `.tmp` não vaza no caminho feliz nem no de erro. A
interrupção foi simulada no `os.replace`, que é o último passo da gravação — o
ponto exato onde uma queda de energia ou um antivírus atrapalharia.

**Impacto.** N3 é o cenário "o programa não abre mais": raro, fatal e reembolso
certo se não corrigido. N1 é a destruição do projeto **anterior** ao salvar por
cima.

---

## 2. RESUMO EXECUTIVO

| | |
|---|---|
| Validações executadas | **8 de 8** |
| Aprovadas | **8** |
| Reprovadas | **0** |
| Bloqueadores encontrados | **0** |

**Pendências (nenhuma bloqueia o A4):**

1. **Decisão comercial em aberto (V3).** O texto escuro do CTA nos presets claros
   é a correção tecnicamente correta, mas é mudança visual. Precisa do aval do
   dono — não é defeito.
2. **Prova do H7 pendente.** O mutex é criado (2 handles confirmados), mas o
   comportamento que interessa — o **instalador detectar o app aberto** — só pode
   ser provado no A4a.
3. **C6 dentro do binário.** Validado no interpretador; falta observar o silêncio
   na abertura do `.exe` compilado (A4b).
4. **Ativação bloqueante.** O fluxo de primeira execução sem licença só existe
   com `sys.frozen` — A4.
5. **Conteúdo do pacote (H24).** As 7 imagens do guia do Corel só aparecem depois
   do `build.bat` — conferir no A4.
6. **Pós-A4.** Descartar e reemitir as licenças de teste presas ao fingerprint
   antigo (decisão A1 do dono).

**Riscos remanescentes:** detalhados na matriz da seção 3.

---

## 3. MATRIZ DE RISCO

| # | Risco | Classificação | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|---|
| R1 | **Gist/conta do GitHub some ou é renomeada** — a URL está gravada no `.exe` de todo cliente da 1.0.0 e não há correção remota | **Alto** | Baixa | Crítico se ocorrer: todos perdem o canal de atualização para sempre | Regra registrada no fonte: nunca apagar a conta, nunca apagar o Gist, nunca renomear `manifesto.json`. Builds futuras apontam para o domínio próprio; o Gist segue servindo a 1.0.0 |
| R2 | **Instalador não detecta o app aberto** — H7 entregue pela metade até ser provado | **Alto** | Média | Erro de arquivo em uso no meio da atualização 1.0→1.0.1 | **A4a é obrigatório.** Se falhar: instrução "feche o PrintNest antes de atualizar" no canal de suporte |
| R3 | **Sem assinatura digital: SmartScreen** no download | **Alto** | Alta | Ticket de suporte "não abre / deu vírus" na primeira hora | Texto explicativo na página/e-mail de entrega (H6-mínimo). Certificado EV fica para depois |
| R4 | **Placeholder no campo `url` do manifesto** — se esquecido na 1.0.1, o cliente é avisado e cai num link morto | **Alto** | Média | Cliente avisado de atualização que não baixa | Lembrete escrito **dentro do próprio campo** (`TROCAR-PELO-LINK-REAL-NA-1.0.1`) + procedimento: publicar o instalador **antes** de editar o manifesto |
| R5 | **Excepthook com modal reentrante** (H5) — o `QMessageBox` abre de dentro do hook; erro durante processamento de eventos gera event loop aninhado | **Médio** | Baixa | Comportamento imprevisível numa situação que já é de erro | Avisa **uma vez por sessão**; o aviso inteiro está sob `suppress` (nunca vira o segundo erro). Não exercitado com erro real em slot Qt na janela viva |
| R6 | **Ativação estoura a 150%** em 1366×768 (509 px contra ~455 úteis) | **Médio** | Baixa | Cliente com essa configuração não consegue ativar | Adiado para 1.0.1 por decisão do Release Manager — 1366×768 @150% é fora do padrão do Windows. **É o primeiro cliente legítimo do canal C6** |
| R7 | **Iconografia sem devicePixelRatio** (H1) — app levemente borrado em 125–150% | **Médio** | Alta | Percepção "amadora" difusa e constante; 150% é padrão em notebook 14" FHD | Adiado para 1.0.1. Nenhuma perda funcional |
| R8 | **Exportações e "Enviar p/ Corel" síncronos** (H10/H11) | **Médio** | Média | "Não respondendo" em exportação pesada; percepção de travamento | Wait cursor já existe. Workers ficam para 1.0.1/1.1 |
| R9 | **Resposta offline indistinguível de "em dia"** (H15) | **Baixo** | Média | Cliente sem internet acha que conferiu e está atualizado | Adiado para 1.0.1. Não causa dano, só informação imprecisa |
| R10 | **Yes/No em inglês** nos diálogos padrão do Qt (H19) e ~30 strings sem acento (H22) | **Baixo** | Alta | Acabamento; o diálogo perigoso de descarte já tem botões pt-BR custom (C8) | Adiado para 1.0.1, numa passada única de i18n |
| R11 | **Sem autosave/recuperação** (N2) | **Baixo** | Baixa | Crash perde o trabalho desde o último `Ctrl+S` | Adiado para 1.1. C2, C3, C7, C8 e N1 já cortaram as rotas principais de perda |

**Nenhum risco classificado como Crítico permanece aberto.** Os quatro Altos têm
mitigação definida; R2 é o único que ainda exige **execução** (A4a).

---

## 4. RELEASE READINESS

| Dimensão | Nota | Justificativa |
|---|---|---|
| **Estabilidade** | **9,0** | As duas causas conhecidas de tombo foram fechadas: pdfium sob lock (C2) e cancelamento no fechar, medido em 0,06 s (C3). Excepthook dá rastro ao que sobrar. Desconta: o `0xc0000374` nunca foi reproduzido, então a correção é da causa **provável**, não da confirmada |
| **UX** | **8,0** | Perda de trabalho fechada nas duas rotas, tooltips legíveis, CTA com contraste, exportação travada durante geração, telas cabendo em notebook. Desconta: Yes/No em inglês, ~30 strings sem acento, barra de progresso que enche duas vezes |
| **Performance** | **7,0** | Nesting e geração em thread com espera comunicada; 400 páginas rasterizam sem travar a UI. Desconta: exportações, "Enviar p/ Corel", "Páginas do PDF…" e o drop incremental seguem síncronos na thread da interface |
| **Licenciamento** | **8,5** | Ed25519 com chave privada fora do repositório; fingerprint sem MAC (dock/adaptador não quebra mais a licença); ativação só declara sucesso se gravou de fato. Desconta: fluxo bloqueante de primeira execução ainda não exercido no binário |
| **Atualizações** | **8,0** | Canal no ar e respondendo em 0,10 s pelos três cenários de versão; offline respeita o timeout. Desconta: hospedagem em Gist pessoal (R1) e o placeholder no campo `url` (R4) |
| **Instalador** | **6,5** | pt-BR, preserva a licença na desinstalação, EULA sem placeholders, `AppMutex` declarado. Desconta pesado: **não recompilado** desde as mudanças, mutex não provado (R2) e sem assinatura digital (R3) |
| **Integridade de dados** | **9,5** | Escrita atômica com `fsync` + `os.replace` no projeto e no config; arquivo anterior comprovadamente intacto após interrupção; config corrompido não brica mais o app e é preservado como `.corrompido`. Desconta: sem autosave (N2) |
| **Confiabilidade** | **8,5** | 939 testes verdes, 0 falhas, 0 erros; 8 de 8 validações manuais aprovadas com evidência coletada; nenhum teste removido ou marcado como xfail. Desconta: o binário compilado ainda não foi exercido em nenhuma dimensão |

**Média ponderada: 8,1 / 10.**

A nota mais baixa — Instalador, 6,5 — é a que **o A4 existe para levantar**. É
consistente: tudo que depende do executável está por provar, e é exatamente onde
a validação ainda não chegou.

---

## 5. GO / NO-GO

# ⚠ GO COM RESSALVAS

**Justificativa técnica.**

O A3 fechou com **8 de 8 aprovadas e zero bloqueadores**, sobre uma base de 939
testes verdes. Todas as rotas de **perda de dados** e **perda de trabalho**
identificadas nas duas auditorias estão fechadas e foram verificadas com o app
real, não apenas por teste unitário: escrita atômica com o arquivo anterior
comprovadamente preservado, config corrompido que não brica mais o app, dirty por
aba, confirmação no Modo Corte e cancelamento de geração em 0,06 s. A causa
**provável** do crash `0xc0000374` — pdfium usado fora do lock em dois pontos —
foi eliminada, e o excepthook garante que o que sobrar deixe rastro em vez de
sumir em silêncio.

O canal de atualização está **no ar e respondendo**, o que muda a natureza de
toda a lista de adiamentos: "1.0.1" deixou de ser um eufemismo para "nunca" e
passou a ser uma entrega executável. É por isso que adiar H1, H15, H19, H22 e a
Ativação a 150% é defensável — cada um deles tem um caminho real de chegar ao
cliente.

**As ressalvas são três, e todas têm data e responsável:**

1. **O binário nunca foi exercido.** Tudo neste relatório roda a partir do fonte.
   O `.exe` e o instalador não foram regerados desde as 18 correções. Isso não é
   uma dúvida sobre o código — é uma etapa que ainda não aconteceu, e é o A4.
2. **O H7 está entregue pela metade** até o A4a provar que o instalador detecta o
   app aberto. Se falhar, a mitigação é textual e aceitável, mas precisa ser
   decidida antes da entrega.
3. **Sem assinatura digital**, o SmartScreen é certeza no primeiro download. A
   mitigação (texto explicativo na entrega) é obrigatória, não opcional.

**O que tornaria isto um NO-GO:** qualquer falha no A4a (mutex), no A4b (silêncio
do update no binário) ou no fluxo bloqueante de ativação em máquina limpa.

**Recomendação: PROSSEGUIR para o A4.** Não há motivo técnico para interromper, e
nenhuma alteração de código adicional é recomendada antes do rebuild — o
congelamento deve permanecer ativo exatamente como está.

---

## 6. REGISTRO OFICIAL DA RC

| Campo | Valor |
|---|---|
| **Versão analisada** | 1.0.0 |
| **Data** | 30 de julho de 2026 |
| **Branch** | `v1.3-redesign` |
| **Hash do commit analisado** | `1717043` — *fix(1.0): lote final do release candidate* |
| **HEAD no momento do relatório** | `0f72bc5` |
| **Suíte utilizada** | pytest, via `--junit-xml` com soma de 14 arquivos XML (a suíte não se auto-reporta: o processo morre no teardown com `0xC0000005` e o exit code mente; `tests/presentation` trava se executada como pasta e roda arquivo a arquivo) |
| **Total de testes** | **939** |
| **Testes aprovados** | **934** |
| **Falhas** | **0** |
| **Erros** | **0** |
| **Skips** | **5** |
| **Checklist utilizado** | `docs/qa/A3-VALIDACAO-MANUAL-RC-2026-07-30.md` |
| **Validações manuais** | 8 executadas · 8 aprovadas · 0 reprovadas |

### Resumo das alterações desde a auditoria inicial

Ponto de partida: `AUDITORIA-PRE-LANCAMENTO-2026-07-30.md` (10 críticos, 25 de
alto impacto, 23 médios, 16 refinamentos) e `PLANO-LANCAMENTO-2026-07-30.md`
(mais 10 achados de integridade N1–N10; veredito inicial: **"Confiança para
lançar amanhã: 4/10 — NÃO RECOMENDO LANÇAR"**).

**Commit `2162ef5` — os 12 bloqueadores.** C1 EULA sem placeholders, acentuada,
vendedor e foro definidos · C2 pdfium sob `PDFIUM_LOCK` nos dois pontos que
faltavam · C3 geração cancelável · C4 Modo Corte cabendo em 1366×768 @125% ·
C5 nome "PrintNest Pro" nas strings visíveis (chaves de QSettings **não**
renomeadas, para não resetar tema e tour de quem já usa) · C7 `_dirty` por aba ·
C8 confirmação ao descartar o arranjo · C9 tooltip legível nos temas escuros ·
C10 texto do CTA derivado por contraste · N1 salvar atômico · N3 config
corrompido não brica o app · H3 ativação que só declara sucesso se gravou ·
H4 fingerprint sem MAC no Windows (**decisão irreversível**, autorizada por
escrito pelo dono: nenhuma licença comercial havia sido emitida).

**Commit `1717043` — lote final.** C6 canal de atualização ligado · H5
`sys.excepthook` global · H7 mutex + `AppMutex` no instalador · H13a exportações
travadas durante a geração · H2 Ativação de 585 px para 509 px (+ H25, a
numeração 1‑2‑3‑**3** que virou 1‑2‑3‑4) · H24 pacote do cliente.

**Dois achados de método**, ambos com correção aplicada: os testes de geometria
mediam **sem** o QSS do produto e davam garantia mais fraca do que aparentavam
(era o que escondia o H2); e a armadilha prevista para o C6 valia para **dois**
testes, não um — o segundo não falhava, **travava** a suíte inteira com uma
`QThread` de rede órfã.

**Adiado por decisão do Release Manager.** Para a **1.0.1**: H1 (ícones sem DPR),
H19 (pt-BR nos diálogos do Qt), H22 (acentos), H13b (barra de progresso),
H15 (resposta offline), Ativação a 150%, H10/H11 (Corel e exportações em worker).
Para a **1.1**: N2 (autosave). **Rejeitado para a 1.0:** `_set_busy(False)` no
caminho de cancelamento — ocorre só com a janela fechando, e "é só uma linha" é
como regressões de véspera começam.

### Artefatos de evidência

| Arquivo | Conteúdo |
|---|---|
| `reports/*.xml` | 14 relatórios junit da rodada única (939/0/0/5) |
| `V1` | log das duas rodadas de fechamento durante rasterização |
| `V2-modo-corte-545.png` | Modo Corte a 900×545, rodapé inteiro visível |
| `V2-ativacao-545.png` | Ativação a 533×545, botão "Ativar" e rodapé visíveis |
| `V3-V4-temas.png` | 14 temas/presets: CTA e tooltip lado a lado |
| `V5/V6` | textos e botões das caixas capturadas + estados das 9 exportações |
| `V7/V8` | resposta do manifesto, offline com timeout, config corrompido, save atômico |

> Os PNGs e logs vivem no diretório de trabalho da sessão. Se forem necessários
> para auditoria futura, devem ser copiados para `docs/qa/evidencias/` **antes**
> do encerramento da sessão — não são versionados por padrão.

---

## PRÓXIMO PASSO

**A4 — Rebuild + Smoke Test.** Bloqueado até aprovação explícita do dono.

Roteiro obrigatório, na ordem:

1. `build.bat` → conferir que `PrintNest_Build\Plugin CorelDRAW\imagens\` chegou
   com os **7** PNGs (única mudança do lote que só aparece no build).
2. Compilar o instalador (`printnest.iss`) → conferir a EULA na tela de licença.
3. **A4a** — com o `.exe` **aberto**, rodar o instalador por cima: o Inno tem que
   detectar e pedir para fechar; fechando, a instalação prossegue.
4. **A4b** — abrir o `.exe` com rede: sem travamento e sem aviso de atualização.
5. Primeira execução sem licença: o diálogo bloqueia e "Sair" encerra.
6. Fluxo completo em máquina limpa: importar → gerar → Modo Corte → exportar.
7. Descartar e reemitir as licenças de teste do fingerprint antigo.

**O congelamento de código permanece ativo.** Nenhuma alteração, refatoração ou
melhoria entra sem nova aprovação explícita.
