# Changelog

Todas as mudanças relevantes do PrintNest Pro. Formato inspirado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/). O histórico detalhado por
sessão fica em [`docs/historico/`](docs/historico/).

## [Não lançado] — branch `v1.3-redesign` (sessão 02/07)

### Refinamento visual (PrintNest Design System) — sem mudar a estrutura
- Tokens + QSS global (paleta clara, foco azul 2px, checkbox 18px, abas com
  sublinhado, menus/scrollbars modernos); mesa do canvas clara com a chapa
  "flutuando" (sombra **vetorial** — a antiga `QGraphicsDropShadowEffect`
  travava o zoom de perto e foi removida).
- Ribbon com seletor QSS correto (estava morto), setas de spinbox/combo
  restauradas (estilizar os botões descartava as nativas — ficavam invisíveis),
  cards do inspector com cabeçalho colorido por seção, respiro 12/16px,
  réguas/overlay/guias nos tokens do tema (um azul só).
- **Tipo de faca** movido para a barra, ao lado do botão azul "Gerar Faca"
  (decidir → gerar num gesto). Mesmo combo de sempre (estado/sessão intactos).

### Atalhos padrão CorelDRAW
- **Ctrl+C / Ctrl+V** copiar/colar peças (colagens cascateiam) e **Ctrl+D em
  cadeia** (a cópia vira a seleção). **Ctrl+W** fecha a aba; **Ctrl+P** exporta
  o PDF de impressão. Alinhar por letras **T/B/L/R/C/E**; zoom **F2/F3**,
  **Shift+F2** (seleção), **Shift+F4** (página); **H** mão; **Alt+setas** pan;
  **Alt+Enter** propriedades do objeto.

### Correções da auditoria QA (ver `docs/qa/RELATORIO-QA-2026-07-02.md`)
- 🔴 **QA-01** Desfazer giro de peça agora reverte de verdade (giros entram no
  snapshot de undo; o giro desfeito não "volta sozinho" no próximo recálculo).
- 🔴 **QA-02** Falha de exportação nunca mais é silenciosa: exportador captura
  as exceções novas do PyMuPDF ≥ 1.26 e os 5 `export_*` mostram diálogo.
- 🔴 **QA-03** Exportar Faca sem faca gerada é recusado com aviso (antes
  gravava PDF em branco que ia pra máquina de corte).
- 🟠 **QA-04** Importar o mesmo arquivo 2× soma a quantidade na linha existente
  (linhas duplicadas colidiam e a produção saía com quantidade errada).
- 🔴 **QA-05** Combo "Tipo de faca" não corta mais o texto.
- 🟠 **QA-06** Canvas 100% nos tokens do tema (faca/marcas/peça vazia/seleção/
  aviso de arquivo ausente — fim do drift de cores).
- 🟡 **QA-07** Duplicar/undo em cadeia ~20% mais rápido (memoização de
  footprint/params por id no redesenho); correção definitiva no backlog.
- 🟡 **QA-08** `closeEvent` espera a thread de geração (fim do risco de
  "fechou sozinho" ao fechar durante o processamento).
- 🟡 **QA-09** Menu Opções virou Alt+P (Alt+O era ambíguo com Organizar).
- 🟢 **QA-12** Clipboard de peças é por trabalho (limpo ao trocar de aba).

## [Não lançado] — branch `v1.2-projeto`

### V2.0 — UX/UI orientada ao operador (estilo CorelDRAW)
Só camada de edição/apresentação — motor, nesting, DXF e PDF **intactos**.

#### Adicionado
- **Barra de propriedades contextual** (Projeto / Objeto / Grupo), abaixo da ribbon.
- **Ferramenta Contorno** (faca): Offset + Direção (externo/interno) + Cantos
  (redondo/ponta/chanfro), só-ícone com tooltip. Cantos no motor via `join_style`.
- **Faixa Faca** (Modo/Recorte/Giro/Suavizar), global, sincronizada com o Documento.
- **Alças de mouse** para redimensionar a peça (com prévia; respeitam o cadeado).
- **Cadeado** de proporção no contexto Objeto.
- Checkbox **"Manter centralizado na chapa"** (sincronizado com o menu Organizar).

#### Alterado
- **"Gerar Faca"** virou o botão azul principal; "Gerar Produção" foi ao menu Ferramentas.
- Documentação reorganizada para `docs/` (por tema) com índice.

#### Removido (enxugar duplicações)
- Card "Medidas da peça" e campos L/A da barra (a medida já aparece no Objeto).
- Controle de "Densidade" (substituído pela ferramenta Contorno).

#### Corrigido
- Excluir a **última** peça (e remover da biblioteca) agora tira a arte da tela.
- **Girar** mantém a seleção (re-seleciona por `artwork_id` após o re-encaixe).

### Sessões anteriores (resumo)
- **29/06:** rotação por peça, marcas de registro na faca (bolinhas pretas),
  duplicar página, centralizar na página, quantidade nativa, correção da sangria.
- **25/06:** redimensionar arquivos, Ctrl+Z ilimitado, nesting MaxRects, Centro de
  Exportação, integração CorelDRAW (macro + instância única).
- **22–24/06:** faca compartilhada e marcas, base de nesting e exportação.

> Detalhes completos em `docs/historico/ESTADO-*.md`.
