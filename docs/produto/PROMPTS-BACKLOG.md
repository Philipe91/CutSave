# Prompts prontos — backlog de melhorias (Onda 1)

Como usar (economia máxima de tokens com o Fable):
1. **Uma tarefa por conversa nova.** Nunca junte várias — o histórico é
   reprocessado a cada mensagem, então conversa curta = barata.
2. Abra a conversa, cole o **CABEÇALHO FIXO** + **UMA TAREFA** de baixo.
3. Quando terminar e eu aprovar o commit, feche e abra outra pra a próxima.

As âncoras de linha (~L....) são aproximadas e podem andar conforme editamos;
são ponto de partida, não endereço exato.

---

## CABEÇALHO FIXO (cole sempre, no topo)

```
PrintNest, software de produção gráfica (PySide6, Windows). Branch v1.3-redesign.
Leia as memórias printnest-backlog-lancamento e printnest-ui-preferences: já têm
todo o contexto — NÃO me peça pra reexplicar nem reexplore o que já está lá.

REGRAS (sagradas):
1. NÃO alterar o que já funciona. Mudança mínima, cirúrgica, aditiva. Na dúvida, pergunte.
2. ECONOMIA DE TOKEN (uso Fable, é caro):
   - Vá direto às âncoras da tarefa. NÃO leia arquivos inteiros — só trechos (offset/limit).
   - NUNCA releia um arquivo que você acabou de editar.
   - NÃO tire screenshots do app. Valide por TESTE (texto). Eu abro o app pra conferir.
   - Durante o trabalho, rode só o teste do arquivo afetado; a suíte inteira uma vez no fim.
   - Seja breve nas respostas; sem narração longa.
3. Commit só quando eu disser "faça commit". Antes de começar, um commit de checkpoint.
4. Rodar app (só se EU pedir): .venv/Scripts/python.exe -m app.presentation
   Testes: .venv/Scripts/python.exe -m pytest <arquivo> -q
```

---

## TAREFA B1 — multi-drop da biblioteca

```
TAREFA (faça SÓ esta, nada além):
B1 — Selecionar vários arquivos na biblioteca (Ctrl/Shift) e soltar TODOS de uma vez
na área de trabalho. Hoje é um por um.
Âncoras em app/presentation/main_window.py:
- self._table.setSelectionMode(QAbstractItemView.SingleSelection) ~L4532 → ExtendedSelection
- _on_library_drop ~L6988 e add_paths ~L5595: aceitar N arquivos e posicioná-los sem sobrepor
- library_drop = Signal ~L231; dropEvent do canvas ~L304
Entregue: a mudança + 1 teste novo cobrindo o multi-drop. Me mostre o teste passando
e peça aprovação antes de commitar.
```

---

## TAREFA B4 — tela dividida horizontal

```
TAREFA (faça SÓ esta, nada além):
B4 — Adicionar modo de visualização "Tela dividida HORIZONTAL" (arte à ESQUERDA,
faca à DIREITA), além do split vertical que já existe. NÃO mexer no vertical.
Âncoras em app/presentation/main_window.py:
- combo _view_mode ~L3562: add item novo, ex. ("Tela dividida (lado a lado)", "split_h")
- _draw_preview ~L6470: hoje o "split" empilha vertical (arte dy=0; faca dy=total_h+gap).
  Para "split_h", deslocar a faca em dx (largura_da_chapa + gap) em vez de dy.
- _draw_sheets já aceita deslocamento; ver se precisa aceitar dx além de dy.
Entregue: a mudança + 1 teste. Peça aprovação antes de commitar.
```

---

## TAREFA B3 — tooltips na barra superior

```
TAREFA (faça SÓ esta, nada além):
B3 — Garantir tooltip (texto ao pairar o mouse) em TODOS os ícones da barra
superior, em linguagem de gráfica. Muitas ações via _act() já têm dica no 3º
argumento; varrer a barra e preencher só as que faltam.
Âncoras em app/presentation/main_window.py:
- construção das ações _act(...) e dos grupos da toolbar (~L1620–1910)
- tb.tool_button / tb.menu_button: conferir setToolTip em cada botão
Não altere comportamento — só adicione/ajuste textos de dica.
Entregue: a varredura + os textos. Teste opcional (checar que botões-chave têm
toolTip não-vazio). Peça aprovação antes de commitar.
```

---

## TAREFA A1 — limpar os nomes das marcas de registro

```
TAREFA (faça SÓ esta, nada além):
A1 — Nas marcas de registro, tirar os TEXTOS "Mimaki" e "bolinhas" dos rótulos
visíveis; deixar só o ícone/visual. NÃO mudar o comportamento das marcas, só o
rótulo/label que o cliente vê.
Âncoras em app/presentation/main_window.py:
- combo _reg_type ~L4728 (itens: "Nenhum"/"none", e os de Mimaki/bolinhas)
- tooltip do _reg_type ~L4480 e os _mk_* (~L4481–4483)
Cuidado: o VALOR (data) de cada item do combo é usado no motor — mudar só o
TEXTO exibido, nunca o data/valor.
Entregue: a mudança + teste garantindo que os data/valores continuam iguais.
Peça aprovação antes de commitar.
```

---

## TAREFA B2 — ajustar tamanho da página antes de colocar arquivos

```
TAREFA (faça SÓ esta, nada além):
B2 — Permitir ajustar largura/altura da chapa ANTES de colocar arquivos na área
de trabalho (hoje os campos parecem não valer antes da 1ª geração).
Âncoras em app/presentation/main_window.py:
- _relayout ~L6231 retorna cedo em "if not self._loaded:" ~L5379 → antes de gerar,
  mexer nos spins _width/_height é no-op silencioso.
- _loaded vira True só em ~L6219 (após gerar produção).
Objetivo: os campos de tamanho refletirem no canvas/preview mesmo sem arquivos
(mostrar a chapa vazia no tamanho escolhido), sem quebrar o fluxo pós-geração.
Investigue a causa e proponha a mudança mínima ANTES de aplicar (me confirme a
abordagem, pois mexe no fluxo central de layout).
Entregue: proposta → após meu ok, a mudança + teste. Commit só com aprovação.
```

---

## TAREFA D1 — Modo Corte: rotação fina das letras (15°/45°)

```
TAREFA (faça SÓ esta, nada além):
D1 — No Modo Corte, permitir rotações além de 0/90/180/270° (45° e 15°) para
letras/formas orgânicas encaixarem mais — pedido do Philipe em 21/07.
NÃO é flip de flag: o domínio hoje SÓ aceita múltiplos de 90.
Âncoras:
- app/domain/model/placement.py: Rotation é IntEnum {0,90,180,270} e
  PlacedItem.rotation usa esse enum → precisa aceitar ângulo arbitrário
  (float ou enum estendido) SEM quebrar project_io (serializa como int).
- app/domain/nesting/true_shape.py:_to_rotation (~L547) rejeita fora de 90 em
  90; o cache de NFP é por (forma, rotação) → mais ângulos = cache e tempo
  crescem linear. Expor a escolha (90/45/15) em vez de liberar tudo.
- app/application/use_cases/run_true_shape_nesting.py:placed_cut_contours já
  gira por float(item.rotation) → a Fase 4 acompanha de graça.
- UI: app/presentation/cut_mode_dialog.py — trocar o checkbox "Permitir girar"
  por combo "Rotações: Nenhuma / 90° / 45° / 15°".
Entregue: proposta do modelo de dados ANTES de codar (mexe em domínio
serializado). Depois do ok: mudança + testes (inclusive project_io). Commit só
com aprovação.
```

---

## TAREFA D2 — Plugin CorelDRAW do Modo Corte

```
TAREFA (faça SÓ esta, nada além):
D2 — Botão "PrintNest Corte" no CorelDRAW: exporta o desenho (página ou
seleção) e abre DIRETO o diálogo do Modo Corte com o arquivo já carregado,
para organizar e exportar o DXF de lá — pedido do Philipe em 21/07.
A infra já existe: corel/PrintNest.bas exporta PDF temporário preservando
vetores e chama o PrintNest.exe (instância única, printnest_path.txt).
Âncoras:
- corel/PrintNest.bas: duplicar a macro com um argumento novo (ex.:
  --modo-corte <pdf>) na linha de comando.
- printnest_main.py / app/presentation/__main__.py: tratar o argumento; com
  ele, abrir a MainWindow e chamar _open_cut_mode + add_vector_file(pdf)
  (cut_mode_dialog.add_vector_file já aceita PDF).
- Instância única: conferir como o arquivo entra na sessão atual (ver
  tests/presentation/test_single_instance.py) e rotear o argumento novo.
- corel/README.md + instalar_plugin_corel.bat: documentar o botão novo e
  lembrar que o Philipe precisa regerar o PrintNest.gms.
Entregue: mudança + teste do parse do argumento + atualização do README do
corel/. Commit só com aprovação.
```

---

## TAREFA D3 — Modo Corte: preencher furos (peça dentro de peça) — PROMPT MESTRE

```
# PrintNest — Fase 6 (D3): nestar peça DENTRO do furo de outra peça

Você está em C:\projetos\Cutph (Python, PySide6, Clean Architecture,
ruff + pytest, venv em .venv). Responda e comente em português, no estilo
dos arquivos vizinhos. NÃO commite — eu commito após revisão.

## Missão
Implementar o inside_check do TrueShapePacker ("Allow inside" de mercado):
peça pequena entra no FURO de peça já colocada (miolo do "O", vão do "8").
É o principal ganho de densidade que falta — nosso aproveitamento já empata
em ~37-38% com o benchmark, mas os vãos ficam vazios.

## Contexto (leia antes de codar)
- app/domain/nesting/true_shape.py:
  - TrueShapePacker(inside_check=True) hoje lança NotImplementedError (o
    construtor guarda a vaga) — vire a chave REAL aqui.
  - Furos já viajam em NestingShape.holes (o motor hoje só usa o outer).
  - _place_nfp: região válida = IFP retangular da chapa − união dos NFPs
    das peças postas; candidato = vértice da região com menor (y, x);
    best_spot já busca rotação por peça quando recebe tupla.
  - Cache de NFP por (id_a, rot_a, id_b, rot_b) — siga o padrão para o
    novo "IFP de furo" (cache por furo × peça × rotações).
  - Oráculo 2A (_overlaps/_inside_sheet) valida qualquer posicionador novo.
- Convenção de escala inteira (pyclipper × _SCALE) e gap via _offset
  (peça inflada em gap/2) — o furo deve ser ENCOLHIDO em gap/2 pelo mesmo
  _offset com delta negativo.

## Desenho sugerido
1. _ifp_hole(hole, piece_norm): região onde a REFERÊNCIA (bbox.min) da peça
   cabe TOTALMENTE dentro do furo = erosão do furo pela peça (Minkowski,
   pyclipper). Validar contra teste bruteforce (amostrar posições e conferir
   com contenção ponto a ponto + _overlaps).
2. Em _place_nfp (quando inside_check): a região válida vira
   (IFP chapa − NFPs) ∪ (para cada FURO de peça posta: _ifp_hole transladado
   para a posição real − NFPs das peças que JÁ estão dentro desse furo).
   O candidato continua sendo o menor (y, x) global — furo perto do topo
   ganha naturalmente.
3. O furo participante é o da peça POSTA com a rotação dela: girar os furos
   junto (mesmo transform do outer, como a Fase 4 faz).
4. Fitness do GA não muda (bbox encolhe sozinho quando o vão é usado).
5. UI: no CutModeDialog, checkbox "Preencher furos (peça dentro de peça)"
   LIGADO por padrão -> TrueShapePacker(inside_check=...). Invalida o
   preview ao mudar (padrão dos outros parâmetros).

## Armadilhas
- GAP dentro do furo: peça interna infla gap/2 E o furo encolhe gap/2 —
  senão o laser funde a peça interna na parede do furo.
- Furo pequeno demais: _ifp_hole vazio -> segue o fluxo normal (chapa).
- Peça DENTRO de furo não pode colidir com outra peça dentro do MESMO furo
  (NFP entre internas) nem vazar para fora do furo.
- Ordem de corte no DXF: a peça de dentro precisa ser cortada ANTES do
  contorno que a envolve (senão a chapa solta e desalinha). No
  export_layouts/DxfExporter, emita primeiro os contornos das peças
  hospedadas em furos. Documente a regra.
- Reconstrução da Fase 4 e preview NÃO mudam (peça interna é só um
  PlacedItem em posição normal).

## Testes (tests/domain/nesting/test_true_shape.py + dialog)
- _ifp_hole validado contra bruteforce (quadrado em furo quadrado; círculo
  aproximado em furo redondo).
- Quadrado 20 SÓ cabe no furo 30 do "O" 100x100 em chapa apertada -> entra
  no furo, sem overlap, dentro do furo (contenção), gap respeitado.
- Furo com 2 peças internas -> sem overlap entre elas.
- gap grande demais -> peça NÃO entra no furo (vai para a chapa/fica fora).
- inside_check=False -> comportamento idêntico ao atual (suite antiga verde
  SEM edição).
- Dialog: checkbox liga/desliga e invalida preview; DXF sai com a peça
  interna antes do outer hospedeiro (ordem no arquivo).
- Determinismo: generations+seed -> dois packs idênticos.

## Regras de sempre
- ruff limpo nos arquivos tocados; suíte inteira verde (hoje 665).
- Motor validado contra o oráculo; NÃO regredir os benchmarks (letras
  150mm, chapa 1000: >=32/33 giradas, ~10s no orçamento de 10s).
- Ao terminar, PARE e entregue resumo (decisões, arquivos, testes,
  benchmark antes/depois do aproveitamento) para revisão.
```

---

## TAREFA E1 — Peças do Modo Corte na ÁREA DE TRABALHO — PROMPT MESTRE

Objetivo do Philipe: parar de tratar o Modo Corte como uma janela à parte —
poder jogar as peças de corte no canvas do PrintNest e manipulá-las lá, com as
mesmas ferramentas do modo Impressão (mover, girar, duplicar, alinhar, guias,
desfazer).

É a maior mudança estrutural desde a Fase 2: hoje os dois mundos são separados
*de propósito*, e a separação está escrita na docstring do `cut_mode_dialog.py`.
Por isso o prompt manda entregar em **duas etapas com parada obrigatória** — a
primeira mexe no fluxo de impressão que já funciona e já vende.

```
# PrintNest — E1: peças de corte manipuláveis na área de trabalho

Você está em C:\projetos\Cutph (Python, PySide6, Clean Architecture,
ruff + pytest, venv em .venv). Responda e comente em português, no estilo
dos arquivos vizinhos. NÃO commite — eu commito após revisão.

## Missão
Levar as peças do Modo Corte (contorno REAL, com furos) para o canvas
principal e deixá-las manipuláveis com as ferramentas que já existem
(mover, girar, duplicar, alinhar, distribuir, guias, snap, desfazer).

Hoje são dois mundos separados de propósito. A docstring do
app/presentation/cut_mode_dialog.py explica por quê: "O canvas do modo
Impressao desenha PieceItem, que e um QGraphicsRectItem — so sabe
retangulo." Esta tarefa é justamente derrubar essa limitação SEM quebrar o
modo Impressão.

## Contexto (leia antes de codar — os números são reais)
- app/presentation/main_window.py (~8175 linhas) tem TODO o canvas:
  - PieceItem(QGraphicsRectItem) na linha ~478, construído com
    super().__init__(0, 0, width, height) do BOUNDING BOX
    (artwork_footprint). paint() só desenha drawRect quando selecionado.
    A arte e a faca são FILHOS criados em _draw_sheets (~6631/6665).
  - PieceItem NÃO guarda rotação. Ela vive em self._piece_rotations
    (~1493) e é assada na geometria durante o _relayout.
  - Estado canônico = self._result (ProductionResult): sheets (Layout),
    artworks (Artwork), sources. A geometria real do polígono mora em
    Artwork.cut_contour (CutContour).
  - CANVAS -> MODELO passa por UM único método: _effective_sheets()
    (~7249), que relê piece.scenePos() e monta PlacedItem(artwork_id, pos)
    com DOIS argumentos — descartando rotação.
  - Undo = SnapshotCommand (~430) + _state_snapshot (~7276) /
    _apply_state (~7288).
- app/presentation/cut_mode_dialog.py: cena PRÓPRIA (~219), desenha com
  addPath/QPainterPath (~573) via placed_cut_contours, OddEvenFill para
  vazar furo (~590). Nada é selecionável nem movível. Ponto de contato
  único com a MainWindow: _open_cut_mode (~7466).
- app/application/use_cases/run_true_shape_nesting.py: placed_cut_contours
  reconstrói a peça posicionada; _cut_order define a ordem de corte (Fase
  6). Leia docs/produto/FASE6-PRENCHER-FUROS.md antes de mexer em corte.

## ETAPA 1 (entregue e PARE para revisão)
Fundação, sem UI nova. Estas duas mudanças tocam o fluxo de impressão que
já está em produção, então merecem revisão isolada:

1. PieceItem deixa de ser retângulo. Passe a QGraphicsPathItem (ou
   mantenha a classe e sobrescreva shape()/boundingRect()) para que:
   - o hit-test respeite o CONTORNO real e os FUROS — clicar no miolo do
     "O" NÃO pode selecionar a letra;
   - peça sem cut_contour continue se comportando exatamente como hoje
     (o retângulo do footprint vira o path; zero mudança visível).
2. A rotação passa a sobreviver ao canvas. Hoje _effective_sheets monta
   PlacedItem com 2 args e o primeiro arraste APAGA o giro. Faça a rotação
   viajar de ponta a ponta: _effective_sheets, _arr_key (~6809),
   _piece_sel_key (~6449) e o SnapshotCommand.

Critério de aceite da etapa 1: suíte inteira verde SEM editar teste antigo
(hoje 684), e o modo Impressão pixel-a-pixel igual — se um teste de
impressão precisar mudar, PARE e me pergunte antes.

## ETAPA 2 (só depois do meu ok)
3. Botão "Enviar para a área de trabalho" no CutModeDialog: converte cada
   PolygonWithHoles/NestingShape em Artwork + CutContour e injeta no
   _result, preservando posição e rotação do nesting true-shape.
4. As ferramentas do canvas passando a ler o bbox do POLÍGONO em vez do
   rect(): alças de resize (~2908), barra de propriedades (~2870),
   overlay (~3693), alinhar (~6894), distribuir (~6927), zoom-seleção
   (~6763), fantasmas/step-repeat (~3956/7218).
5. Exportação DXF a partir do canvas respeitando a ordem de corte da
   Fase 6 (de dentro para fora).

## DECISÃO DE ARQUITETURA (Philipe, 22/07) — canvas ÚNICO, não área separada
Cogitou-se criar uma área de trabalho SEPARADA só para corte. **Decidido:
não.** Um canvas só, com modo de corte (mesma cena, mesmas ferramentas, mesmo
desfazer; muda a barra, o nesting e a exportação).

- **Motivo:** o que falta ao Modo Corte não é um canvas — ele já tem cena
  própria. Faltam as FERRAMENTAS (mover, girar, duplicar, alinhar, distribuir,
  guias, snap, desfazer): ~30 métodos da MainWindow, todos amarrados ao
  `ProductionResult`. Área separada = reescrever os 30 e manter DOIS conjuntos
  em sincronia para sempre. Cada bug de alinhamento viraria dois.
- **O que decidiu:** Philipe confirmou que NÃO vai vender o Modo Corte
  separado — é sempre o mesmo cliente fazendo impressão e corte. Se algum dia
  quiser vender separado (versão só para quem tem laser), reabrir esta
  decisão: aí a duplicação passaria a se pagar como estratégia de produto.
- **Se apertar no futuro:** o caminho NÃO é duplicar, é EXTRAIR o canvas para
  um componente reutilizável e instanciar duas vezes (impressão e corte).
  Código compartilhado, espaços separados. O `main_window.py` (~8175 linhas)
  já precisa disso de qualquer forma.
- **Risco conhecido e aceito:** os conceitos não se misturam (impressão tem
  sangria/marcas/DPI; corte tem folga/ordem de corte/giro fino), então as
  barras e diálogos vão precisar mostrar/esconder por modo. Vigiar para não
  apodrecer — é o sintoma que dispara a extração do componente.

## DECISÃO DE DESENHO obrigatória antes de escrever a etapa 2
**Peça de corte no canvas NÃO sobrevive a salvar/reabrir hoje.** Verificado
em 22/07 (project_io.py + _capture_project, main_window.py:2180):

- O `.printnest` salva CAMINHOS DE ARQUIVO + parâmetros + file_overrides +
  faca_manual. NÃO salva Layout/PlacedItem — ao abrir, reimporta e
  re-organiza do zero. (Por isso não há buraco de rotação na etapa 1: o
  arranjo inteiro já não é persistido.)
- Consequência para as peças de corte:
  - vinda de arquivo: para sobreviver teria de entrar em `self._paths`, mas
    aí volta pelo importador da IMPRESSÃO — sem o contorno true-shape.
  - vinda do botão **Texto…**: não tem caminho nenhum. **Sumiria por
    completo** ao reabrir. Silencioso.

Escolher UMA saída antes de codar:
(a) persistir as peças de corte de verdade no `.printnest`, em campo ADITIVO
    novo (mesmo padrão do `faca_manual`, criado na varredura de 09/07 — ver
    docstring do `ProjectDocument`); ou
(b) avisar no botão que peça de corte não sobrevive ao salvar (ruim — o
    cliente monta o arranjo com letras, salva, reabre e não está lá).

Isto muda o FORMATO do arquivo, então não dá para deixar para depois.

## Armadilhas
- NÃO quebre o modo Impressão. Ele é o produto que já vende. Peça sem
  cut_contour tem de continuar idêntica.
- _effective_sheets é o ÚNICO caminho canvas->modelo. Toda mudança de
  estado do canvas passa por ele; esquecer um campo lá = perder o dado no
  primeiro arraste.
- Snap (_snapped, ~541) usa rect() e sceneBoundingRect(). Com contorno
  real ele encaixa na CAIXA, não na forma — decida e documente se nesta
  etapa o snap continua por caixa (aceitável) ou passa a ser por contorno.
- merge_touching_rect_cuts (~7803) só reconhece retângulo. Com contorno
  real ele fica inerte em silêncio — não deixe isso virar bug mudo.
- A ferramenta Pontos (~2962) ancora os nós em -fp.min_x/-fp.min_y, ou
  seja, no bounding box. Com polígono, confira se o sistema local bate.
- Rotação livre (giro fino do Modo Corte, ex. 45°) NÃO é o enum Rotation.
  PlacedItem.rotation aceita float; o canvas precisa aguentar os dois.
- main_window.py tem ~8175 linhas. Se a etapa 2 crescer demais, proponha
  extrair um módulo ANTES de escrever, não depois.

## Testes
- Hit-test: clique no furo de uma peça com contorno NÃO seleciona.
- Peça sem cut_contour: comportamento idêntico ao de hoje (teste de
  não-regressão explícito).
- Rotação sobrevive a: arrastar, desfazer/refazer, redesenhar a cena.
- Etapa 2: peça enviada do Modo Corte chega ao canvas na mesma posição e
  rotação do preview; o DXF exportado do canvas bate com o do diálogo.

## Regras de sempre
- ruff limpo nos arquivos tocados; suíte inteira verde (hoje 684).
- Motor de nesting validado contra o oráculo; não regredir os benchmarks.
- Ao terminar a ETAPA 1, PARE e entregue resumo (decisões, arquivos,
  testes, o que mudou no fluxo de impressão) para revisão.
```

---

## TAREFA E2 — nesting true-shape no modo IMPRESSÃO — PAUSADO

> **DECISÃO DO PHILIPE (22/07): não fazer por enquanto.** O modo Impressão
> fica como está. Não retomar sem ele pedir.
>
> **Motivo dele:** não quer peça impressa girada em ângulo torto (37°, 45°).
>
> **Nuance importante para quem retomar:** o ganho do true-shape NÃO vinha
> principalmente do giro fino — vinha do ENTRELAÇAMENTO das formas (um "C"
> entrando na barriga do outro), que funciona girando só de 90 em 90, como a
> impressão já faz hoje. Então a restrição de giro sozinha não invalida a
> ideia.
>
> O que realmente pesa contra são os outros quatro itens da lista abaixo
> (sangria, marcas de registro, tempo de resposta, faca compartilhada) somados
> a um ganho que só aparece em trabalho COM FACA DE CONTORNO. Se algum dia
> retomar, retome por aí — e meça com trabalho real antes de prometer economia.

Registrado em 21/07: usar a lógica de encaixe do Modo Corte (a mesma linha do
eCut) para economizar material também na impressão.

### Por que o E1 vem antes (não é desvio)
Os dois consertos do E1 são exatamente os pré-requisitos:
- `PieceItem` deixar de ser retângulo = poder encaixar pela FORMA real.
- rotação sobreviver ao canvas = o true-shape gira em ângulo fino (45°, 15°)
  e sem isso o ganho evapora no primeiro arraste.

### O que existe hoje
- Impressão usa `MaxRectsPacker` (`app/domain/nesting/max_rects.py`), ligado em
  `main_window.py:1534` via `RunGridNestingUseCase`. Empacota **retângulos**.
- Corte usa `TrueShapePacker` (`app/domain/nesting/true_shape.py`), NFP/IFP +
  genético. Já sabe contorno real, furos (Fase 6) e giro livre.
- A geometria real da peça de impressão já existe: `Artwork.cut_contour`.

### Onde está o ganho de verdade
**Não é em qualquer trabalho.** Arte retangular encaixada por true-shape dá
exatamente o mesmo que MaxRects — retângulo é retângulo. O ganho aparece em
**impressão com faca de contorno** (adesivo recortado, letra, peça vazada), que
é justamente o forte do PrintNest. Antes de prometer economia, medir com
trabalho REAL do Philipe, não com sintético.

### Perguntas a resolver ANTES de codar
1. **Rotação é livre na impressão?** No corte, girar 45° é de graça. Na
   impressão pode haver restrição (sentido do material, bobina, consistência
   de cor entre peças iguais). Perguntar ao Philipe antes de assumir.
2. **Sangria/bleed**: o encaixe tem de respeitar a sangria da arte, não só o
   contorno da faca. Decidir qual polígono entra no NFP.
3. **Marcas de registro** precisam de área livre — o true-shape não sabe disso
   hoje.
4. **Tempo**: MaxRects é instantâneo; o true-shape custa segundos a minutos.
   Na impressão o operador espera resposta rápida. Provavelmente vira opção
   ("Encaixe inteligente"), não o padrão.
5. **Faca compartilhada**: o modo grade existe porque peças que dividem faca
   precisam ficar alinhadas. True-shape quebraria isso — tem de continuar
   sendo um modo à parte.

### Não regredir
O motor de impressão é o que já vende. Isto entra como MODO ADICIONAL, nunca
substituindo o MaxRects sem o Philipe pedir.

### Já resolvido pela Fase 6 (aproveitar)
O custo do GA passou a ser (chapa consumida, compacidade) em vez de área do
bounding box — ver `docs/produto/FASE6-PRENCHER-FUROS.md` seção 4. Isso vale
para qualquer uso futuro do `TrueShapePacker`, inclusive este.

---

## Ondas 2 e 3 (depois)
- A2 (marca personalizável) + A3 (novos tipos) — só após o Philipe enviar o
  documento com a pesquisa das marcas do mercado.
- C1 (testar barra superior: organizar/nesting, alinhar, distribuir).
- C2 (nesting): eCut SÓ como benchmark, nunca copiar código. Técnicas públicas
  (Skyline, Simulated Annealing). Ver [[printnest-backlog-lancamento]].
