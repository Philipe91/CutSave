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

## Ondas 2 e 3 (depois)
- A2 (marca personalizável) + A3 (novos tipos) — só após o Philipe enviar o
  documento com a pesquisa das marcas do mercado.
- C1 (testar barra superior: organizar/nesting, alinhar, distribuir).
- C2 (nesting): eCut SÓ como benchmark, nunca copiar código. Técnicas públicas
  (Skyline, Simulated Annealing). Ver [[printnest-backlog-lancamento]].
