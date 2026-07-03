# Site de vendas — PrintNest

Base do site comercial do PrintNest. Landing page pronta para apresentar o
produto e receber o fluxo de venda (compra → entrega da licença).

> **📌 Comece pelo [`ESTADO-SITE.md`](ESTADO-SITE.md)** — é o ponto de retomada, com o
> estado atual e o que falta.

> A parte **legal/técnica** de virar produto (licenciamento, code signing, EULA,
> gateway de pagamento) está descrita em
> [`../docs/produto/PLANO-COMERCIALIZACAO.md`](../docs/produto/PLANO-COMERCIALIZACAO.md).
> Este `site/` é a peça **6.1 (site/landing)** daquele plano.

---

## ⚠️ O site agora é React (migrado em 03/07/2026)

A landing foi migrada de HTML+CSS puro para **React + Vite + TypeScript + Tailwind v4 +
shadcn/ui**. O projeto ativo é **`site/app/`**. O visual premium foi preservado 1:1.

```
site/
├── app/            # 👈 SITE ATIVO (React/Vite). Ver site/app/README.md
├── index.html      # site estático ANTIGO (HTML puro) — só referência/backup
├── styles.css      # CSS do site antigo — só referência
├── assets/         # logos + screenshot (copiados para app/public/assets)
├── ESTADO-SITE.md  # ponto de retomada (comece aqui)
├── ARQUITETURA-SITE.md · UX-EXPERIENCIA.md · DESIGN-SYSTEM.md · COPY.md  # estratégia
└── README.md       # este arquivo
```

### Como rodar (site ativo, React)
```bash
cd site/app
npm install     # só na primeira vez
npm run dev     # abre em http://localhost:5173
npm run build   # gera dist/ para publicar
```

### Site antigo (referência)
Ainda abre com `python -m http.server 5500` dentro de `site/`, mas não é mais o site de verdade.

---

## O que falta para virar um site de vendas de verdade

Cada item vira uma tarefa nossa. Ordem sugerida:

### 1. Conteúdo e prova
- [ ] Trocar o **mock do app** (bloco `.app-mock` no hero) por **screenshots reais** do PrintNest.
- [ ] Adicionar um **vídeo curto** (GIF/loop) do fluxo importar → faca → nesting → export.
- [ ] Depoimentos de gráficas que testaram (prova social).

### 2. Preços (bloco `#planos`)
- [ ] Definir o modelo: **licença perpétua**, **assinatura** ou os dois.
- [ ] Preencher os valores (`R$ —`) no `index.html`.
- [ ] Ligar cada botão “Comprar/Assinar” ao **gateway** (Hotmart / Eduzz / Mercado Pago / Stripe).

### 3. Download e licença
- [ ] Hospedar o **instalador assinado** (`.exe`) e apontar os botões “Baixar” para ele.
- [ ] Página/fluxo pós-compra que **entrega a chave** de licença por e-mail
      (ver módulo `app/licensing/` e a seção 1 do plano de comercialização).

### 4. Legal (links no footer já existem, faltam as páginas)
- [ ] `termos.html` — EULA (contrato de licença de uso).
- [ ] `privacidade.html` — Política de Privacidade (LGPD; coleta e-mail + fingerprint).
- [ ] `reembolso.html` — Política de reembolso (CDC, 7 dias).

### 5. Publicação
- [ ] Registrar o **domínio** (ex.: `printnest.com.br`).
- [ ] Publicar (site estático: **Netlify**, **Vercel**, **Cloudflare Pages** ou **GitHub Pages**).
- [ ] SEO básico: já há `<title>` e `meta description`; falta Open Graph, favicon final e sitemap.
- [ ] Pixel/analytics (Google Analytics / Meta) se for anunciar.

---

## Decisões pendentes (nossas)

| Tema | A decidir |
|---|---|
| Preço | Perpétua x assinatura x híbrido, e os valores |
| Gateway | Hotmart/Eduzz (entrega automática) x Mercado Pago/Stripe (webhook próprio) |
| Domínio | Nome final e onde registrar |
| Hospedagem | Netlify/Vercel/Cloudflare/GitHub Pages |
| Marca | Registro “PrintNest” no INPI (ver plano, item 5) |

---

## Notas de design

- **Cores** em `:root` no topo do `styles.css` — mude ali para reajustar a paleta inteira.
  Azul da marca `--blue: #0B5CFF`; navy `--navy: #0A1220`.
- Fonte **Inter** via Google Fonts (com fallback para fontes do sistema).
- Layout **responsivo** (breakpoints em 900px e 560px).
- Zero framework/JS pesado — só HTML + CSS. O acordeão do FAQ usa `<details>` nativo.
