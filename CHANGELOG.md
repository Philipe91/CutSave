# Changelog

Todas as mudanças relevantes do PrintNest Pro. Formato inspirado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/). O histórico detalhado por
sessão fica em [`docs/historico/`](docs/historico/).

## [v1.3.0] — branch `v1.3-redesign` (sessões 04–06/07)

### Comercialização
- **Fluxo de venda validado de ponta a ponta** (06/07): exe bloqueou num 2º PC
  real, ID enviado, chave emitida com `gen_license.py`, ativação ok e
  persistente após reiniciar. Emissão com interface: `tools/license_studio.py`.
- **Ativação AUTOMÁTICA (robô)**: cliente clica "Pedir minha chave por e-mail"
  no app, envia o código de compra (`PNC-XXXX-XXXX`, uso único) e o robô no PC
  do dono (`tools/license_robot.py`) valida, assina e responde com a chave —
  sem ninguém na frente do computador. Testado com e-mail real no mesmo dia.
  Guia: `docs/produto/ROBO-ATIVACAO.md`.
- **Desativar no exe fecha o app na hora** (a sessão aberta continuava usável
  após desativar — brecha fechada).

### Faca
- **Curvas de VERDADE (Bézier)**: contornos curvos saem como curva contínua no
  canvas, Bézier nativo na Faca PDF e **SPLINE no DXF** — mesma contagem de
  nós, ≥4× mais fiel que as cordas retas. Cantos vivos e retas preservados
  exatos (retângulo continua retângulo).
- **Solda de contornos (estilo Contorno do Corel)**: facas de desenhos
  vizinhos que se INVADEM (sangria de um entra no outro) são unidas numa
  linha externa única — a lâmina não atravessa mais o adesivo do lado.
  Automático; quem não se toca continua com a própria faca.
- **Fusão automática de cortes rentes**: quadrados com espaçamento 0 viram
  grade de linhas contínuas (1 passada por linha, sem cortar 2× a mesma
  borda); com espaçamento, corte individual — sem botão, é automático.
- **Detecção sub-pixel**: em imagens pequenas a máscara é ampliada com
  interpolação — a faca deixa de seguir os degraus dos pixels (facetamento
  medido: 0,44 → 0,11 mm num círculo de 30 mm).

### Beta (feedback do chefe — 06/07)
- Cursor **mãozinha** ao pairar/mover peças (estilo Corel/Photoshop).
- Campo "Suavizar" não corta mais o número em monitores com escala 125/150%.
- Restaurar a janela com o canvas "perdido" (pan/zoom longe da chapa)
  **re-enquadra sozinho**.

### Jurídico (rascunhos para validação)
- `docs/produto/juridico/`: EULA, Política de Privacidade (LGPD) e Termos de
  Venda com a garantia de 7 dias.

- **Ferramenta Pontos (F10)**, estilo Corel: mover nó (arrastar), adicionar
  (duplo-clique no segmento), remover (duplo-clique no nó); escopo por arquivo
  (cópias herdam); faca manual sobrevive a rotação/redimensionamento e entra no
  undo. "Voltar ao automático" no card da peça.
- **Menos nós na faca** (melhor para a máquina de corte): pós-simplificação
  Douglas-Peucker + seletor **"Nós da faca" Fino/Médio/Leve** (Médio padrão).
  Com suavizado ativo usa tolerâncias menores para **não** desfazer a curva
  (256 → 32 nós mantendo a suavização).
- **Multi-desenho refinado**: marcas de registro enquadram a peça inteira
  (todas as facas); elementos pequenos reais entram (filtro por área absoluta
  em mm², não % da imagem) sem virar ruído.

## [v1.3.0] — branch `v1.3-redesign` (sessão 03/07)

### Comercialização — licenciamento
- **Ativação por chave (node-locked, offline, sem trial)** + garantia de 7 dias.
  Ed25519: o app tem só a chave pública; a privada fica com o dono
  (`tools/license_private_key.pem`, gitignored). Sem licença o exe não abre
  (dev não trava). Emissão: `gen_license.py` (CLI), `license_studio.py` (GUI),
  `issuer.py` (compartilhado). Menu Ajuda → Licença. Ver `docs/produto/LICENCIAMENTO.md`.

### Faca
- **Múltiplos desenhos por imagem**: uma folha com N adesivos gera N facas (a
  peça segue uma só; cortes internos). Preview e exportação (DXF/faca PDF) levam
  todas as linhas.

### UI / build
- Ícone do exe/janela com o **logo real**; versão **v1.3.0** no título/About;
  build carimba data no VERSAO.txt.
- Cards do inspector azuis e compactos; barrinha de exibição flutuante no canvas
  (não some mais); radio marcado redondo; lista de chapas do Centro de
  Exportação sempre interativa.

### Vendas
- Copy da landing page em `docs/produto/COPY-SITE-VENDAS.md` (R$ 397, garantia
  7 dias). Site em `site/` (feito por outra sessão).

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
