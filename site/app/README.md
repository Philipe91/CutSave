# PrintNest Pro — Landing (React)

Landing de vendas migrada para **React + Vite + TypeScript + Tailwind CSS v4 + shadcn/ui**.
O design premium original (azul `#2563EB`, Inter, hairlines) foi preservado 1:1 — o
design system antigo vive em `src/styles/printnest.css` e o tema shadcn foi mapeado para
a nossa paleta em `src/index.css`.

## Rodar em desenvolvimento

```bash
cd site/app
npm install        # só na primeira vez
npm run dev        # sobe o Vite (http://localhost:5173)
```

## Build de produção

```bash
npm run build      # gera site estático em dist/
npm run preview    # serve o build para conferência
```

Publicação: qualquer host estático (Vercel, Netlify, Cloudflare Pages) buildando `site/app`
com `npm run build` e servindo `dist/`.

## Estrutura

```
src/
├── App.tsx                  # landing completa (todas as seções)
├── components/site/Faq.tsx  # acordeão de dúvidas (React)
├── components/ui/           # componentes shadcn/ui (button, ...)
├── styles/printnest.css     # design system original (tokens + componentes)
├── index.css                # Tailwind v4 + tema shadcn (paleta da marca)
└── lib/utils.ts             # helper cn() do shadcn
public/assets/               # logos + screenshot do app
```

## Notas

- Placeholders de copy mantidos: `[LINK_PAGAMENTO]` e `[SUPORTE]` (em `App.tsx`).
- Para adicionar componentes shadcn: `npx shadcn@latest add <componente>`.
- O site estático antigo (HTML puro) segue intacto em `site/index.html` como referência.
