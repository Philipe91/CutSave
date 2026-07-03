# Estado do Site de Vendas — PrintNest Premium

> Ponto de retomada. Se a sessão/energia acabar, comece por aqui.
> Última atualização: sessão de 03/07/2026.

---

## 0. Resumo em uma linha
Landing page de vendas **funcional e refinada** (nível Apple/Stripe) já está pronta
em `site/index.html`. Falta **conteúdo real** (prints, vídeo, preços) e a **parte
comercial/legal** (pagamento, download do .exe, páginas legais, publicação).

## Como abrir
Duplo clique em `site/index.html` (não precisa de servidor). Para live-reload:
`python -m http.server 5500` dentro de `site/` → abrir `http://localhost:5500`.

---

## 1. O que JÁ está feito ✅

### Arquivos entregues (pasta `site/`)
| Arquivo | O que é | Status |
|---|---|---|
| `index.html` | Landing completa (16 seções) | ✅ pronto e refinado |
| `styles.css` | Design system premium (tokens, componentes) | ✅ pronto |
| `assets/` | Logos + screenshot real do app | ✅ |
| `README.md` | Visão geral + roteiro | ✅ |
| `ARQUITETURA-SITE.md` | Arquitetura de informação (CPO) | ✅ |
| `UX-EXPERIENCIA.md` | UX/fluxo (Hick, Fitts, Miller…) | ✅ |
| `DESIGN-SYSTEM.md` | Tokens + specs de componentes | ✅ |
| `COPY.md` | Copy de venda + 30 FAQ + extras (ads, e-mails) | ✅ |
| `ESTADO-SITE.md` | Este documento | ✅ |

### Seções da landing (todas construídas)
Header · Hero (com print real) · Segmentos · Problema×Solução · Como funciona ·
Benefícios · Recursos · Vídeo (placeholder) · Screenshots (galeria) · Comparação ·
Depoimentos · Planos · Garantia · FAQ · CTA final · Footer.

### Refino visual aplicado (nível premium)
- **Paleta:** preto / branco / **azul `#2563EB`** (token único; sombras e foco derivam dele).
- **Ícones:** família única **Lucide** (46 SVGs) — **zero emoji**. FAQ "+" gira e vira ×;
  ✓/✕/– são check/x/minus do Lucide.
- **Padronizado:** tipografia (Inter, tracking calibrado, numerais tabulares), espaçamento
  (ritmo 4pt, seções 112px), sombras ultra-suaves, radius em escala, hover unificado,
  hairlines `#ECEDF1`, header com blur sutil, `prefers-reduced-motion`, responsivo.
- **Sem:** glassmorphism, gradiente chapado, card colorido, sombra pesada, cara de template.

### Conteúdo real já incorporado
- Screenshot **`assets/app-producao.jpg`** (produção com 435 peças / 7 chapas / 77%)
  no hero, no bloco de vídeo (poster) e no 1º slot da galeria.
- Copy fiel ao produto (faca, nesting, PDF+DXF, offline, atalhos Corel, integração Corel).

---

## 2. O que FALTA fazer ⏳

### A) Conteúdo (rápido — depende de material)
- [ ] **Prints novos** para os 3 slots da galeria (já estilizados, esperando):
  1. ⭐ **Zoom de 1 chapa** (impressão em cima + faca vermelha embaixo) — o mais forte
  2. Momento **"Gerar Faca"** (contorno acompanhando a arte)
  3. **Centro de Exportação** (PDF + DXF)
  - Extras úteis: contorno de imagem, biblioteca com arquivos, botão no CorelDRAW.
- [ ] **Vídeo/GIF** de 20–40s do fluxo (importar→faca→nesting→exportar) — substitui o placeholder.
- [ ] **Depoimentos reais** (hoje são exemplos rotulados; trocar por clientes com consentimento).

### B) Comercial (decisões + integração)
- [ ] **Definir preço** e modelo (perpétua / assinatura / híbrido) → preencher `R$ —` nos planos.
- [ ] **Escolher gateway** (Hotmart/Eduzz *ou* Mercado Pago/Stripe) e ligar os botões de compra.
- [ ] **Hospedar o instalador `.exe` assinado** e apontar os botões "Baixar".
- [ ] Fluxo de **entrega da chave** por e-mail (liga com `app/licensing/`).

### C) Legal (páginas + textos)
- [ ] `termos.html` (EULA) · `privacidade.html` (LGPD) · `reembolso.html` (7 dias).
  (Links já existem no footer, faltam as páginas. Base de texto em `COPY.md`.)

### D) Publicação
- [ ] Registrar **domínio** (ex.: `printnest.com.br`).
- [ ] Publicar (Netlify / Vercel / Cloudflare Pages / GitHub Pages — site estático).
- [ ] SEO: Open Graph/`og:image`, favicon final, sitemap; analytics/pixel se for anunciar.

### E) Bloqueador herdado (do produto, não do site)
- [ ] ⚠️ **Licença do PyMuPDF (AGPL)** — resolver antes de vender (comprar comercial da
  Artifex ou trocar a dependência). Ver `docs/produto/PLANO-COMERCIALIZACAO.md` §5.
- [ ] Code signing do instalador, EULA/LGPD, figura jurídica + nota fiscal (mesmo plano).

---

## 3. Próximo passo recomendado (quando retomar)
1. **Tirar o print "zoom de 1 chapa"** e mandar → encaixo no slot 1 da galeria (impacto imediato).
2. **Decidir preço + gateway** → preencho os planos e ligo os botões de compra.
3. Criar as **3 páginas legais** (texto-base já está no `COPY.md`).
4. **Publicar** num host estático com o domínio.

## 4. Decisões pendentes (do usuário)
| Tema | A decidir |
|---|---|
| Preço | Perpétua × assinatura × híbrido + valores |
| Gateway | Hotmart/Eduzz × Mercado Pago/Stripe |
| Domínio | Nome final + registrador |
| Hospedagem | Netlify/Vercel/Cloudflare/GitHub Pages |
| Marca | Registro "PrintNest" no INPI |

## 5. Notas técnicas
- Editar cor da marca: `--blue` no topo de `styles.css` (tudo deriva dela).
- Fonte Inter via Google Fonts (com fallback do sistema).
- Só HTML + CSS, sem framework/JS pesado. FAQ usa `<details>` nativo.
- Referências estratégicas completas nos 4 docs `.md` desta pasta.
- Nada foi commitado ainda — commit só quando o Philipe pedir ("faça commit").
