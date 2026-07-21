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

## Ondas 2 e 3 (depois)
- A2 (marca personalizável) + A3 (novos tipos) — só após o Philipe enviar o
  documento com a pesquisa das marcas do mercado.
- C1 (testar barra superior: organizar/nesting, alinhar, distribuir).
- C2 (nesting): eCut SÓ como benchmark, nunca copiar código. Técnicas públicas
  (Skyline, Simulated Annealing). Ver [[printnest-backlog-lancamento]].
