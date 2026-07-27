# AUDITORIA DE UI — julho/2026 (Tarefa U1, Etapa 1)

Contexto: teste real de 24/07 — usuário não descobriu que arquivo vai pra chapa
ARRASTANDO, e teve impressão de funções duplicadas. Regra: refinar, não
reinventar. Fonte: `app/presentation/main_window.py` (~linhas citadas) e
`licensing_dialog.py`. Nada foi alterado nesta etapa.

---

## 1. INVENTÁRIO de controles visíveis

### 1.1 Menus (barra superior) — `_build_menu_toolbar` (main_window.py:1579)

| Menu | Itens (ação · atalho) | ~linha |
|---|---|---|
| **Arquivo** (1716) | Novo Ctrl+N · Abrir Ctrl+O · Salvar Ctrl+S · Salvar Como Ctrl+Shift+S · Fechar trabalho Ctrl+W · Adicionar arquivos Ctrl+I · Substituir arquivo · Centro de Exportação Ctrl+E · Exportar PDF Ctrl+P · DXF único · DXF por chapa · Faca PDF · Imagem · Faca Mimaki · (cartelas, se flag) · Sair | 1580–1723 |
| **Editar** (1732) | Desfazer Ctrl+Z · Refazer Ctrl+Y · Copiar Ctrl+C · Colar Ctrl+V · Girar 90 esq/dir Ctrl+[ / Ctrl+] · Selecionar tudo Ctrl+A · Duplicar Ctrl+D · Duplicar só esta página Ctrl+Shift+C · Repetir em grade Ctrl+Shift+D · Agrupar Ctrl+G · Desagrupar Ctrl+U · Propriedades do objeto Alt+Return · Excluir Del · Resetar arranjo · Remover PDF selecionado | 1605–1735 |
| **Organizar** (1737) | Organizar (nesting) Ctrl+L · Ajustar chapa ao conteúdo Ctrl+Shift+F · Centralizar na chapa (check) · Agrupar/Desagrupar · Frente Shift+PgUp / Trás Shift+PgDown · Alinhar L/R/T/B/C/E · Distribuir h/v · Encaixar (snap) Alt+Q (check) | 1621–1741 |
| **Exibir** (1765) | Ajustar à tela F4/Ctrl+0 · Zoom+ F2 · Zoom− F3 · Zoom página Shift+F4 · Zoom seleção Shift+F2 · Ferramenta mão H (check) · Limpar guias | 1742–1769 |
| **Ferramentas** (1783) | **Gerar Produção F5** · Gerar Faca Shift+F5 · Pontos (nós da faca) F10 | 1595–1786 |
| **Opções** (1789) | Aparência → Tema / Personalizar Interface · Unidade de medida cm/mm | 1793–1824 |
| **Ajuda** (1830) | Tour de boas-vindas · Licença · Sobre | 1826–1834 |

Só-atalho (sem menu): Pan Alt+setas (1758–1763, invisíveis de propósito).

### 1.2 Ribbon (1888–1947)

Grupos: **Arquivo** (novo/abrir/salvar) · **Editar** (undo, redo, girar ±90,
duplicar, repetir em grade, pontos F10, excluir) · **Organizar** (organizar,
agrupar/desagrupar, frente/trás, menu Alinhar, menu Distribuir, snap) ·
**Corte** (Modo Corte, 1931) · **Exportar** (Centro de Exportação + menu
"Mais...", 1936–1939) · **Exibir** (Ajustar à tela, botão "Visualização"
(menu com os 4 modos, 1951), botão "Exibição" (popup réguas+snap, 1874),
toggle Réguas solto (1867/1945)).

**Ausência notável: "Gerar Produção" NÃO tem botão na ribbon nem em lugar
nenhum visível** — só menu Ferramentas + F5 (1595, 1784).

### 1.3 Biblioteca (painel esquerdo) — `_build_library_panel` (4561)

Logo · título "Biblioteca" · botão azul **Adicionar arquivos** (4588) ·
tabela Arquivo/Qtd com `QuantityStepper` (4594; **DragOnly**, 4604–4605) ·
**Recortar...** (diálogo de recorte de página, 4609) · **Remover
selecionado** (4618) · combo "Cortar para (caixa do PDF)" (4623) · rótulo de
seleção (4639). Combo de rotação global existe mas está oculto (4634–4637).

### 1.4 Barra de propriedades contextual (`_pbar_stack`, 2434–2539)

- Página **Projeto** (sem seleção): leitura Chapa/Peças/Chapas (2450).
- Página **Objeto** (1 peça): L×A editáveis + cadeado proporção + girar ±90 +
  Duplicar + Excluir (2471–2519).
- Página **Grupo**: contagem + medida (só leitura, 2521).

### 1.5 Barra Faca (fixa à direita da propBar) — `_build_contour_tool` (2541)

Tag de escopo "✂ Faca · documento/arquivo" (2559) · botão azul **Gerar Faca**
(2569, Shift+F5) · combo **Tipo de faca** (2577) · **Offset** + botões
fora/dentro (2584–2619) · **Suavizar** (2623) · popup **Ajustes ▾** (2716):
Cantos (2637), Raio dos cantos (2661), Nós da faca (2680), Modo do corte
por peça/grade (2694), botão Ajustar chapa ao conteúdo (2707).

### 1.6 Inspector direito (`IconRailTabs`, 3846–3853)

Abas por ícone: **Documento · Seleção · Objeto · Transformar** (+ Cartelas se
flag).

- **Documento** (3780): check Modo Compacto (3788) · card Resumo (4668) ·
  acordeão exclusivo: **Produção** (4688: largura/altura da chapa,
  espaçamentos h/v, check Manter centralizado) · **Acabamento** (4727:
  Recorte da arte/cortar bordas; Tipo de faca e Nós viraram estado oculto —
  consolidação 2e76dc5) · **Imagens** (4772: Sensibilidade, check Remover
  fundo) · **Marcas de registro** (4796: tipo + parâmetros Mimaki) ·
  **Avançado** (5060: resetar faca manual).
- **Seleção** (3830): vazio = dica em texto (3831); peça = card **Tamanho**
  (4126), card **Faca deste arquivo** (4150: Tipo, Sangria (+fora/−dentro),
  Recorte da arte, Giro em graus, Suavizar, Cantos arredondados-raio, 2 botões
  de reset), card **Ações** (4203: Duplicar, Duplicar só esta página,
  Excluir); grupo = Medidas + Ações (4211: Alinhar esq., Alinhar topo,
  Agrupar, Excluir).
- **Objeto** (4243): lista de objetos + Ações (Selecionar tudo, Agrupar,
  Desagrupar, Frente, Trás, **Remover** → exclui peças da chapa, 4261–4268).
- **Transformar** (3869): cards **Duplicar (posição)** (3885), **Grade
  (colunas×linhas)** (3914), **Rotação** ±90 (3938).

### 1.7 Canvas e volta

- Barrinha flutuante de exibição arrastável com o combo de modo de
  visualização — fonte canônica `_view_mode` (FloatingDisplayBar, 709).
- Popup "Exibição" da ribbon: **Mostrar réguas** + **Encaixar (snap)**
  (`_build_display_controls`, 5119–5134).
- Abas de trabalho multi-projeto + botão "+" (3345–3353).
- Drop do Explorer em qualquer ponto da janela → biblioteca (2075–2089).
- Drag da biblioteca → canvas (310–312 → `_on_library_drop` 7170):
  sem produção gera com os selecionados `generate(blocking=True, paths,
  faca=False)` (7181); com produção insere na posição do drop (7183+).
  **É o ÚNICO caminho visível-adjacente de pôr arquivo na chapa sem menu.**

---

## 2. DUPLICADOS

### 2a. PROPOSITAIS (padrão Corel: mesma QAction em menu + ribbon + atalho — MANTER)

Novo/Abrir/Salvar, Undo/Redo, Girar ±90, Duplicar, Repetir em grade, Pontos,
Excluir, Organizar, Agrupar/Desagrupar, Frente/Trás, Alinhar, Distribuir,
Snap (menu+ribbon), Centro de Exportação, Ajustar à tela, Modo Corte. Todos
compartilham a MESMA QAction — um objeto, N acessos. Correto.

### 2b. DUPLICATAS CONFUSAS (widgets distintos mexendo no mesmo parâmetro, ou nomes trocados)

| # | Duplicata | Onde | Diagnóstico |
|---|---|---|---|
| D1 | **Réguas 2×, lado a lado no MESMO grupo da ribbon** | toggle solto (1867, 1945) + checkbox "Mostrar réguas" no popup Exibição (5129) | Dois widgets espelhados a 30px um do outro. Irmã direta do 2e76dc5. |
| D2 | **Tooltip do botão "Exibição" mente** | 1880: promete "Unidade, modo de visualização, réguas e encaixe" | O popup só tem réguas+snap (5119–5134); unidade foi pro menu Opções e modo pra barrinha flutuante. Promessa quebrada = usuário procura e não acha. |
| D3 | **Modo de visualização 2×** | combo da barrinha flutuante (728) + botão "Visualização" da ribbon (1951) | Espelhados por código (fonte única). Defensável (a barrinha pode estar colapsada), mas conta pra "ferramentas espalhadas". |
| D4 | **Centralizar na chapa 2×** | check no menu Organizar (1668) + checkbox no card Produção (4712) | Dois widgets, mesmo parâmetro, nomes iguais. Espelhados. Tolerável. |
| D5 | **Ajustar chapa ao conteúdo 2×** | QAction menu Organizar (1623) + QPushButton no popup Ajustes da barra Faca (2707) | Segundo é botão avulso (não a QAction), mas mesmo slot e tooltip cita o atalho. OK. |
| D6 | **"Offset" (barra Faca) vs "Sangria" (card Faca deste arquivo)** | 2584/2587 vs 4157 | MESMO conceito, DOIS NOMES. A barra com peça selecionada vira override do arquivo (tag 2559) — ou seja, os dois widgets editam o mesmo parâmetro com nomes diferentes. Idem "Raio dos cantos" (2676) vs "Cantos arredondados - raio" (4175). **A duplicata confusa nº 1 da faca.** |
| D7 | **Três "Recortes" com nome quase igual** | biblioteca "Recortar..." = recorte de página com prévia (4609); Acabamento "Recorte da arte (cortar bordas)" = apara global mm (4730); card do arquivo "Recorte da arte - cortar bordas" = apara por arquivo (4161) | Funções DIFERENTES, rótulos quase idênticos. Usuário não sabe qual usar. |
| D8 | **"Remover" ambíguo** | biblioteca "Remover selecionado" = tira o ARQUIVO da lista (4618); aba Objeto "Remover" = EXCLUI PEÇAS da chapa (4267, chama `_delete_selected`); menu Editar "Remover PDF selecionado" (1633) | Mesma palavra, dois efeitos distintos (arquivo × peça). Risco de perda acidental. |
| D9 | **Duplicar 4 widgets** | propBar Objeto (2500) + card Ações da Seleção (4204) + card "Duplicar (posição)" do Transformar (3885) + QAction menu/ribbon Ctrl+D | O do Transformar tem semântica extra (posição/cópias) — os outros 3 são o mesmo Ctrl+D reembalado. |
| D10 | **Repetir em grade 2 caminhos** | diálogo Ctrl+Shift+D (1641) + card "Grade (colunas×linhas)" do Transformar (3914) | Dois fluxos independentes pro mesmo step-and-repeat. |
| D11 | **Rotação de peça 3 widgets + "Giro (graus)"** | Ctrl+[/] (1609) + propBar (2492) + card Rotação do Transformar (3938); e "Giro (graus)" no card do arquivo (4165) é OUTRO parâmetro (giro da arte) | Os 3 primeiros são a mesma ação (ok-ish); o 4º tem nome parecido e efeito diferente. |
| D12 | **Ações card do grupo é subconjunto arbitrário** | 4224: só "Alinhar esq." e "Alinhar topo" dos 6 alinhamentos | Inconsistência: parece que só existem 2 alinhamentos. |

Estado oculto correto (não são duplicatas): `_faca_mode`, `_faca_nodes`,
`_shared`, `_offset`, `_auto_smooth`, `_auto_offset`, `_rotation` — widgets
vivos só como estado/testes, consolidação 2e76dc5/QA 2.0 (4720–4722,
4764–4766, 4780–4783). **Não mexer.**

---

## 3. MAPA DE FRICÇÃO — primeira viagem (importar → quantidade → gerar → faca → exportar)

| Passo | Caminho hoje | Fricção |
|---|---|---|
| 1. Importar | Botão azul "Adicionar arquivos", Ctrl+I, drop do Explorer em qualquer lugar (2075) | **Baixa.** Visível e redundante do jeito certo. |
| 2. Quantidade | Stepper na coluna "Qtd" da tabela (3434) | Baixa. Visível; tooltip ok (1156). |
| 3. **Pôr na chapa** | (a) ARRASTAR da biblioteca pro canvas — gesto sem nenhuma pista visual; (b) menu Ferramentas → Gerar Produção / F5 — "Ferramentas" não é onde um leigo procura a ação PRINCIPAL do app | **CRÍTICA — foi exatamente onde o usuário real travou.** Não há botão, nem duplo clique, nem menu de contexto na tabela (conferido: `_table` só tem `itemSelectionChanged`, 4606). Canvas vazio não ensina nada. A ação mais importante do software é a única sem botão. |
| 4. Faca | Botão azul "Gerar Faca" na barra Faca; ajustes ao lado | Média. Botão visível, mas "Offset" é jargão (D6) e o escopo documento/arquivo só aparece na tag pequena. |
| 5. Exportar | Ribbon "Exportar" → Centro de Exportação (Ctrl+E) | Média-baixa. Visível, MAS as ações nascem desabilitadas (1864) sem explicar por quê — cinza mudo até gerar a produção. |
| 6. Ativação | Diálogo Licença: mailto pronto + "Copiar pedido"; o código de compra deve ser colado DENTRO do corpo do e-mail (licensing_dialog.py:124) | **Alta (teste real: colou o ID no lugar do código 2×).** Não há campo próprio pro código; se o mailto falha (sem cliente de e-mail), não há instrução de webmail. |

Descoberta geral: existe Tour de boas-vindas (1988), mas o usuário do teste
não chegou aos gestos por ele.

---

## 4. PROPOSTA priorizada (nada aplicado; aguardando aprovação item a item)

| # | Proposta | Custo | Risco | Resolve |
|---|---|---|---|---|
| P1 | **Botão "Colocar na chapa" na biblioteca + duplo clique na linha**, ambos chamando o MESMO caminho do drop (`_on_library_drop`/`generate(blocking=True, paths, faca=False)`) — já decidido pelo dono (Etapa 2.1) | S | Baixo (aditivo, reusa fluxo existente) | Fricção passo 3 |
| P2 | **Canvas vazio que ensina**: dica central "Adicione arquivos (Ctrl+I) e clique em Colocar na chapa", padrão `_HintView` do cut_mode_dialog — já decidido (Etapa 2.2) | S | Baixo (só aparece sem produção) | Fricção passo 3 |
| P3 | **Campo "Código de compra" na tela de ativação** entrando no mailto e no "Copiar pedido" + instrução de webmail quando o mailto falhar — já decidido (Etapa 2.3) | S | Baixo (diálogo isolado) | Fricção passo 6 |
| P4 | **Réguas (D1)**: remover o toggle solto da ribbon (1945); fica o checkbox do popup Exibição. Réguas não tem atalho nem menu — nada é perdido | S | Baixo | D1 |
| P5 | **Tooltip do botão "Exibição" (D2)**: corrigir para "Réguas e encaixe (snap)" | S | Nulo | D2 |
| P6 | **Renomear rótulos ambíguos** (só texto/tooltip, zero lógica): barra Faca "Offset" → "Sangria" (tooltip mantém "(offset)"); card do arquivo "Cantos arredondados - raio" → "Raio dos cantos" (igual à barra); biblioteca "Recortar..." → "Recortar páginas..."; "Remover selecionado" → "Remover da biblioteca"; aba Objeto "Remover" → "Excluir da chapa"; menu "Remover PDF selecionado" → "Remover arquivo da biblioteca" | S | Baixo (conferir se algum teste asserta os textos) | D6, D7, D8 |
| P7 | **Exportações desabilitadas mudas**: tooltip nas ações cinzas "Gere a produção primeiro (F5)" | S | Baixo | Fricção passo 5 |
| P8 | **Ações do grupo (D12)**: completar o card com os 6 alinhamentos (menu-botão) OU trocar por dica "use a ribbon" | M | Médio | D12 — **sugiro adiar** |
| P9 | D3, D4, D5, D9, D10, D11: espelhos funcionais com fonte única de estado — **manter como estão** (consolidar = redesign, viola a regra) | — | — | — |

Ordem sugerida de aplicação na Etapa 2: P1 → P2 → P3 (já decididos) →
P5 → P4 → P7 → P6 (item a item conforme aprovação). P8/P9 fora do escopo.
