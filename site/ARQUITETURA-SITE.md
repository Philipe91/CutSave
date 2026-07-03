# PrintNest Premium — Arquitetura da Landing Page de Alta Conversão

> Documento de arquitetura de informação (não é o visual). Define **ordem, objetivo,
> conteúdo, componentes, gatilho psicológico e impacto na conversão** de cada seção.
> Base para construir o `index.html`. Público: gráficas rápidas, comunicação visual,
> bureaus, impressão digital, operadores de produção e indústria.

---

## 1. Estratégia antes das seções

### Quem chega e em que estado mental
O visitante é um **operador ou dono de gráfica** que HOJE prepara faca e encaixe na mão,
no CorelDRAW/Illustrator. Ele é cético (já viu software que promete e não entrega),
tem pressa e mede tudo em **tempo perdido e chapa desperdiçada**. Ele não quer "conhecer
uma empresa" — quer resolver uma dor concreta.

### A grande promessa (a frase que o site inteiro prova)
> **"Do arquivo do cliente à faca e ao nesting em segundos — exporta PDF de impressão + DXF de corte, 100% offline."**

### Os 3 eixos de conversão (tudo no site serve a um deles)
1. **Prova de que funciona** → screenshots e vídeos do produto real (não ilustração).
2. **Redução de risco** → offline, teste grátis, garantia, "não controla sua máquina".
3. **Redução de atrito** → CTA repetido, preço claro, "instala em minutos, atalhos do Corel".

### Regra de ouro da arquitetura
**Toda seção responde a uma objeção na ordem em que ela nasce na cabeça do visitante.**
O fluxo abaixo é essa ordem psicológica: Atenção → Dor → Alívio → Prova → Confiança → Ação.

---

## 2. Ordem oficial das seções

| # | Seção | Papel na jornada | Objeção que derruba |
|---|---|---|---|
| 0 | **Header fixo** | Orientação + CTA sempre à mão | "como compro?" |
| 1 | **Hero** | Prometer + provar em 5 segundos | "isso é pra mim?" |
| 2 | **Barra de confiança** | Micro-prova imediata | "serve pro meu segmento?" |
| 3 | **Problema** | Fazer a dor doer (espelho) | "não é tão ruim assim" |
| 4 | **Solução** | O alívio, em uma frase visual | "e como isso resolve?" |
| 5 | **Como funciona** | Mostrar que é simples (4 passos) | "vai ser complicado" |
| 6 | **Benefícios** | Traduzir recurso em resultado (R$/tempo) | "o que EU ganho?" |
| 7 | **Recursos** | Profundidade pra quem quer detalhe | "tem o que eu preciso?" |
| 8 | **Vídeo / demonstração** | Prova em movimento | "quero ver funcionando" |
| 9 | **Screenshots** | Prova estática, detalhe do produto | "é bonito/usável?" |
| 10 | **Comparação** | Ancorar contra a dor atual | "por que não continuar no Corel?" |
| 11 | **Depoimentos** | Prova social (gente como ele) | "outros confiam?" |
| 12 | **Planos / Preço** | A decisão comercial | "quanto custa?" |
| 13 | **Garantia** | Zerar o risco da compra | "e se eu não gostar?" |
| 14 | **FAQ** | Derrubar as últimas objeções | dúvidas técnicas/fiscais |
| 15 | **CTA final** | Fechar com foco único | "vou pensar depois" |
| 16 | **Rodapé** | Confiança, legal, navegação | credibilidade/legal |

> **Princípio:** a decisão de preço (12) só aparece **depois** de dor→alívio→prova.
> Mostrar preço cedo demais mata a percepção de valor. O teste grátis, porém, é
> oferecido desde o Hero (baixo risco, não exige a decisão de compra).

---

## 3. Seção a seção

### 0. Header fixo (sticky)
- **Objetivo:** orientar e manter a ação de compra a um clique, em qualquer scroll.
- **Conteúdo:** logo · links (Recursos, Como funciona, Planos, Dúvidas) · **2 CTAs**: "Ver planos" (secundário) e "Baixar teste grátis" (primário, azul).
- **Componentes:** navbar translúcida com blur; no mobile vira menu compacto + CTA primário sempre visível.
- **Gatilho psicológico:** *disponibilidade* — a saída está sempre à vista, reduz frustração.
- **Impacto na conversão:** CTA sticky costuma somar cliques ao longo de toda a página (o visitante decide em pontos diferentes).

### 1. Hero — "prometer e provar em 5 segundos"
- **Objetivo:** em um lampejo, dizer o que é, pra quem é e provar que é real.
- **Conteúdo:**
  - Pills de qualificação: **100% offline · Em português · Windows**.
  - Headline com a grande promessa (faca + nesting em segundos).
  - Subtexto de 1 frase: importa → faca → nesting → **PDF + DXF**.
  - **CTA duplo:** "Baixar teste grátis" (primário) + "Ver como funciona" (âncora).
  - Micro-reforço: "Sem cartão · Instala em minutos · Atalhos do CorelDRAW".
  - **Screenshot real do produto** (produção com 435 peças em 7 chapas, 77% de aproveitamento) numa moldura de janela + chip flutuante **PDF / DXF**.
- **Componentes:** hero centralizado, headline com palavras-âncora em destaque, imagem grande "product-first".
- **Gatilho psicológico:** *prova imediata* + *especificidade* (números reais 435/7/77% batem mais que adjetivos).
- **Impacto na conversão:** é a seção que mais pesa. Um hero com produto real e promessa específica define a taxa de rolagem para o resto.

### 2. Barra de confiança (segmentos)
- **Objetivo:** o visitante se reconhecer ("é pro meu tipo de gráfica").
- **Conteúdo:** faixa "Feito para o dia a dia da gráfica" + segmentos: Comunicação visual · Plotter de recorte · Adesivos & rótulos · Cartões & convites · Impressão digital.
- **Componentes:** linha de rótulos/ícones discretos, largura total.
- **Gatilho psicológico:** *identificação* (in-group). Substitui logos de clientes que ainda não temos.
- **Impacto:** aumenta a permanência — quem se reconhece continua lendo.

### 3. Problema — "fazer a dor doer"
- **Objetivo:** verbalizar a dor melhor do que o próprio cliente conseguiria.
- **Conteúdo (jeito antigo):** faca peça por peça na mão · encaixar "no olho" e desperdiçar chapa · refazer tudo quando muda a quantidade · faca torta que estraga o corte · exportar PDF e DXF em passos confusos.
- **Componentes:** card "Do jeito antigo" com lista de dores (ícones ✕ vermelhos).
- **Gatilho psicológico:** *aversão à perda* — dor de perder tempo/chapa é mais motivadora que o ganho.
- **Impacto:** cria a tensão que a próxima seção alivia. Sem dor, não há urgência.

### 4. Solução — "o alívio em um golpe de vista"
- **Objetivo:** contrapor cada dor com o alívio do PrintNest, lado a lado.
- **Conteúdo (com o PrintNest):** faca automática (retângulo/contorno/vetor do PDF) · nesting que aproveita a chapa toda · reencaixa em 1 clique · faca **exata por padrão** · um botão = PDF + DXF.
- **Componentes:** card escuro "Com o PrintNest" ao lado do card de dor (contraste antes/depois).
- **Gatilho psicológico:** *contraste* — o alívio só brilha ao lado da dor.
- **Impacto:** é o "clique mental" onde o valor é entendido. Alta correlação com scroll até o preço.

### 5. Como funciona — "isso é simples"
- **Objetivo:** matar o medo de "software complicado".
- **Conteúdo:** 4 passos — **1) Importe · 2) Gere a faca · 3) Encaixe (nesting) · 4) Exporte**. Uma frase cada.
- **Componentes:** 4 cards numerados com ícone; opcionalmente um screenshot por passo.
- **Gatilho psicológico:** *fluência cognitiva* — o que parece fácil parece confiável.
- **Impacto:** reduz a fricção percebida antes de pedir a compra. Prepara o terreno para "baixar e testar".

### 6. Benefícios — "o que EU ganho" (traduzir recurso → resultado)
- **Objetivo:** converter capacidade técnica em **dinheiro, tempo e tranquilidade**.
- **Conteúdo (3–4 benefícios de resultado, não de recurso):**
  - **Menos chapa no lixo** → nesting com aproveitamento medido (ex.: 77% na tela real).
  - **Horas que viram minutos** → faca e encaixe automáticos; muda quantidade, reencaixa em 1 clique.
  - **Corte sem retrabalho** → faca exata por padrão, sem "faca torta".
  - **Seus arquivos nunca saem da gráfica** → 100% offline.
- **Componentes:** 3–4 blocos com número/ícone + título de resultado + 1 linha explicando o "como".
- **Gatilho psicológico:** *interesse próprio* + *quantificação* (número concreto convence).
- **Impacto:** é onde o valor vira justificativa de compra ("paga-se com a chapa que economizo").
- **Nota de IA:** Benefícios (resultado) ≠ Recursos (funcionalidade). **Benefícios vêm antes** — vendem; recursos vêm depois — confirmam.

### 7. Recursos — "tem tudo que preciso"
- **Objetivo:** dar profundidade a quem compra por checklist técnico.
- **Conteúdo:** faca automática (3 modos + sangria/recorte/giro por arquivo) · nesting inteligente · export PDF+DXF (chapa única ou por chapa, marcas de registro) · edição estilo CorelDRAW (alinhar/distribuir/agrupar/guias/undo ilimitado) · integração CorelDRAW (botão manda do Corel) · 100% offline em português.
- **Componentes:** grade de 6 cards com ícone + título + 1 linha.
- **Gatilho psicológico:** *autoridade/competência* — abrangência transmite maturidade do produto.
- **Impacto:** converte o comprador analítico; serve de "prova de completude".

### 8. Vídeo / demonstração — "quero ver funcionando"
- **Objetivo:** provar em movimento o fluxo completo (o que print estático não mostra).
- **Conteúdo:** vídeo/GIF curto (20–40s) importar → gerar faca → nesting → exportar PDF+DXF. Um só, focado, com legenda.
- **Componentes:** player leve com thumbnail (poster) do app; play grande; autoplay mudo opcional em loop para GIF.
- **Gatilho psicológico:** *ver para crer* — movimento reduz a incerteza melhor que qualquer texto.
- **Impacto:** uma das seções de maior efeito para software; costuma elevar a intenção de baixar.
- **Nota:** enquanto não houver vídeo, esta seção usa o screenshot #1 (zoom de uma chapa) com selo "demonstração em breve".

### 9. Screenshots — "é bonito e usável"
- **Objetivo:** detalhe do produto real, respondendo "como é usar".
- **Conteúdo (galeria priorizada):** ① zoom de 1 chapa (impressão em cima + faca vermelha embaixo) · ② momento "Gerar Faca" (contorno acompanhando a arte) · ③ Centro de Exportação (PDF + DXF) · ④ contorno automático de imagem · ⑤ biblioteca com vários arquivos · ⑥ integração no CorelDRAW.
- **Componentes:** galeria/carrossel com legenda curta por print (cada legenda vende um benefício).
- **Gatilho psicológico:** *transparência* — mostrar a tela real derruba a desconfiança de "só marketing".
- **Impacto:** sustenta a credibilidade construída no hero; alimenta o comprador visual.

### 10. Comparação — "por que não continuar no Corel/na mão?"
- **Objetivo:** ancorar o PrintNest contra o status quo (não contra concorrentes nominais).
- **Conteúdo:** tabela **PrintNest × Fazer na mão (Corel/Illustrator)** nas linhas que importam: tempo de preparação, aproveitamento de chapa, faca exata, PDF+DXF num passo, mudar quantidade, offline, curva de aprendizado (atalhos do Corel).
- **Componentes:** tabela de 2 colunas com ✓/✕; PrintNest destacado em azul.
- **Gatilho psicológico:** *ancoragem* + *efeito contraste* — deixa a escolha óbvia.
- **Impacto:** desarma a objeção "já faço do meu jeito"; acelera a decisão logo antes do preço.
- **Cuidado de IA:** comparar com "método atual", não difamar produtos de terceiros (evita ruído jurídico e soa mais maduro).

### 11. Depoimentos — "gente como eu confia"
- **Objetivo:** prova social específica do segmento.
- **Conteúdo:** 2–4 depoimentos de gráficas reais (nome, cidade, tipo de gráfica, foto/logo) com resultado concreto ("economizei X% de material", "preparo o lote em minutos").
- **Componentes:** cards com aspas, avatar/logo, nome e negócio; opcional estrelas.
- **Gatilho psicológico:** *prova social* — decisivo para desktop pago; medo de comprar sozinho.
- **Impacto:** alto, especialmente perto do preço. Depoimento com número > depoimento genérico.
- **Nota:** sem depoimentos ainda → começar com 1 case do próprio uso/beta e substituir por reais o quanto antes. **Nunca inventar** depoimento.

### 12. Planos / Preço — "quanto custa"
- **Objetivo:** apresentar a decisão comercial com clareza e uma escolha recomendada.
- **Conteúdo:** Teste grátis (15 dias, com marca d'água) · **Licença perpétua** (destaque "mais popular", 1 ativação, 1 ano de updates, suporte) · Assinatura (sempre atualizado, cancele quando quiser). Valores a definir.
- **Componentes:** 3 cards; o do meio destacado (borda azul + selo). CTA em cada card.
- **Gatilho psicológico:** *ancoragem de preço* + *opção-isca* (3 planos fazem o do meio parecer o equilíbrio certo).
- **Impacto:** conversão direta. Clareza (sem "fale com vendas") reduz abandono em compra de ticket baixo/médio.
- **Notas de IA:** destacar 1 plano; máximo de 3 opções (mais que isso paralisa); sempre mostrar o que está incluído em cada; teste grátis como plano reduz o risco da decisão.

### 13. Garantia — "e se eu não gostar?"
- **Objetivo:** transferir o risco da compra do cliente para a empresa.
- **Conteúdo:** garantia de reembolso (ex.: 7 dias — direito de arrependimento do CDC, transformado em argumento) + reforço "teste grátis antes de pagar" + "sem fidelidade na assinatura".
- **Componentes:** faixa/selo de garantia com ícone de escudo, logo após o preço.
- **Gatilho psicológico:** *reversão de risco* — quando o risco é do vendedor, a barreira cai.
- **Impacto:** aumenta a conversão exatamente no ponto de maior hesitação (logo após ver o valor).

### 14. FAQ — "as últimas dúvidas"
- **Objetivo:** derrubar objeções residuais técnicas, fiscais e operacionais.
- **Conteúdo:** controla minha máquina? (não — gera PDF+DXF) · precisa de internet? (não pra trabalhar) · Mac/Linux? (Windows) · usa a faca vetorial do cliente? (sim) · vou reaprender tudo? (atalhos do Corel) · troca de PC/licença? (desativa e ativa) · emite nota fiscal? · como recebo a chave?
- **Componentes:** acordeão `<details>` nativo; primeira já aberta.
- **Gatilho psicológico:** *redução de incerteza* — cada dúvida aberta é uma venda travada.
- **Impacto:** recupera quem quase converteu; também ajuda SEO (perguntas reais).

### 15. CTA final — "fechar com foco único"
- **Objetivo:** um último empurrão, sem distração.
- **Conteúdo:** headline de fechamento ("Experimente na sua produção") + 1 frase + **CTA primário** (Baixar para Windows) e secundário (Ver planos). Sem menu, sem links dispersos.
- **Componentes:** bloco escuro em destaque, centralizado, largura total.
- **Gatilho psicológico:** *foco* + *recência* — a última coisa lida vira a ação.
- **Impacto:** captura quem rolou até o fim (alta intenção) e ainda não clicou.

### 16. Rodapé
- **Objetivo:** credibilidade, navegação e conformidade legal.
- **Conteúdo:** logo + 1 frase · colunas Produto / Suporte / Legal (EULA, Privacidade/LGPD, Reembolso) · contato · "Feito no Brasil" · © ano.
- **Componentes:** rodapé escuro em 4 colunas.
- **Gatilho psicológico:** *confiança institucional* — presença de páginas legais sinaliza empresa séria.
- **Impacto:** indireto, mas sustenta a percepção de segurança para pagar.

---

## 4. O que NÃO entra (decisões de exclusão)
Arquitetura também é cortar. **Fora da landing:**
- **História da empresa / "sobre nós" longo** → não vende software de produção; no máximo 1 frase no rodapé.
- **Blog, novidades, roadmap público** → dispersam do objetivo único (converter).
- **Detalhes técnicos internos** (stack Python/PySide6, arquitetura) → irrelevante pro comprador; some.
- **Excesso de planos** (>3) → paralisa a decisão.
- **Jargão de dev** ("nesting MaxRects", "DXF via ezdxf") → traduzir para benefício.
- **Muitos CTAs concorrentes** → a página inteira empurra para **1 ação primária** (baixar/testar); "comprar" é a evolução natural do teste.
- **Pop-ups agressivos no load** → quebram a confiança logo na entrada.

---

## 5. Sistema de CTAs (consistência é conversão)
- **CTA primário (sempre azul, mesmo texto):** *Baixar teste grátis* → o compromisso de menor risco.
- **CTA secundário (contorno):** *Ver planos* / *Ver como funciona* → para quem ainda pesquisa.
- **Repetição:** header (sticky) → hero → fim de "Solução" → após "Comparação" → dentro de cada plano → CTA final. ~6 pontos de decisão.
- **Regra:** nunca dois CTAs primários competindo na mesma dobra. Um manda, o outro apoia.

---

## 6. Wireframe textual completo (top → bottom)

```
┌──────────────────────────────────────────────────────────────────────┐
│ [LOGO PrintNest]      Recursos  Como funciona  Planos  Dúvidas        │  ← HEADER STICKY
│                                        [ Ver planos ]  [ Baixar grátis ]│
└──────────────────────────────────────────────────────────────────────┘

╔══════════════════════════════ HERO ══════════════════════════════════╗
║             ( 100% offline )  ( Em português )  ( Windows )           ║
║                                                                       ║
║      DO ARQUIVO DO CLIENTE À  *FACA*  E AO  *NESTING*  EM SEGUNDOS.    ║
║   Importa PDF/imagem, gera a faca, encaixa na chapa e exporta         ║
║              PDF de impressão + DXF de corte.                         ║
║                                                                       ║
║            [ BAIXAR TESTE GRÁTIS ]    [ Ver como funciona ]           ║
║        ✓ Sem cartão · ✓ Instala em minutos · ✓ Atalhos do Corel       ║
║                                                                       ║
║   ┌───────────────── SCREENSHOT REAL DO APP ─────────────────────┐    ║
║   │  ● ● ●  PrintNest Premium — produção em 7 chapas             │    ║
║   │  [ 435 adesivos nesting · impressão em cima · faca embaixo ] │    ║
║   │  435 peças · 7 chapas · 77% de aproveitamento               │    ║
║   └──────────────────[ PDF impressão ] [ DXF corte ]────────────┘    ║
╚═══════════════════════════════════════════════════════════════════════╝

──── BARRA DE CONFIANÇA ────
 Feito para a gráfica:  Comunicação visual · Plotter · Adesivos · Cartões · Impressão digital

╔══════════════════ PROBLEMA  ✕  SOLUÇÃO (lado a lado) ════════════════════╗
║  ┌─ DO JEITO ANTIGO ─────────┐   ┌─ COM O PRINTNEST ──────────────────┐  ║
║  │ ✕ Faca na mão, peça a peça │   │ ✓ Faca automática (3 modos)        │  ║
║  │ ✕ Encaixe "no olho"        │   │ ✓ Nesting aproveita a chapa toda   │  ║
║  │ ✕ Refaz se muda a qtd      │   │ ✓ Reencaixa em 1 clique            │  ║
║  │ ✕ Faca torta               │   │ ✓ Faca exata por padrão            │  ║
║  │ ✕ PDF e DXF em passos      │   │ ✓ 1 botão: PDF + DXF               │  ║
║  └───────────────────────────┘   └────────────────────────────────────┘  ║
║                        [ Baixar teste grátis ]                           ║
╚══════════════════════════════════════════════════════════════════════════╝

──── COMO FUNCIONA (4 passos) ────
 [1 Importe] → [2 Gere a faca] → [3 Encaixe/nesting] → [4 Exporte PDF+DXF]

──── BENEFÍCIOS (resultado, não recurso) ────
 [ Menos chapa no lixo ]  [ Horas viram minutos ]  [ Corte sem retrabalho ]  [ Offline: dados na gráfica ]

──── RECURSOS (grade 6) ────
 [🔪 Faca auto] [🧩 Nesting] [📤 PDF+DXF]
 [🎨 Edição Corel] [🔌 Integração Corel] [📴 Offline PT]

╔═══════════════ VÍDEO / DEMONSTRAÇÃO ═══════════════╗
║        ▶  Importar → Faca → Nesting → Exportar     ║
║        (loop 20–40s do fluxo real, com legenda)    ║
╚════════════════════════════════════════════════════╝

──── SCREENSHOTS (galeria com legenda) ────
 [Zoom 1 chapa: impressão+faca] [Gerar Faca] [Centro de Exportação]
 [Contorno de imagem] [Biblioteca] [Botão no CorelDRAW]

──── COMPARAÇÃO ( PrintNest × Fazer na mão ) ────
 | Critério              | PrintNest | Na mão (Corel) |
 | Tempo de preparação   |    ✓      |      ✕         |
 | Aproveitamento chapa  |    ✓      |      ✕         |
 | Faca exata            |    ✓      |      ✕         |
 | PDF + DXF num passo    |    ✓      |      ✕         |
 | Mudar quantidade       |    ✓      |      ✕         |
 | Offline                |    ✓      |      —         |

──── DEPOIMENTOS ────
 [ "Economizei X% de chapa" — Gráfica, Cidade ]  [ ... ]  [ ... ]

╔════════════════════════ PLANOS / PREÇO ════════════════════════╗
║  ┌ Teste grátis ┐   ┌── LICENÇA PERPÉTUA ──┐   ┌ Assinatura ┐  ║
║  │ R$ 0         │   │  ★ MAIS POPULAR      │   │ R$ —/mês   │  ║
║  │ 15 dias      │   │  R$ — pagamento único│   │ sempre     │  ║
║  │ [ Baixar ]   │   │  [ COMPRAR LICENÇA ] │   │ [ Assinar ]│  ║
║  └──────────────┘   └──────────────────────┘   └────────────┘  ║
╚════════════════════════════════════════════════════════════════╝

──── GARANTIA ────
 🛡  7 dias de garantia · teste grátis antes de pagar · sem fidelidade

──── FAQ (acordeão) ────
 ▸ Controla minha máquina?   ▸ Precisa de internet?   ▸ Mac/Linux?
 ▸ Usa a faca do cliente?    ▸ Vou reaprender tudo?   ▸ Troca de PC?  ▸ Nota fiscal?

╔══════════════════════════ CTA FINAL ═══════════════════════════╗
║        Experimente o PrintNest na sua produção.                ║
║        [ ⬇ BAIXAR PARA WINDOWS ]     [ Ver planos ]            ║
╚════════════════════════════════════════════════════════════════╝

┌──────────────────────────── RODAPÉ ────────────────────────────┐
│ [LOGO] +frase │ Produto │ Suporte │ Legal (EULA·Privacidade·   │
│               │         │         │ Reembolso)                 │
│ © 2026 PrintNest · Feito no Brasil 🇧🇷                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Estado atual × alvo (o que a landing já tem)
| Seção | Já existe no `index.html`? | Ação |
|---|---|---|
| Header, Hero (com print real), Confiança | ✅ | pronto |
| Problema → Solução | ✅ | pronto |
| Como funciona, Recursos, Para quem | ✅ | "Para quem" pode fundir na barra de confiança |
| Benefícios (resultado) | ⚠️ parcial | **criar seção própria** antes de Recursos |
| Vídeo | ❌ | criar (placeholder até ter o vídeo) |
| Screenshots (galeria) | ❌ | criar (usa os prints que você vai tirar) |
| Comparação | ❌ | **criar** (PrintNest × na mão) |
| Depoimentos | ❌ | criar (começa com 1 real do beta) |
| Planos | ✅ | falta preço |
| Garantia | ❌ | **criar** (faixa após o preço) |
| FAQ | ✅ | ampliar (nota fiscal, receber chave) |
| CTA final, Rodapé | ✅ | pronto |

**Prioridade de construção:** Benefícios → Comparação → Garantia → Screenshots (galeria) → Vídeo → Depoimentos.
```
```
