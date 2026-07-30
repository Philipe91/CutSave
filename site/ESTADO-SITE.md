# Estado do Site de Vendas — PrintNest Pro

> Ponto de retomada. Se a sessão/energia acabar, comece por aqui.
> Última atualização: sessão de 28/07/2026 (hero "o nesting acontecendo").

> **⚙️ HERO DO PRODUTO (28/07).** Depois de o Philipe recusar 6 heroes seguidos
> (editorial, monitor CSS, azul Qexal, aurora escura, claro, branco, grade), a
> conclusão foi: **o catálogo do 21st.dev não tem hero "de produto", tem fundo
> bonito** — aurora, shader, grade, partícula. Serve igual para nesting, cripto
> ou academia, e é por isso que nenhum pegava. A saída foi fazer o hero **com o
> produto**, não com um efeito atrás dele.
>
> **`components/pn/NestingStage.tsx`** desenha a chapa do PrintNest com 12 peças
> reais entrando voando, encaixando, a faca desenhando o contorno em volta e o
> aproveitamento subindo até 88%. Ciclo de ~9,5 s, em laço. Com
> `prefers-reduced-motion` vai direto para o estado final e não repete.
>
> **As peças são de verdade.** `scripts/gerar-pecas-hero.py` pega os adesivos de
> `Downloads`, **descarta o fundo branco** (é o que o app faz com PNG/JPG de
> fundo branco: o alfa vinha 100% opaco, então o primeiro try com alfa devolvia
> retângulos de 4 nós), extrai o **maior contorno externo com cv2**, simplifica
> com `approxPolyDP`, empurra os pontos para fora do centro (a sangria) e grava
> tudo em `components/pn/pecas.ts` como path SVG normalizado numa viewBox de
> largura 100. O traço vermelho do hero é o contorno real daquela arte.
>
> **Seletor de heroes segue ativo** (canto inferior direito e `?hero=`), com
> `produto` como padrão e as 5 peles antigas ao lado para comparação. Quando o
> Philipe bater o martelo: apagar `.pn-hero-switch` do CSS, o bloco do seletor
> no `Landing.tsx`, o `useHeroSkin` e deixar `HERO_SKINS` com uma entrada só.

> **🌌 HERO AURORA (28/07).** O Philipe pediu para procurar um hero profissional
> no **21st.dev**. Baixei as 175 prévias da categoria Heroes, montei folhas de
> contato e revisei uma a uma. Finalistas apresentados: `preetsuthar17/hero-2-1`
> (aurora escura), `ruixen.ui/hero-section-with-gradient` (claro) e
> `shadcnblockscom/hero-195` (branco). **Escolha: aurora escura.**
> Reconstruído no nosso código (nada copiado):
> - `.pn-hero` virou **escuro** (`#080b12`) com uma **aurora** de quatro manchas
>   radiais borradas (azul da marca + violeta + ciano + rosa) que gira devagar,
>   mais uma vinheta que garante o contraste do texto.
> - Layout **centralizado**: selinho, manchete grande, subtítulo, dois botões
>   pílula e a **janela do software grande logo abaixo**, com brilho azul atrás e
>   a moldura vestindo pele escura (`.pn-hero-shot .pn-frame-bar`).
> - A copy entra em **cascata** no carregamento (`pn-rise`, atrasos por filho) e
>   a janela sobe depois. O carrossel de 3 telas continua funcionando dentro.
> - O corte hero escuro → corpo claro é proposital; o header segue **branco**.
> - ⚠️ Ao reescrever o bloco `/* hero */` inteiro eu apaguei sem querer as regras
>   de `.pn-hero-shot` e `.pn-hero-caption`, e os `replace` seguintes falharam em
>   silêncio. Foram recriadas depois da seção da moldura. Se algo do hero sumir,
>   conferir se a regra existe no CSS compilado antes de investigar outra coisa.
> - Obs. de captura: screenshot headless com `--disable-gpu` mostra a janela do
>   hero **em branco** (a combinação blur + z-index negativo não compõe sem GPU).
>   Não é bug do site: com GPU ligada renderiza normal.

> **🔍 VISUALIZADOR + HERO ANIMADO + COREL (28/07).** Três pedidos do Philipe:
> - **Visualizador (lightbox):** as capturas apareciam pequenas demais. Agora
>   **toda imagem marcada com `data-zoom`** abre em tela cheia ao clique, e um
>   segundo clique mostra **em tamanho real (1:1)** com rolagem, para o cliente
>   ler a interface. Esc e o X fecham; o `body` trava o scroll enquanto aberto.
>   O hook `useLightbox()` usa **um listener delegado no documento**, então basta
>   pôr `data-zoom` + `data-caption` em qualquer `<img>` nova: não precisa passar
>   props. Legenda e dica de uso aparecem embaixo.
> - **Hero animado:** `HeroWindow` troca sozinho entre **3 capturas reais**
>   (impressão e corte, job de 870 peças, marcas de registro) a cada 5,2 s, com
>   fade, bolinhas clicáveis, contador "1 de 3" e legenda que muda junto. Pausa
>   no hover e **não roda** com `prefers-reduced-motion`. As três imagens têm a
>   mesma proporção (2200×866) de propósito: a `.pn-slides` usa `aspect-ratio`
>   fixo para a altura não pular na troca. A janela entra deslizando e os
>   círculos do fundo derivam devagar.
> - **Seção CorelDRAW:** `plugin-corel.webp` saiu da galeria e virou bloco
>   próprio ("Você nem precisa sair do Corel"), listando as 6 macros que a
>   instalação registra. A galeria caiu para 2 colunas (miniaturas maiores) e o
>   item largo usa `.is-wide` para ocupar a linha inteira.

> **📸 CAPTURAS 28/07 — as 14 imagens de `site/assets/print screen/`.** O Philipe
> gravou telas do app rodando jobs reais e pediu para organizar todas no site.
> Processadas para WebP em `app/public/assets/app/` (barra de título do Windows
> cortada nas janelas inteiras: a moldura do site já desenha a dela).
> Mapa do que cada uma virou:
> | origem | destino | onde entrou |
> |---|---|---|
> | nest 03 | `chapa-dividida.webp` | hero (198 peças, 1 chapa, 88%) |
> | nest 01 | `chapa-cheia.webp` | galeria |
> | nest 02 | `faca-circular.webp` | galeria |
> | faca (antiga) | `faca.webp` | bloco Faca (contorno irregular) |
> | tipos de facas | `menu-tipos-faca.webp` | detalhe do bloco Faca |
> | varios pdfs 2 | `escala-dividida.webp` | bloco Nesting (870 peças, 7 chapas, 98%) |
> | varios pdfs 1 | `escala-chapa.webp` | galeria |
> | nest 04 | `registro-chapa.webp` | bloco Registro (18 peças, 79%, círculos 5 mm) |
> | marcas de registro | `menu-registro.webp` | detalhe do bloco Registro |
> | marcas de registo e facas | `registro-saida.webp` | bloco Registro (arquivos exportados) |
> | nesting letras | `corte-192.webp` | bloco Modo Corte (192 corpos, 98% da chapa) |
> | nest margem | `corte-furos.webp` | detalhe do Modo Corte (peça dentro de furo) |
> | nest mod corte | `corte-48.webp` | galeria |
> | nest mod corte pode mover | `corte-ajuste.webp` | galeria |
> | plugin corel drawn | `plugin-corel.webp` | galeria (macros no CorelDRAW) |
>
> **Seções novas:** bloco **Marcas de registro** (5º recurso) e uma **galeria
> "Mais telas"** depois do Centro de Exportação. Componente `Detail` e classes
> `.pn-detail` / `.pn-gallery` foram criados para isso.
>
> **Copy corrigida pelas capturas:** o menu real de faca é *automático, retângulo
> (corte reto), contorno justo, contorno suave, contorno simplificado e faca do
> cliente* — o site dizia "círculo e oval", que **não existem** nesse menu.
> Todos os números foram trocados pelos das capturas novas (198/88%, 870/7/98%,
> 192 corpos/98% da chapa, 18/79%). As capturas antigas geradas pelo harness
> (`nesting.webp`, `escala.webp`, `modo-corte.webp`) foram apagadas.
>
> ⚠️ **Dois pontos para o Philipe decidir:**
> 1. A barra de título do app diz **"PrintNest Premium v1.0.0"** e o site vende
>    **"PrintNest Pro"**. Cortei a barra das capturas, então não aparece, mas o
>    nome precisa ser um só antes de lançar.
> 2. `registro-saida.webp` mostra **arte de clientes** (marca "emplavi" e
>    "#EU SOU QG"). É trabalho da gráfica, mas a marca é de terceiro: convém ter
>    o OK do cliente antes de usar em material de venda.

> **✍️ COPY 28/07 — landing reescrita para "informar até vender".** O design da
> repaginação Qexal ficou; o texto é que estava curto demais. Passada completa em
> `app/src/components/pn/Landing.tsx` + SEO no `app/index.html`:
> - **Hero:** manchete continua sendo o resultado real (`44 peças, 1 chapa, 83% de
>   área usada`, direto da captura). O subtítulo passou a explicar o que o software
>   é (desktop Windows) e já responde a objeção número 1: **ele não comanda a
>   máquina, entrega o arquivo**. Legenda do hero descreve a captura inteira.
> - **4 recursos:** parágrafos ampliados (mecanismo, não adjetivo) e tabelas de
>   especificações de 4 → 5/6 linhas. As especificações novas só citam o que aparece
>   nas capturas ou está na lista de verdades do produto.
> - **Como funciona:** os 3 passos ganharam corpo (quantidade, largura do material,
>   altura zero = rolo, escolha do registro, formatos de saída).
> - **Compatibilidade:** 5 → 6 itens por coluna; o parágrafo repete que o programa
>   não comanda o equipamento.
> - **FAQ: 7 → 14 perguntas** (faca do cliente, rolo, mudança de quantidade,
>   quanto de material o job gasta, registro, CorelDRAW, garantia…).
> - ⚠️ **Removida a frase "sem cobrança por máquina adicional dentro da mesma
>   gráfica"** que estava na seção de preço: não há decisão registrada sobre
>   número de ativações (o `COPY.md` fala em 1 ativação por licença). Não voltar
>   sem o Philipe definir a política de licenciamento.
> - Ainda **sem prova social** (nenhum depoimento, logo ou contagem de clientes).
>   Entra só com cliente real e consentimento por escrito.
> - Nada de tempo/economia prometidos ("economize X horas"): só mecanismo e o que
>   aparece na tela.

> **🎨 REPAGINAÇÃO 28/07 — referência Qexal (themesbrand).** O Philipe mandou
> `themesbrand.com/qexal-react/` como referência e escolheu o **layout 1**
> (hero azul cheio) mantendo **o azul da logo** (`#095df9`), não o do template.
> `pn.css` e `Landing.tsx` foram reescritos nesse idioma:
> - **Hero azul de ponta a ponta**, texto branco à esquerda e a tela do
>   PrintNest à direita dentro de uma **moldura de janela** (bolinhas +
>   título) que avança 152% da coluna e sai pela borda, igual ao demo 1.
>   Círculos suaves de fundo.
> - **Header fixo transparente** sobre o hero (logo em branco via
>   `filter: brightness(0) invert(1)`) que vira barra branca ao rolar,
>   trocando também a pele do botão "Comprar licença".
> - **Selinhos pílula** (`.pn-badge`) abrindo cada seção, títulos de seção
>   **centralizados**, cartões brancos com sombra suave e raio 14px, botões
>   totalmente arredondados, FAQ em cartões, rodapé azul-escuro.
> - A seção Modo Corte virou **faixa azul** (`.pn-band`) no lugar do preto, e o
>   CTA final é um bloco azul arredondado.
> - A "linha de faca" (contorno vermelho com marcas de registro em volta das
>   capturas) foi aposentada nesta versão; o vermelho sobrou só no selinho
>   "O software por dentro". O histórico dela está mais abaixo.
> - ⚠️ **Armadilha de especificidade (mordeu duas vezes):** `.pn a` e `.pn p`
>   são (0,1,1) e venciam classes como `.pn-btn-light` e `.pn-hero-lead`,
>   deixando texto branco sobre branco e parágrafo cinza sobre azul. Os botões
>   ganharam prefixo `.pn ` e o parágrafo virou `:where(.pn p)` (especificidade
>   zero). Se aparecer texto com cor errada, é isso.
> - Conferido em 2560px, 1440px e 390px (sem estouro horizontal).

> **✏️ AJUSTE 28/07 (pedido do Philipe).** Duas mudanças no redesign de 27/07:
> - **Tipografia trocada por Inter** em todos os papéis (títulos, texto e
>   dados). Bricolage Grotesque, Archivo e IBM Plex Mono saíram: o Philipe
>   achou as letras estranhas e pediu fonte padrão de site. As etiquetas que
>   eram monoespaçadas viraram Inter 600 caixa-alta com tracking curto, e os
>   números usam `font-variant-numeric: tabular-nums`.
> - **Hero refeito**: o software roda dentro de um **monitor de PC desenhado em
>   CSS** (`.pn-monitor`: moldura, queixo com a marca, pescoço, base e sombra na
>   mesa), com brilho azul de fundo. Layout **horizontal**: texto à esquerda,
>   monitor à direita (pedido do Philipe), os dois dentro do container.
>   Abaixo de 1000px empilha. As etiquetas flutuantes ("83%", "PDF + DXF") foram
>   removidas: a manchete já traz os mesmos números.
> - ⚠️ **Não voltar a "sangrar" o monitor para fora do container.** Uma versão
>   intermediária deixava ele avançar até a borda da tela; num monitor ultrawide
>   (2560px) ele virava um bloco gigante ao lado de um texto minúsculo e o Philipe
>   apontou a diagramação quebrada. Agora o monitor tem `max-width: 760px` e vive
>   na coluna. O container subiu de 1200 para **1280px** e o hero usa
>   `0.82fr / 1.18fr`. Conferido em 2560px, 1440px e 390px.
> - As capturas foram **refeitas com a janela em 16:9** (`win.resize(1760, 990)`
>   nos scripts) para encher a tela do monitor sem corte. A tela do mockup usa
>   `aspect-ratio: 1.7`, que é a proporção real do grab.

> **🎯 REDESIGN 27/07 — landing nova, guiada por capturas reais do app.**
> A landing foi refeita do zero em `app/src/components/pn/Landing.tsx` +
> `app/src/styles/pn.css`. `App.tsx` renderiza essa versão; a `editorial/`
> (hero scrollytelling e hero vídeo) continua no repo, apenas não é mais
> renderizada, e `index.css` importa `pn.css` no lugar de `editorial.css`.
>
> **Conceito:** a página usa a linguagem do próprio software. Fundo = o cinza
> da mesa de trabalho do app (`#eceff4`), blocos = chapas brancas, azul
> `#095df9` = marca/ação (igual à UI) e vermelho `#e5322a` = corte (igual à
> faca). O elemento assinatura é a **linha de faca**: cada captura de tela é
> envolvida por um contorno vermelho de 1px com offset e marcas de registro
> nos cantos, que se desenha no scroll (quatro traços percorrendo o perímetro).
> Tipografia: **Bricolage Grotesque** (títulos), **Archivo** (texto) e
> **IBM Plex Mono** (medidas, etiquetas e legendas de captura).
>
> **Seções:** hero (manchete = o resultado real "44 peças, 1 chapa, 83%") ·
> antes/depois · 4 recursos, cada um com afirmação + especificações + captura
> em largura total (faca, nesting, Modo Corte numa faixa escura, Centro de
> Exportação) · 3 passos · compatibilidade (entra/sai/máquinas) · preço ·
> FAQ · CTA · rodapé.
>
> **Capturas reais (novas, 27/07):** `app/public/assets/app/` — geradas com um
> harness que sobe a `MainWindow` de verdade (config.json temporário, sem tocar
> no app), abre um projeto de amostra com PNGs de adesivo, gera a faca por
> contorno e captura em 2x:
> `nesting.webp` (44 peças / 1 chapa / 83%), `faca.webp` (zoom do contorno),
> `escala.webp` (176 peças / 6 chapas / 78%), `modo-corte.webp` (22 letras
> encaixadas, 97% da chapa), `exportacao.webp` (Centro de Exportação).
> `nesting.jpg` fica só como `og:image`. Total ~800 KB em WebP.
> As capturas antigas (v3.0.0) seguem em `public/assets/prints/`.
>
> **Pendências herdadas:** `[LINK_PAGAMENTO]` e `[SUPORTE]` continuam como
> placeholder no topo do `Landing.tsx`; páginas legais ainda apontam para `#`.
>
> **Não usado hoje:** `public/assets/hero-loop*.mp4` e
> `src/assets/hero-variants/` (frames do scrollytelling). Ficam no repo caso o
> Philipe queira o vídeo de volta; nada disso entra no bundle atual.

> **🎬 HERO SCROLLYTELLING (09/07, tarde):** o hero agora é uma **sequência de 51
> frames controlada pelo scroll** (caos → nesting → interface final), estilo Apple
> keynote, sobre o design "Appline/UIdeck" que o GPT gerou (azul já trocado pelo azul
> da logo `#095DF9`).
> - Código: `app/src/components/editorial/HeroSequence.tsx` + `HeroText.tsx` e hooks
>   `app/src/hooks/useImageSequence.ts` (glob automático, nada hardcoded) +
>   `useCanvasRenderer.ts` (canvas contain-fit, DPR, fundo amostrado do frame).
> - Seção de 450vh com canvas sticky; preload com loader circular (scroll travado até
>   carregar); texto em **5 atos** com fade/blur/rise sincronizados ao progresso;
>   lerp para suavidade 60fps.
> - Frames em **duas camadas**: `app/src/assets/hero-frames-hd/` (1920×1080, desktop)
>   e `app/src/assets/hero-frames/` (1152×648, mobile) — 60 frames cada, extraídos
>   **direto do MP4 original** (`Downloads/Continue_seamlessly_from_the_p-ezgif...mp4`,
>   720p/240 frames) com Lanczos + unsharp; o hook escolhe a camada por
>   `innerWidth × devicePixelRatio`. A pasta `site/frame_to_video_hero/` (ezgif 51
>   frames recomprimidos) virou só backup.
> - Nitidez máxima real exigiria upscale por IA (Real-ESRGAN — download foi bloqueado
>   por permissão; Philipe precisa autorizar) **ou** regerar o vídeo em 1080p/4K na
>   ferramenta de IA que o criou (melhor opção).
> - **Sistema de VARIANTES (09/07, tarde):** cada vídeo candidato vira uma pasta em
>   `app/src/assets/hero-variants/<nome>/{hd,sd}/` (detecção automática por glob).
>   Seletor flutuante no canto inferior direito compara as versões ao vivo
>   (`?hero=<nome>` na URL). Para processar um vídeo novo:
>   `cd site/app && python scripts/extract-hero-frames.py "<video.mp4>" v3-nome 3 && npm run build`.
>   Variantes atuais: `v1-caos-monitor` (720p original, **favorita do Philipe**) e
>   `v2-otimizacao` (1080p nativo, 80 frames, estúdio claro — **manter salva**, pedido
>   do Philipe). Vídeos-fonte ficam em **`site/videos-fonte/`** (backup obrigatório —
>   o MP4 da v1 foi perdido de Downloads; o da v2 já está copiado lá).
> - **v1 refeita do 4K (09/07, fim de tarde):** o Philipe exportou o mesmo vídeo em
>   **4096×2304** (`videos-fonte/Continue_seamlessly_from_the_p 4K.mp4`, veio dentro do
>   zip "Untitled session-all-assets"). v1 regenerada: 80 frames downscalados de 4K
>   (nitidez máxima, sem upscale) + **cauda de 13 frames em crossfade para o
>   `app-producao.jpg` real** — o scroll termina na UI verdadeira, sem textos borrados
>   de IA. Total: 93 frames (HD ~19 MB / SD ~7 MB). Real-ESRGAN não é mais necessário.
> - **Prints REAIS no site (09/07, fim do dia):** seções "Sobre" e "Demonstração"
>   agora usam capturas reais do app (`app/public/assets/prints/`): P1 tela dividida,
>   P2 nesting 479 peças/94%, P3 faca por contorno, P5 Centro de Exportação.
>   Falta o **P4** (chapa com barra Gerar Faca) — terceira miniatura usa
>   `app-producao.jpg` até chegar. Galeria do "o que falta" está praticamente resolvida.
> - **2º LAYOUT de hero — "vídeo ao lado" (09/07):** sem scrollytelling; o vídeo roda
>   em loop na metade direita (`public/assets/hero-loop.mp4`, H.264 720p 2,2 MB,
>   encodado com o ffmpeg do `imageio-ffmpeg` que já estava no Python) e se dissolve
>   em **degradê branco para a esquerda**, onde ficam headline/CTAs.
>   Componente `HeroVideoSplit.tsx`; alternância pelo seletor (agora em
>   `HeroSwitcher.tsx`, renderizado no Landing) ou `?layout=video` / `?layout=scroll`.
>   O vídeo NÃO pausa com prefers-reduced-motion (decisão: é o propósito do layout).
> - ⚠️ Este PC está com animações do Windows **desativadas** (prefers-reduced-motion);
>   o scrub por scroll continua funcionando nesse modo (só perde a inércia/blur).
> - Versões anteriores do Landing: `app/src/archive/` (dribbble-editorial e
>   appline-pre-scrollhero).

> **⚠️ REDESIGN nesta sessão (09/07):** a landing foi refeita no estilo editorial da
> referência do Dribbble (shot 27261147 — TwelveMei): fundo "papel" com slabs
> arredondados, tipografia serif **Instrument Serif** nos títulos, nav em pílula
> centralizada, cards glass (backdrop-blur), abas de recursos com sublinhado animado,
> reveal on scroll (fade+blur+translate) e hero com **blur/fade do texto ao rolar**.
> - Código novo: `app/src/components/editorial/` (Landing, Hero, FeatureTabs) +
>   `app/src/styles/editorial.css` (design system completo).
> - A landing anterior segue no git (App.tsx antigo) e os componentes
>   `components/site/*` continuam no repo, apenas não são mais renderizados.
> - **Hero preparado para o scroll-video:** os 51 frames do vídeo cinematográfico
>   estão em `app/public/assets/hero-frames/` (frame 001 já é o fundo do hero).
>   O Philipe vai enviar um esquema do que acontece junto com o scroll — próximo passo.
> - Validado: `npm run build` ok, desktop e mobile (390px) sem overflow, screenshots ok.

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
