# PrintNest Premium — UX da Landing (entender o software em < 20s)

> Head of UX. Transforma a arquitetura em experiência simples. Objetivo:
> menos dúvidas, menos cliques, menos abandono, mais conversão.
> Princípios aplicados: **NN/g, Hick, Jakob, Fitts, Miller, Cognitive Load**.

---

## 1. Os 6 princípios e como cada um guia o design

| Princípio | O que diz | Como aplico no PrintNest |
|---|---|---|
| **Cognitive Load (Sweller)** | Memória de trabalho é limitada; corte o supérfluo | 1 ideia por seção, 1 CTA primário por dobra, frases curtas |
| **Hick's Law** | Mais opções = decisão mais lenta | 2 CTAs no máximo por bloco; 3 planos (nunca mais) |
| **Miller (7±2)** | Agrupar em blocos pequenos | Recursos em 6 cards; passos em 4; benefícios em 4 |
| **Jakob's Law** | Usuário espera o padrão que já conhece | Header com logo à esquerda + CTA à direita; FAQ acordeão; preço em 3 cards |
| **Fitts's Law** | Alvo grande e perto = clique fácil | CTAs grandes (≥48px altura), sticky no topo, largura cheia no mobile |
| **NN/g heurísticas** | Visibilidade, reconhecimento > memória, consistência | Mesmo texto/cor de CTA sempre; screenshots reais; feedback em toda interação |

**Regra dos 20 segundos:** nos primeiros 20s o visitante lê só 3 coisas —
**headline, subheadline e o print do app**. Essas três precisam responder
"o que é, pra quem é, funciona?". Todo o resto é aprofundamento opcional
(*progressive disclosure*).

---

## 2. Fluxo de leitura e hierarquia visual

**Padrão em Z / F combinado:** o olho entra no logo (topo-esq.), varre até o CTA
(topo-dir.), desce para a headline central, para no print, e a partir daí lê em F
(escaneando títulos de seção à esquerda). Por isso:
- **Títulos de seção** curtos e à esquerda/centro, alto contraste.
- **1ª linha de cada seção** carrega a mensagem (o resto é suporte).
- **Números** (435 peças, 77%, 15 dias) em destaque — âncoras visuais que o olho fisga.

**Hierarquia (3 níveis, nunca mais):**
1. Headline / número / CTA primário (o que decide).
2. Subtexto / título de card (o que explica).
3. Detalhe / legenda / microcopy (o que confirma).

---

## 3. Posição dos CTAs (Fitts + visibilidade)
- **Sticky header:** CTA primário sempre visível → decisão possível a qualquer momento.
- **Hero:** CTA primário grande, acima da dobra.
- **Fim de "Solução", após "Comparação", em cada plano, e no CTA final:** ~6 pontos.
- **Mobile:** CTA ocupa 100% da largura (alvo máximo = Fitts); nunca dois lado a lado.
- **Consistência (NN/g):** cor azul + texto "Baixar teste grátis" idênticos sempre.
  O secundário é sempre contorno/neutro — nunca compete.

---

## 4. Progressive Disclosure (revelar sob demanda)
- **FAQ** em acordeão: só o título aparece; a resposta abre no clique (reduz carga).
- **Recursos:** título + 1 linha; o detalhe técnico fica no clique/tooltip, não na página.
- **Preço:** o teste grátis vem primeiro (baixo compromisso); a compra é o passo seguinte.
- **Comparação:** tabela enxuta com as 6 linhas que importam, não 20.
> Efeito: a página parece simples, mas a profundidade está lá para quem quer.

---

## 5. Escaneabilidade
- Blocos curtos, muito respiro (whitespace = menos carga cognitiva).
- Listas com ✓/✕ em vez de parágrafos.
- Ícone + título + 1 frase nos cards.
- Contraste forte para títulos; cinza para texto de apoio.
- Nada de parágrafo com mais de 2–3 linhas.

---

## 6. Microinterações (feedback = confiança, NN/g)
| Elemento | Interação | Por quê |
|---|---|---|
| Botão | hover muda tom + leve elevação; active afunda 1px | confirma que é clicável (Fitts + feedback) |
| FAQ | "+" gira para "×" ao abrir; altura anima | mostra estado, evita confusão |
| Cards de recurso | leve subida no hover | vivacidade sem distrair |
| Print do app | zoom suave/borda no hover | convida a olhar o produto |
| Âncoras do menu | scroll suave | orientação, não teletransporte |
| Plano destacado | selo "mais popular" fixo | reduz Hick (aponta a escolha) |
> Todas rápidas (120–200ms), discretas. Microinteração serve à clareza, não ao show.

---

## 7. A jornada, seção a seção (por que existe / o que sente / dúvida / CTA / ação esperada)

**Header** · existe para orientar e manter a compra a 1 clique · sente controle · "como avanço?" · CTA *Baixar teste grátis* · ação: clicar quando decidir.

**Hero** · existe para entender tudo em 5s · sente "é exatamente meu problema" · "o que é e funciona?" · CTA *Baixar teste grátis* / *Ver como funciona* · ação: rolar ou baixar.

**Barra de segmentos** · existe para o usuário se reconhecer · sente pertencimento · "é pra minha gráfica?" · sem CTA (micro-prova) · ação: continuar lendo.

**Problema** · existe para dar nome à dor · sente "sou eu, todo dia" · "vale mudar?" · sem CTA · ação: sentir a tensão.

**Solução** · existe para aliviar · sente esperança · "como isso resolve?" · CTA *Baixar teste grátis* · ação: rolar convencido.

**Como funciona** · existe para mostrar simplicidade · sente "eu consigo usar" · "é difícil?" · CTA leve *Ver demonstração* · ação: reduzir medo.

**Benefícios** · existe para traduzir em R$/tempo · sente ganho pessoal · "o que EU ganho?" · CTA *Ver planos* · ação: justificar a compra.

**Recursos** · existe para o comprador técnico · sente competência do produto · "tem o que preciso?" · sem CTA forte · ação: marcar o checklist mental.

**Vídeo** · existe para provar em movimento · sente confiança · "funciona mesmo?" · CTA *Baixar teste grátis* · ação: querer testar.

**Screenshots** · existe para detalhe real · sente transparência · "como é usar?" · sem CTA · ação: credibilidade.

**Comparação** · existe para ancorar contra o status quo · sente "não dá pra continuar assim" · "por que trocar?" · CTA *Ver planos* · ação: decidir trocar.

**Depoimentos** · existe para prova social · sente segurança · "outros confiam?" · sem CTA · ação: baixar a guarda.

**Planos** · existe para a decisão comercial · sente clareza · "quanto custa?" · CTA *Comprar/Assinar/Baixar* · ação: escolher.

**Garantia** · existe para zerar risco · sente segurança total · "e se não gostar?" · reforço do CTA de compra · ação: comprar sem medo.

**FAQ** · existe para últimas objeções · sente "todas as dúvidas resolvidas" · técnicas/fiscais · CTA *Falar no WhatsApp* · ação: converter o hesitante.

**CTA final** · existe para fechar · sente urgência calma · "vou agir agora" · CTA *Baixar para Windows* · ação: baixar/comprar.

**Footer** · existe para confiança/legal · sente empresa séria · legitimidade · links legais · ação: segurança final.

---

## 8. Objeções × onde morrem
| Objeção | Seção que resolve |
|---|---|
| "É pra mim?" | Hero + barra de segmentos |
| "Vale a pena mudar?" | Problema + Comparação |
| "Funciona?" | Screenshots + Vídeo + números reais |
| "É difícil?" | Como funciona + atalhos do Corel |
| "Controla minha máquina?" | FAQ (não; gera PDF+DXF) |
| "Preciso de internet?" | Hero (offline) + FAQ |
| "Quanto custa?" | Planos |
| "E se não gostar?" | Garantia + teste grátis |
| "É empresa séria?" | Depoimentos + Footer legal |

---

## 9. Lead capture, demonstração, download, licenciamento

- **Lead capture (leve):** o e-mail é pedido **no download do teste**, não antes.
  Formulário mínimo: e-mail (1 campo) → link do instalador. *Cognitive load* mínimo,
  e o lead entra na sequência de onboarding.
- **Demonstração:** vídeo autoexplicativo na página (não exige agendar). Para
  enterprise/indústria, botão discreto "Agendar demonstração" (só se houver time).
- **Download:** botão único → página `/download` (SO detectado = Windows) → e-mail →
  instalador assinado. Feedback claro de progresso e "próximos passos" (instalar, ativar).
- **Licenciamento:** explicado em linguagem humana no FAQ e na página `/licenca`:
  1 chave = 1 PC; desativar num e ativar em outro; reset de assento pelo suporte.
  Fluxo espelha eCut/CorelDRAW (*Jakob* — o usuário já conhece o modelo).

---

## 10. Fluxo completo do usuário — da entrada à compra

```
ENTRADA (anúncio / busca / indicação)
   │
   ▼
HERO ── lê headline + vê o print (5s) ──► "é o meu problema"
   │                                         │
   │ (quer testar já) ─────────────► [Baixar teste grátis]
   │                                         │
   ▼ (quer entender)                         ▼
PROBLEMA → SOLUÇÃO → COMO FUNCIONA     PÁGINA /download
   │   sente a dor e o alívio                │ e-mail (1 campo)
   ▼                                         ▼
BENEFÍCIOS → RECURSOS → VÍDEO           instalador (.exe assinado)
   │   "eu ganho tempo e chapa"              │ instala em minutos
   ▼                                         ▼
COMPARAÇÃO → DEPOIMENTOS                app abre em modo TRIAL (15 dias)
   │   "não dá pra continuar na mão"         │ usa no trabalho real
   ▼                                         ▼
PLANOS → escolhe (perpétua destaque)   sequência de ONBOARDING (e-mail)
   │                                         │  dica 1, 2, 3 + "ative agora"
   ▼                                         ▼
GARANTIA (7 dias) zera o risco         decide comprar ◄─────────┐
   │                                         │                  │
   ▼                                         ▼                  │
[COMPRAR] ──► CHECKOUT (gateway) ──► PAGAMENTO ──► e-mail com a CHAVE
   │                                         │                  │
   │ (abandonou?) ──► sequência de RECUPERAÇÃO DE CARRINHO ─────┘
   ▼
PÁGINA /obrigado → cola a chave no app → [Ativar] → LIBERADO no PC
   │
   ▼
CLIENTE ATIVO → suporte + atualizações + (upsell futuro)
```

**Métrica-chave por etapa:** % que rola além do hero → % que clica em baixar →
% que instala → % que ativa trial → % trial→compra → % que ativa a licença.
Cada seção acima existe para mover um desses números.
