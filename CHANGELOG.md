# Changelog

Todas as mudanças relevantes do PrintNest Pro. Formato inspirado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/). O histórico detalhado por
sessão fica em [`docs/historico/`](docs/historico/).

## [1.1.3] — 2026-08-17 — **curvas do Modo Corte saem como curvas**

Relato de produção com letras de acrílico (logo do Hospital Santa Lucia, letras
de até 264 × 336 mm). Suíte: 831 testes, 0 falhas, 5 skips, mais
`tests/presentation` verde arquivo por arquivo.

**As curvas do desenho original chegavam ao corte trocadas por retas.** Em letra
grande as cordas retas ficam visíveis e o laser perde acabamento. Medido no
arquivo do cliente: entravam 720 nós com **365 curvas Bézier**; saíam 2.089
vértices e **zero curvas**.

- **Causa raiz:** a curva era destruída no *import*. Os importadores de PDF e de
  SVG achatavam a Bézier em polilinha e descartavam os pontos de controle — não
  havia como recuperá-los depois. O `Polygon` só sabia representar vértices.
- **O que o operador via, e por qual caminho.** "Exportar DXF" reconstruía uma
  curva por cima dos pontos achatados (aproximação, não o original). Já
  **"Enviar para o Corel" gravava `M ... L ... L ... Z`: polilinha pura, nenhuma
  curva**, apesar de o módulo prometer "curvas do corte". Foi por esse caminho
  que o defeito apareceu.
- **Correção:** a Bézier original do arquivo agora viaja ao lado do polígono
  achatado até a exportação. O motor de encaixe continua trabalhando só com o
  polígono e **não foi alterado**; giro e translação não deformam Bézier, então
  o mesmo transform do arranjo aplicado aos pontos de controle devolve a letra
  idêntica à do Corel. SVG e DXF gravam a curva de verdade, com a **mesma
  contagem de nós do desenho de origem** — 365 curvas entram, 365 saem.
- **Precisão de posicionamento:** a peça era posicionada pela caixa do polígono
  achatado. Como a curva pode estufar para fora das cordas, ela podia ficar até
  a tolerância de achatamento mais perto da vizinha do que o encaixe calculou.
  A referência passou a ser a caixa envolvente **exata** da Bézier.
- **Degradação segura:** contorno sem curva original (faca detectada em imagem,
  contorno simplificado ou suavizado, arco de SVG que não tem cúbica exata)
  mantém exatamente o comportamento anterior. Nunca se grava curva
  dessincronizada dos vértices.

Fora deste escopo, registrado em
[`docs/especificacoes/CURVAS-ORIGINAIS-MODO-CORTE.md`](docs/especificacoes/CURVAS-ORIGINAIS-MODO-CORTE.md):
texto digitado dentro do PrintNest continua achatando, e a faca de impressão
ainda faceta curvas com raio abaixo de ~1,5 mm.

## [1.0.2] — 2026-07-31 — **correção de impressão girada/espelhada**

Correção do commit `a1c8f9c`, empacotada. Suíte: 990 testes, 0 falhas, 5 skips.

**Impressão saía girada ou espelhada em relação à tela** — duas causas
independentes, as duas provadas com sonda de pixel antes da alteração. Relato
de produção de 31/07 com arquivo de cliente. Material impresso assim só revela
o erro depois de cortado: é chapa perdida.

- **Sentido do giro** (atinge qualquer arquivo com 90° ou 270°). O canvas gira
  com `QTransform().rotate(+ângulo)`, que é horário; a matriz de encaixe girava
  ao contrário. A peça caía no lugar e no tamanho certos — o retângulo de
  destino é o mesmo nos dois sentidos — mas a **arte saía 180° virada** em
  relação ao que o operador via. A faca não é afetada: não passa por essa
  matriz. O defeito é **anterior à migração PyMuPDF→pikepdf**; o teste de
  paridade copiava fielmente o sentido do `fitz`, que já discordava da tela.
- **Caixa de página invertida** (atinge só alguns arquivos). `MediaBox
  [0 297 210 0]` é PDF legal e todo visualizador normaliza sozinho. A matriz
  calculava a largura como `x1-x0`: invertida, isso dá negativo, a escala fica
  negativa e a arte entra **espelhada**. Mesma causa: a checagem
  `(x1-x0) > 2*crop` também dava negativo e o **recorte de borda era ignorado
  em silêncio** — a arte saía com a sangria que o operador mandou tirar.

Arquivos: `app/infrastructure/exporters/pdf_writer.py`,
`app/infrastructure/exporters/pikepdf_print_exporter.py`. Teste novo:
`tests/infrastructure/test_export_caixa_invertida.py`.

## [1.0.1] — 2026-07-31 — **acabamento**

Primeira versão entregue pelo canal de atualização.

- Ícones nítidos com escala do Windows em 125% ou 150% (padrão de fábrica em
  notebook). Antes eram esticados e saíam borrados; em 100% nada muda.
- Botão **Modo Corte** destacado na barra, em azul escuro com ícone de alvo.
  Antes se confundia com o "Gerar Faca", que usa o mesmo símbolo de tesoura.

## [1.0.0] — 2026-07-30 — **primeira versão comercial**

Release aprovada em 30/07/2026. Registro completo em
[`docs/qa/RELATORIO-FINAL-RELEASE-1.0-2026-07-30.md`](docs/qa/RELATORIO-FINAL-RELEASE-1.0-2026-07-30.md).
Suíte: 939 testes, 0 falhas, 0 erros, 5 skips. Validação manual: 8/8 aprovadas.
Build `SHA-256 2A49367B388BFF6AF056716718CC81548F6C884A1059C444DA00A0D5E76DA2DE`.

### Release candidate — 18 correções (commits `2162ef5` e `1717043`)

**Estabilidade e integridade de dados**
- **pdfium sob lock em dois pontos que faltavam** (`_crop_pages_dialog` e
  `_pdf_page_count`): abrir "Páginas do PDF…" durante uma geração colocava duas
  threads dentro da biblioteca ao mesmo tempo. Era a causa **provável** do crash
  `0xc0000374` que aparecia sem repro na máquina do cliente.
- **Geração cancelável**: fechar a janela no meio de uma geração longa não
  congela mais até 10 s nem aborta o processo. Medido em 0,06 s fechando na
  página 120 de 400, dentro da rasterização.
- **Salvar `.printnest` virou atômico** (`.tmp` + `fsync` + `os.replace`): uma
  interrupção no meio do `Ctrl+S` destruía o arquivo novo **e** o anterior.
- **`config.json` corrompido não impede mais o app de abrir**: o arquivo
  quebrado é preservado como `.corrompido` e o programa sobe com os padrões.
  Antes, com `console=False`, o app "abria e fechava" para sempre.
- **`sys.excepthook` global**: exceção não tratada num slot do Qt vira
  `CRITICAL` no log + aviso em pt-BR apontando a pasta de logs. Antes sumia
  sem rastro e a ação simplesmente "não acontecia".

**Perda de trabalho**
- **`_dirty` passou a ser por aba**: editar a aba A, trocar para a B, salvar a B
  e fechar o app matava o trabalho da aba A **sem perguntar nada**.
- **Modo Corte confirma antes de descartar o arranjo**: um `Esc` acidental
  jogava fora minutos de nesting e retoques manuais, sem volta.
- **Exportação bloqueada durante a geração**: os 9 caminhos de saída ficavam
  habilitados e exportavam o resultado **anterior**, em silêncio — numa gráfica,
  material caro impresso errado.

**Licenciamento**
- **MAC removido do fingerprint no Windows**: dock, adaptador USB ou driver novo
  mudavam o `machine_id` e a licença do cliente "quebrava" sem ele trocar de PC.
  O `MachineGuid` sozinho já é único e estável. *Mudança irreversível, aplicada
  antes da primeira venda.*
- **Ativação só declara sucesso se gravou de fato**: falha na escrita devolve
  mensagem citando antivírus/permissões, em vez de "ativada" seguido de nova
  tela de ativação na próxima abertura.

**Canal de atualização**
- **Endereço do manifesto embutido no executável**: sem ele, nenhum cliente da
  1.0.0 saberia de uma 1.0.1 — e a própria 1.0.1 é entregue por esse canal.
- Mensagem de desenvolvedor ("Defina 'update_url' na configuração") substituída
  por texto de produto.

**Interface**
- **Tooltip legível nos temas escuros**: o QSS pintava texto branco sobre fundo
  branco (contraste 1,0:1) — os 104 tooltips viravam balões vazios no dark mode.
- **Texto do botão de destaque derivado por contraste**: 7 presets reprovavam
  WCAG AA com o branco fixo (Verde 2,28:1, Turquesa 2,49, Graphite 2,52).
  Presets claros passam a ter texto escuro no CTA.
- **Modo Corte cabe em notebook 1366×768 @125%**: mínimo de 600 para 540 e
  parâmetros dentro de `QScrollArea`. É o diálogo que a macro do CorelDRAW abre
  sozinha, sem janela principal por trás — os botões do rodapé ficavam fora da
  tela e o operador sem saída.
- **Ativação de 585 px para 509 px** pelo mesmo motivo, e a numeração dos passos
  corrigida de 1‑2‑3‑**3** para 1‑2‑3‑4.

**Instalador e pacote**
- **EULA final**: os 5 placeholders de rascunho (`[RAZAO SOCIAL]`, `[NUMERO]`,
  `[CIDADE/UF]`…) apareciam na primeira tela que todo comprador vê. Documento
  acentuado, vendedor identificado, foro definido.
- **Nome único "PrintNest Pro"** no título, no Sobre, no instalador e no
  `VERSAO.txt` — o cliente comprava "Pro" e instalava "Premium". As chaves de
  `QSettings` **não** foram renomeadas, para não resetar tema e tour de quem já
  usa.
- **`AppMutex`**: instalar por cima com o app aberto dava erro de arquivo em
  uso. Agora o instalador detecta e pede para fechar (validado em log).
- **Pacote do cliente**: as 7 imagens do guia do Corel passaram a ser copiadas
  (o guia chegava com 7 referências quebradas); LEIA-ME sem "obrigado por
  testar" e apontando para o Tutor IA que de fato existe; `.bat` do plugin
  alinhado com o guia; README com as 7 opções reais de registro.

## [Não lançado] — branch `v1.3-redesign` (sessões 09/07–24/07)

### Modo Corte (módulo novo — fluxo só-corte)
- **Pipeline true-shape completo**: importadores vetoriais SVG e PDF, texto
  digitado → curvas (fontTools), nesting true-shape com giro garantido, ângulo
  fino e **preencher furos** (peça dentro de peça, Fase 6/D3), custo do GA por
  chapa consumida, DXF cortando **de dentro para fora**.
- **Manipulação no preview (E3)**: arrastar peça com o mouse, girar com a
  tecla R/botão, Ctrl+Z por folha, limite vermelho da chapa com clamp, zoom.
- **Chapas lado a lado** no preview (estilo eCut) + UI ilustrada com a faixa
  de passos Adicionar → Organizar → Exportar.
- **Plugin CorelDRAW ida-e-volta (D2)** com tutorial ilustrado (7 imagens);
  a ponte tenta a macro nos projetos PrintNest.gms e GlobalMacros.

### Marcas de registro (A2/A3 + E4)
- **3 formas novas**: Quadrados (Summa/OPOS), Cruzes e L de canto
  (Graphtec/Roland) — além de bolinhas, L e bolinhas+L.
- **Ajustes do cliente**: distância, tamanho e **espessura do traço**
  (0,3–2,0 mm), persistidos no projeto. Saída idêntica no preview, PDF de
  impressão e DXF (provado por teste em coordenadas reais).
- **Combo sem nome de máquina** (E4): rótulos por forma + ilustrações;
  ícones Lucide no Modo Corte, miniaturas nas listas.

### Faca
- **Faca do cliente** (16/07): reaproveita a faca desenhada no próprio
  arquivo — traço **magenta 100% sem preenchimento** (guia em
  docs/produto/FACA-DO-CLIENTE.md). Cartelas idênticas pausado por flag.
- **DXF com Y refletido** (y' = H − y): Corel/CAD não abre mais espelhado.
- **DXF: um contorno = UMA entidade (F3, 24/07)**: contorno curvo sai como
  **um único SPLINE fechado** (Bézier → B-spline exata, cantos preservados) —
  a letra seleciona inteira no Corel em vez de abrir em pedaços; furo segue
  objeto próprio e a ordem de corte (de dentro para fora) não muda.

### Licença / motor PDF
- **Migração PyMuPDF (AGPL) → pypdfium2 + pikepdf** (13/07): app 100% em
  licenças livres; fitz virou dev-only e não entra em `app/`.

### UI/UX
- Theme Engine + persistência; pacote de ilustrações de orientação;
  miniaturas ilustrativas nos combos; trilho de ícones no inspector;
  tela dividida horizontal (B4); multi-seleção e multi-drop na biblioteca
  (B1); tour de boas-vindas + **Tutor IA**.

### QA e correções
- **Missão QA MASTER PREMIUM (22/07)**: relatório completo em
  docs/qa/RELATORIO-QA-2026-07-22.md — 20+ achados, notas 0–10, roteiro
  manual de 22 itens, **85 testes novos em tests/qa/**. Veredito da data:
  não aprovado para produção (lista mínima de 6 itens).
- **Lote F1 (24/07, commit `1963870`)** — 5 da lista mínima corrigidos:
  girar não re-seleciona todas as cópias (fim da duplicação exponencial ao
  girar+duplicar); PDF ruim de cliente não estoura mais exceção crua nos
  caminhos síncronos; `.printnest` com lixo binário avisa amigável;
  **Substituir arquivo** reimporta de verdade (antes cortava a arte antiga
  com o nome novo); falha no recorte de página avisa em vez de sair o
  original em silêncio.
- **F2 (24/07)** — o arranjo manual **persiste no `.printnest`** (achado
  A0, o último da lista mínima): duplicatas, peças movidas e giro por peça
  sobrevivem a salvar+reabrir; campo aditivo com assinatura de invalidação,
  projeto antigo abre igual. Com isso a lista mínima do QA fechou 6/6.
- 5 correções do QA EXTREMO (13/07) + 9 fixes de varredura.
- **Pendente conhecido (pós-lançamento)**: merge de facas O(n²) em chapas
  de 1000+ peças (A10); marcas de registro saem RGB(0,0,0) em vez de K
  puro no PDF (A4 — validar leitura no plotter real).

### Site de vendas
- Landing React: hero scrollytelling 4K, prints reais do app, seção do
  Modo Corte (retomada por `site/ESTADO-SITE.md`).

### Decisões de escopo registradas
- **Motor de nesting congelado** (22/07): só reabre por bug real.
- **E1 cancelada** (peças de corte no canvas de impressão): revertida em
  `90959f4`; o caminho é manipular dentro do próprio Modo Corte (E3).
- **E2 (true-shape na impressão) pausado** por decisão do dono.

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
- **Cantos arredondados da faca** (raio em mm, estilo Corel): vale até para
  faca retangular; convexos e côncavos; global na barra Faca, com sobreposição
  por arquivo no card "Faca deste arquivo". Versão do app: **3.0.0**.
- **Ajustar chapa ao conteúdo** (Ctrl+Shift+F, card Produção e menu
  Organizar): a chapa encolhe para o tamanho exato do arranjo — exportação
  sem branco em volta (marcas de registro entram na folga própria). Desfazível.
- **Barra Faca** no topo (no lugar de Alinhar/Distribuir/Agrupar, que seguem
  na ribbon/menu/atalhos): Tipo de faca, Offset + direção, cantos, Raio,
  Suavizar, Nós e Por peça/Grade — sincronizada com o painel Documento.
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
