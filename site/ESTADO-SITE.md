# Estado do Site de Vendas — PrintNest Pro

> Ponto de retomada. Se a sessão/energia acabar, comece por aqui.
> Última atualização: sessão de 03/07/2026 (migração para React).

> **⚠️ MUDANÇA GRANDE nesta sessão:** o site foi **migrado de HTML+CSS puro para
> React + Vite + TypeScript + Tailwind v4 + shadcn/ui**. O novo projeto vive em
> **`site/app/`**. O site estático antigo continua **intacto** em `site/index.html`
> (serve de referência/backup). A copy foi atualizada: sem travessões, e "chapa/adesivo"
> virou "material / máquina de corte" (serve para plotter, router, laser e outras).

---

## 0. Resumo em uma linha
Landing de vendas **funcional, refinada e agora em React/shadcn** (`site/app/`), com o
mesmo visual premium de antes (nível Apple/Stripe). Falta **conteúdo real** (prints extras,
vídeo, depoimentos), a **parte comercial/legal** (pagamento, download do .exe, páginas
legais) e **publicar**.

## Como rodar (IMPORTANTE — mudou!)
O site não é mais "abre com dois cliques". Precisa de Node.js (já instalado: v24).

```bash
cd site/app
npm install     # só na primeira vez (ou na primeira vez em casa)
npm run dev     # abre em http://localhost:5173
```

- Build de produção: `npm run build` → gera `site/app/dist/` (site estático).
- Conferir o build: `npm run preview`.
- O site **antigo** (HTML puro) ainda pode ser aberto com `python -m http.server 5500`
  dentro de `site/`, mas ele é só referência agora.

---

## 1. O que JÁ está feito ✅

### Migração para React (nesta sessão)
| Item | Status |
|---|---|
| Scaffold Vite + React + TypeScript em `site/app/` | ✅ |
| Tailwind CSS v4 (plugin oficial do Vite) + path alias `@/` | ✅ |
| shadcn/ui inicializado (preset Nova, base Radix) | ✅ |
| Tema shadcn mapeado para a marca (azul `#2563EB`, fonte Inter) | ✅ |
| Design system original preservado em `src/styles/printnest.css` | ✅ |
| Landing portada 1:1 (`src/App.tsx` + `src/components/site/Faq.tsx`) | ✅ |
| `npm run build` passando (TS estrito + bundle) | ✅ |
| Validação visual no Chrome (hero, preço, FAQ, recursos) | ✅ idêntico ao original |

### Estrutura do app (`site/app/`)
```
src/
├── App.tsx                  # landing completa (todas as seções)
├── components/site/Faq.tsx  # acordeão de dúvidas (React, 1º item aberto)
├── components/ui/           # componentes shadcn/ui (button, ...)
├── styles/printnest.css     # design system original (tokens + componentes)
├── index.css                # Tailwind v4 + tema shadcn (paleta da marca)
└── lib/utils.ts             # helper cn() do shadcn
public/assets/               # logos + screenshot do app (app-producao.jpg)
```

### Seções da landing (8 seções do brief oficial)
Header · **1** Hero (print real + CTA R$ 397) · **2** O Problema · **3** A Solução
(5 recursos) · **4** Por que PrintNest (4 cards) · **5** Como funciona (3 passos) ·
**6** Preço (card único R$ 397 + âncora de valor + garantia) · **7** FAQ (7 perguntas) ·
**8** CTA final · Requisitos · Footer.

### Copy já atualizada nesta sessão
- **Sem travessões** (—) no texto; escrita mais profissional e cativante.
- **Não fala mais em "chapa/adesivo"** como se fosse só isso: usa "material",
  "área/perímetro que você define" e deixa claro que a faca serve para **qualquer
  máquina de corte** (plotter de recorte, router, laser, mesa de corte, IECHO, Mimaki…).
- Adesivos aparecem só como **um exemplo** dentro de uma lista maior.

### Docs de estratégia (referência, não vão pro ar)
`ARQUITETURA-SITE.md` · `UX-EXPERIENCIA.md` · `DESIGN-SYSTEM.md` · `COPY.md`.
> Obs.: esses docs foram escritos assumindo "teste grátis 15 dias + 3 planos". A decisão
> atual é **R$ 397, licença vitalícia, sem trial, garantia 7 dias**. Estão desatualizados
> nesse ponto — atualizar quando sobrar tempo (baixa prioridade).

---

## 2. O que FALTA fazer ⏳

### A) Seções novas (agora fáceis com React/shadcn/21st)
- [ ] **Depoimentos** (prova social) — cards ou marquee. **Nunca inventar**; usar reais com consentimento.
- [ ] **Comparação** "Na mão × Com o PrintNest" (tabela).
- [ ] **Galeria de screenshots** (3+ prints) com legenda por benefício.
- [ ] **Vídeo/GIF** de 20–40s do fluxo (importar→faca→nesting→exportar).
- [ ] (opcional) Seção de **Benefícios** (resultado em R$/tempo) antes de Recursos.
> Base React pronta: dá pra colar componentes do shadcn/21st direto. Ver nota do 21st abaixo.

### B) Conteúdo real (depende de material do Philipe)
- [ ] **Prints novos** para a galeria (⭐ zoom de 1 chapa; momento "Gerar Faca"; Centro de Exportação).
- [ ] **Vídeo** do fluxo real.
- [ ] **Depoimentos** de clientes reais.

### C) Comercial (decisões + integração)
- [x] **Preço definido:** R$ 397, pagamento único, licença vitalícia, garantia 7 dias.
- [ ] **Preencher `[LINK_PAGAMENTO]`** (2 lugares em `src/App.tsx`: card de preço + CTA final).
- [ ] **Preencher `[SUPORTE]`** (2 lugares em `src/App.tsx`: requisitos + footer) com WhatsApp/e-mail.
- [ ] **Escolher gateway** (Hotmart/Eduzz *ou* Mercado Pago/Stripe) e gerar o link.
- [ ] **Hospedar o instalador `.exe` assinado** + fluxo de entrega da chave (liga com `app/licensing/` do produto).

### D) Legal (páginas + textos)
- [ ] `termos` (EULA) · `privacidade` (LGPD) · `reembolso` (7 dias).
  (Links no footer ainda apontam para `#`. Base de texto em `COPY.md`.)
  Em React, viram rotas/páginas — decidir se vale trazer um router (react-router) ou páginas estáticas.

### E) Publicação
- [ ] Registrar **domínio** (ex.: `printnest.com.br`).
- [ ] Publicar: host estático buildando `site/app` com `npm run build` e servindo `dist/`
      (**Vercel / Netlify / Cloudflare Pages** detectam Vite automaticamente).
- [ ] SEO: Open Graph/`og:image`, favicon final, sitemap; analytics/pixel se for anunciar.

### F) Bloqueador herdado (do produto, não do site)
- [ ] ⚠️ **Licença do PyMuPDF (AGPL)** — resolver antes de vender. Ver `docs/produto/PLANO-COMERCIALIZACAO.md` §5.
- [ ] Code signing do instalador, EULA/LGPD, figura jurídica + nota fiscal.

---

## 3. Próximo passo recomendado (quando retomar em casa)
1. `cd site/app && npm install && npm run dev` → conferir que abre.
2. Preencher `[LINK_PAGAMENTO]` e `[SUPORTE]` no `src/App.tsx` (quando tiver gateway/contato).
3. Adicionar as **seções novas** (comparação → garantia → galeria → depoimentos → vídeo).
4. Criar as **páginas legais**.
5. **Publicar** num host estático com o domínio.

## 4. Decisões pendentes (do usuário)
| Tema | A decidir |
|---|---|
| Gateway | Hotmart/Eduzz × Mercado Pago/Stripe |
| Domínio | Nome final + registrador |
| Hospedagem | Vercel/Netlify/Cloudflare Pages |
| Router legal | react-router × páginas estáticas soltas |
| Marca | Registro "PrintNest" no INPI |

## 5. Notas técnicas
- **Cor da marca:** `--blue` no `src/styles/printnest.css` (tudo deriva dela). O tema shadcn
  (azul primário) está em `src/index.css` (`--primary` em oklch).
- **Fonte Inter** via Google Fonts no `site/app/index.html`.
- **Adicionar componente shadcn:** `npx shadcn@latest add <componente>` dentro de `site/app`.
- **MCP 21st.dev:** foi adicionado nesta sessão (`claude mcp add ... 21st`). As ferramentas
  dele só carregam **reiniciando o Claude Code**. Depois de reiniciar, dá pra buscar
  componentes (heroes, testimonials, pricing…) e colar no React. ⚠️ A API key do 21st foi
  colada no chat — considerar **rotacionar** por segurança.
- **README do app:** instruções completas em `site/app/README.md`.
- Nada foi commitado ainda — commit só quando o Philipe pedir ("faça commit").
