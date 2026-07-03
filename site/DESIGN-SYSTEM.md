# PrintNest Premium — Design System

> Principal Product Designer. Identidade própria: **premium, tecnológica,
> minimalista, industrial**. Referências de rigor: Apple, Stripe, Vercel, Linear,
> Framer, Raycast, Arc, Adobe. **Azul (primária) · Branco (secundária) · Preto (base).**
> Proibido: gradiente exagerado, neumorphism, glassmorphism, cards coloridos,
> excesso de sombra, cara de Bootstrap/Material.

---

## 1. Filosofia
Minimalismo industrial: **muito branco, tipografia forte, uma cor de destaque**.
A cor (azul) é usada como *tinta de precisão* — só onde há ação ou dado crítico.
Estrutura por **hairlines (bordas de 1px)** e **espaço**, não por sombras e caixas
coloridas. O produto (screenshots do app) é o herói visual; a UI do site recua.

---

## 2. Cores (tokens)

```
/* Base — preto / neutros */
--black:      #0A0A0B;   /* texto principal, seções escuras */
--ink:        #16181D;   /* títulos */
--gray-900:   #1F2228;
--gray-600:   #4A4E57;   /* texto de apoio */
--gray-400:   #8A9099;   /* legendas, placeholder */
--gray-200:   #E7E8EC;   /* hairlines / bordas */
--gray-100:   #F3F4F6;   /* fundo de seção alternado */
--white:      #FFFFFF;   /* secundária / base clara */

/* Primária — azul (da logo) */
--blue:       #0B5CFF;
--blue-600:   #0A4FE0;   /* hover */
--blue-700:   #093FB4;   /* active */
--blue-050:   #EEF3FF;   /* wash sutil (uso raro) */

/* Sinal */
--positive:   #12B76A;   /* ✓ ganhos */
--negative:   #E5484D;   /* ✕ dores */
--focus:      #0B5CFF;   /* anel de foco */
```
Regra: **90% preto/branco/cinza, 10% azul**. Sem gradiente de fundo colorido —
no máximo um preto→azul-escuro discreto em 1 ou 2 seções escuras.

---

## 3. Grid e layout
- **Container:** máx. `1200px`, padding lateral `24px` (mobile) / `32px` (desktop).
- **Grid:** 12 colunas, gutter `24px`.
- **Breakpoints:** `≤640` (mobile 1 col) · `641–1024` (tablet 2 col) · `≥1025` (desktop).
- **Ritmo vertical (section padding):** `96px` desktop, `64px` mobile. Seção "hero" `80px` topo.
- Alinhamento: conteúdo textual em coluna estreita (máx. `720px`) para leitura confortável.

## 4. Espaçamento (escala 4pt)
`4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 · 128`
- Dentro de componente: 4–16. Entre componentes: 24–32. Entre seções: 96.
- **Whitespace é feature**, não sobra. Nunca "encher" espaço.

## 5. Tipografia
- **Fonte:** Inter (fallback: -apple-system, Segoe UI, Roboto). Numerais tabulares nos preços/dados.
- **Escala (desktop):**
  - Display/H1: `56–64px` / peso 800 / tracking `-0.03em` / line-height 1.05
  - H2 seção: `36–40px` / 800 / `-0.02em`
  - H3 card: `18–20px` / 700
  - Body grande (lead): `18–19px` / 400 / line-height 1.6 / cor gray-600
  - Body: `15–16px` / 400
  - Legenda/microcopy: `13px` / 500 / gray-400
  - Eyebrow: `12px` / 700 / uppercase / tracking `0.1em` / azul
- **Regra Apple:** frases curtas, muito peso no título, corpo leve e cinza.

## 6. Radius
`--r-sm: 8px` (badge, input) · `--r-md: 12px` (botão, card) · `--r-lg: 16px`
(painel, screenshot) · `--r-pill: 999px` (pills/segmentos).
Consistente e moderado — nem quadrado seco, nem arredondado "app fofo".

## 7. Sombras / elevação (mínimas)
```
--e0: none;                                    /* padrão: usar borda, não sombra */
--e1: 0 1px 2px rgba(10,10,11,.04);            /* card hover sutil */
--e2: 0 8px 24px rgba(10,10,11,.08);           /* screenshot / pricing destaque */
--e3: 0 24px 60px rgba(10,20,50,.14);          /* modal / hero frame */
```
Estrutura vem de `1px solid var(--gray-200)`. Sombra só para separar do fundo,
nunca decorativa.

## 8. Ícones
- Estilo **line / stroke 1.5–2px, monocromático** (herda a cor do texto), 24px.
- Sem ícones coloridos "3D". Um traço só. Azul apenas quando o ícone É o CTA.
- Biblioteca sugerida: Lucide/Feather (consistência de traço).

---

## 9. Componentes (padding · margin · radius · hover · focus · disabled · loading · elevation)

### Botão
- **Primário (azul):** bg `--blue`, texto branco. padding `14px 24px`. radius `12px`.
  hover `--blue-600` + `translateY(-1px)`. active `--blue-700` + `translateY(0)`.
  focus: anel `0 0 0 3px rgba(11,92,255,.35)`. disabled: `--gray-200`/gray-400, sem sombra.
  loading: spinner 16px + texto "Aguarde"; largura travada (sem "pulo"). elevation e0→e1 no hover.
- **Secundário:** bg branco, borda `1px --gray-200`, texto ink. hover borda azul + texto azul.
  focus igual. disabled: texto gray-400. sem elevação.
- **Terciário (texto):** só texto azul + sublinhado no hover. Para links de ação leve.
- Altura mínima `48px` (Fitts). Mobile: largura 100%.

### Card genérico
- padding `28px`. radius `12px`. borda `1px --gray-200`. bg branco. margin: gutter 24.
- hover: borda `--gray-300` + elevation e1 + `translateY(-3px)` (150ms). focus-within: anel.
- **Nunca fundo colorido.** Destaque por borda/tipografia.

### Feature card
- padding `28px 24px`. ícone line 24px em quadrado `44px` de borda hairline (não preenchido de cor).
  título H3 + 1 linha gray-600. hover como card. elevation e0→e1.

### Input
- altura `48px`. padding `12px 14px`. radius `8px`. borda `1px --gray-200`. bg branco.
  focus: borda azul + anel `0 0 0 3px blue@20%`. placeholder gray-400.
  disabled: bg gray-100. erro: borda `--negative` + mensagem 13px vermelha. loading: ícone spinner à direita.

### Navbar
- altura `64px`. bg branco **sólido** (sem blur/glass), borda inferior `1px --gray-200`.
  sticky. logo 26px à esquerda; links gray-600 (hover ink); à direita 1 secundário + 1 primário.
  scroll: mantém, some a sombra (fica só a hairline). mobile: logo + CTA primário + menu "hambúrguer".

### Footer
- bg `--black`. texto gray-400. padding `64px 0 32px`. 4 colunas + linha inferior.
  links hover → branco. logo invertido. hairline `rgba(255,255,255,.08)`.

### Badge / Pill (segmento)
- padding `7px 13px`. radius pill. borda `1px --gray-200`. texto 13px/600 ink.
  variante "status": ponto verde 7px + texto. Sem preenchimento colorido.

### FAQ (accordion)
- item: borda `1px --gray-200`, radius `12px`, margin-bottom `10px`, bg branco.
  summary padding `20px 24px`, peso 700. ícone "+" azul → gira 45° (vira ×) no open.
  resposta padding `0 24px 22px`, gray-600. hover: bg gray-100. focus: anel no summary.

### Timeline / Como funciona
- 4 nós numerados. número em quadrado `40px`, borda hairline, azul. conector: linha 1px gray-200
  (desktop horizontal, mobile vertical). cada nó: título H3 + 1 linha. Sem cards pesados.

### Pricing
- 3 cards. radius `16px`. padding `32px`. borda hairline; **destaque** = borda `2px --blue` +
  elevation e2 + selo pill azul "Mais popular" no topo. preço em numeral tabular grande (40px/800).
  lista com ✓ (positive) / — (gray-400) e hairline entre linhas. CTA full-width no rodapé do card.
  hover no card não-destacado: borda azul sutil.

### Testimonial
- card branco, borda hairline, radius `12px`, padding `28px`. aspas discretas. texto 16px ink.
  rodapé: avatar/inicial 40px (círculo neutro) + nome (700) + negócio/cidade (13px gray-400).
  opcional: número em destaque azul ("−32% de desperdício"). Sem estrelas berrantes.

### CTA (bloco)
- seção `--black` (ou preto→azul-escuro **muito** sutil), texto branco, centralizado, radius `16px`,
  padding `64px 40px`. 1 primário azul + 1 secundário contorno claro. elevation e0 (o contraste já separa).

### Hero
- fundo branco, sem gradiente colorido chapado. eyebrow/pills → H1 → lead (gray-600, máx 640px)
  → 2 CTAs → microprova → **screenshot do app** em frame escuro (radius 16, elevation e3, barra de
  janela com 3 pontos). O produto real é o ponto focal. Nada compete com ele.

---

## 10. Como cada seção deve parecer (descrição visual)

- **Header:** branco sólido, hairline embaixo, logo + 4 links discretos + CTA azul. Silencioso.
- **Hero:** muito ar; título preto enorme com "faca" e "nesting" em azul; print do app numa moldura
  escura flutuando sobre o branco; chip PDF/DXF na borda inferior. Sensação: Stripe/Linear.
- **Segmentos:** faixa fina, texto cinza uppercase centralizado + rótulos. Quase invisível, só ancora.
- **Problema × Solução:** duas colunas. Esquerda branca (dores, ✕ vermelho fino). Direita **preta**
  (ganhos, ✓ verde). O contraste preto/branco É o recurso — sem gradientes.
- **Como funciona:** faixa branca, 4 números azuis em quadrados hairline conectados por linha fina.
- **Benefícios:** 3–4 blocos grandes com um NÚMERO azul gigante (−32%, 8×, 0) + frase de resultado.
- **Recursos:** grade 3×2, cards brancos com ícone line monocromático. Regular, técnico, calmo.
- **Vídeo:** bloco escuro largo, player minimalista, botão play azul, legenda embaixo.
- **Screenshots:** carrossel/grade de prints reais em frames escuros, legenda de 1 linha cada.
- **Comparação:** tabela minimalista, 2 colunas (Sem × Com), coluna PrintNest com fundo azul-wash
  levíssimo e ✓ azuis; a outra com ✕ cinza. Hairlines entre linhas.
- **Depoimentos:** 3 cards brancos sóbrios, foco no texto e no número de resultado.
- **Planos:** 3 cards, o do meio com borda azul e leve elevação; preços em tabular; muito branco.
- **Garantia:** faixa clara com ícone de escudo line + 1 frase forte. Curta.
- **FAQ:** coluna estreita centralizada, acordeões hairline, "+" azul.
- **CTA final:** bloco preto de ponta a ponta, título branco, 1 botão azul. Foco absoluto.
- **Footer:** preto, 4 colunas cinza, logo invertido, legal visível. Sério e discreto.

---

## 11. Acessibilidade (NN/g)
- Contraste AA: texto ink/gray-600 sobre branco ✓; branco sobre preto/azul ✓.
- Foco sempre visível (anel azul 3px) — nunca `outline:none` sem substituto.
- Alvos ≥ 44×44px. `prefers-reduced-motion` → desliga animações.
- Ícones sempre com rótulo/aria. Imagens com alt descritivo (ex.: o print da produção).
