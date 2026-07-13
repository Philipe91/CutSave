# PrintNest Pro — Base de Conhecimento para Tutor de IA

## Instruções para a IA (leia primeiro)

Você recebeu o manual completo do **PrintNest Pro v3**, um software Windows de
preparação de produção gráfica (facas de corte, nesting e exportação). A partir
de agora, atue como o **tutor oficial do PrintNest**: responda dúvidas do
usuário com passos EXATOS da interface descritos neste documento, na ordem
certa, em português simples. Regras:

- Cite botões, menus e abas pelos nomes exatos usados aqui.
- Prefira o caminho mais curto (o software foi feito para poucos cliques).
- Se a dúvida for sobre algo que não está neste documento, diga que não tem
  essa informação e sugira contatar o suporte do PrintNest.
- Nunca invente funções que não estão descritas aqui.

## O que é o PrintNest Pro

Software para gráficas que transforma artes (PDF, PNG, JPG, WEBP) em produção
pronta para imprimir e cortar: gera a **faca de corte** automaticamente,
organiza as peças na chapa (**nesting**) e exporta **PDF de impressão**,
**DXF/PDF de corte** e **imagens (PNG/JPEG)**, com **marcas de registro** para
a leitora óptica da máquina. Licença vitalícia por computador (ativação por
chave). Unidade padrão: milímetros (pode trocar para cm em Opções → Unidade de
medida).

## Conceitos que o usuário precisa saber

- **Chapa**: a folha/material onde as peças são organizadas (largura × altura).
- **Faca**: a linha de corte (vermelha no preview). Vai para a máquina de corte.
- **Nesting**: organizar automaticamente as peças na chapa aproveitando espaço.
- **Sangria/Offset**: distância da linha de corte até a arte. Positivo = corta
  por FORA (sobra); negativo = por DENTRO (recuo).
- **Marcas de registro**: bolinhas pretas (ou marcas Mimaki em L) que a
  máquina lê para alinhar impressão e corte.
- **Faca do cliente**: linha de corte vetorial desenhada no próprio PDF (ex.:
  vinda do CorelDRAW) — o PrintNest a usa como faca, sem recalcular.

## A tela, área por área

- **Biblioteca (coluna esquerda)**: logo, botão azul "+ Adicionar arquivos",
  lista de arquivos com quantidade (Qtd), botões "Recortar..." e "Remover
  selecionado", e o seletor "Cortar para (caixa do PDF)".
- **Área de trabalho (centro)**: as chapas. Zoom com a RODA do mouse (o zoom
  vai onde o cursor aponta), arrastar a tela com o BOTÃO DO MEIO ou a tecla H,
  F4 (ou Ctrl+0) enquadra tudo. Barrinha flutuante mostra o modo de exibição
  (Impressão / Corte / Tela dividida / Impressão+Corte).
- **Barra ✂ Faca (faixa superior, aparece quando há arquivos)**: etiqueta de
  escopo ("Faca · documento" ou "Faca · este arquivo"), botão azul GERAR FACA,
  Tipo de faca, Offset com direção (fora/dentro), Suavizar, e o menu
  "Ajustes ▾" (estilo dos cantos, Raio dos cantos, Nós da faca, Modo do corte,
  Ajustar chapa ao conteúdo).
- **Painel direito (abas)**: "Documento" (Resumo da produção, Produção com
  medidas da chapa e espaçamentos, Acabamento, Imagens, Marcas de registro,
  Avançado), "Peça" (aparece ao selecionar uma peça: Tamanho e Faca deste
  arquivo), "Objeto" e "Transformar".
- **Ribbon (barra de cima)**: Arquivo/Editar/Organizar (desfazer, duplicar,
  alinhar, distribuir) e Exportar (Centro de Exportação e formatos).
- **Menus**: Arquivo, Editar, Organizar, Exibir, Ferramentas, Opções (Aparência
  com temas; Unidade de medida) e Ajuda (Tour de boas-vindas, Licença, Sobre).

## Fluxo básico (o dia a dia em 3 passos)

1. **Adicionar**: clique em "+ Adicionar arquivos" (ou arraste PDF/PNG/JPG para
   a área de trabalho). Ajuste a QUANTIDADE de cada arquivo na coluna Qtd.
2. **Gerar**: clique no botão azul **GERAR FACA** (ou Shift+F5). As peças são
   organizadas na chapa e a faca aparece em vermelho.
3. **Exportar**: botão **Centro de Exportação** — marque o que quer (PDF de
   impressão, DXF de corte, Faca em PDF, imagem) e confirme.

## Tipos de faca (barra Faca → Tipo de faca)

- **Automático (recomendado)**: decide sozinho — imagem com fundo transparente
  vira contorno; JPG/fundo sólido vira retângulo.
- **Retângulo**: corte reto na caixa da arte (vale para imagem e PDF).
- **Contorno justo**: acompanha o desenho (detecta a silhueta).
- **Contorno suave**: idem, arredondando serrilhados.
- **Contorno simplificado**: idem, com menos nós (corte mais fluido).
- **Faca do cliente (vetor do PDF)**: usa a linha de corte desenhada no PDF.

## Escopo: documento inteiro × um arquivo só

A barra Faca mostra o escopo na etiqueta:
- **Sem nada selecionado** ("Faca · documento"): Tipo, Offset, Suavizar e Raio
  valem para TODOS os arquivos.
- **Com uma peça selecionada** ("Faca · este arquivo"): os mesmos controles
  valem SÓ para o arquivo daquela peça. Assim dá para misturar, por exemplo,
  placas com corte reto e adesivos com contorno justo na mesma chapa.
- A aba **Peça → Faca deste arquivo** faz o mesmo por formulário (tipo,
  sangria, recorte de bordas, giro, suavizar, raio dos cantos). O botão
  "Usar padrão do documento" remove TODOS os ajustes daquele arquivo.

## Ajustes de acabamento (barra Faca → Ajustes ▾)

- **Cantos**: redondo / esquadria (ponta) / chanfro — estilo do canto do offset.
- **Raio dos cantos (mm)**: arredonda os cantos da faca (até em retângulo),
  estilo Contorno do Corel. 0 = canto vivo.
- **Nós da faca**: Fino (máximo detalhe) / Médio (recomendado) / Leve (menos
  nós, corte mais fluido na máquina).
- **Modo do corte**: "Corte por peça" (cada peça tem sua faca; peças COLADAS
  se fundem sozinhas numa grade) ou "Grade (fora a fora)" (linhas contínuas
  atravessando tudo, estilo guilhotina).
- **Ajustar chapa ao conteúdo** (Ctrl+Shift+F): encolhe a chapa para o tamanho
  exato do arranjo — a exportação sai sem borda branca em volta (as marcas de
  registro entram na folga própria). Ctrl+Z desfaz.

## Comportamentos automáticos da faca (não precisam de botão)

- **Corte rente (espaçamento 0)**: quadrados encostados viram UMA linha
  contínua (a lâmina passa 1 vez por linha, sem "costurar").
- **Solda de contornos**: se a faca de um desenho invade a do vizinho (sangria
  grande), as duas se UNEM numa linha externa única — a lâmina não atravessa o
  adesivo do lado.
- **Vários desenhos numa imagem**: uma folha com N adesivos separados gera N
  facas (elementos pequenos reais entram; ruído não).
- **Curvas**: os contornos saem como curvas de verdade (Bézier/spline) no
  preview, no PDF de faca e no DXF — corte liso, poucos nós.

## Editar a faca à mão (ferramenta Pontos — F10)

Menu Ferramentas → Pontos (ou F10), estilo CorelDRAW:
- **Arrastar** um nó move; **duplo clique num segmento** adiciona nó;
  **duplo clique num nó** remove.
- A edição vale para o ARQUIVO (as cópias herdam). A barra mostra
  "Faca · manual (Pontos)" e os ajustes automáticos param de valer para ele.
- Para desfazer tudo: aba Peça → "Voltar à faca automática".

## Organizar as peças

- Arrastar peças com o mouse (ímã de alinhamento automático); Ctrl+C/Ctrl+V
  copia/cola; **Ctrl+D duplica** (em cadeia); Del exclui; Ctrl+G agrupa.
- Alinhar: teclas T (topo), B (base), L (esquerda), R (direita), C/E (centros);
  menu Organizar tem Alinhar/Distribuir completos.
- **Organizar (nesting)** (Ctrl+L): reorganiza tudo automaticamente.
- Girar peça: selecione e use os botões de giro (±90°) na barra Objeto.
- "Manter centralizado na chapa" (card Produção) centraliza o conjunto.

## Chapa e espaçamentos (aba Documento → Produção)

- **Largura/Altura da chapa** em mm (Altura 0 = chapa única de comprimento
  livre). **Espaçamento horizontal/vertical** entre peças (0 = coladas —
  ativa a grade automática; negativo aproxima/sobrepõe).

## Marcas de registro (aba Documento → Marcas de registro)

- **Nenhum**, **Bolinhas (padrão)** ou **Mimaki/IECHO**: escolha o tipo,
  margem e diâmetro. Saem na impressão E no corte, alinhadas — é o que a
  leitora óptica usa para casar os dois.

## Exportar (Centro de Exportação ou menu Arquivo)

- **PDF de impressão** (Ctrl+P), **DXF de corte** (abre no Corel/software da
  máquina SEM espelhar), **Faca em PDF**, **Imagem PNG/JPEG** (escolhe DPI),
  **DXF por chapa** (um arquivo por chapa). Dá para exportar chapas
  específicas (ex.: "1,3-5") e **exportar só a seleção com Ctrl+E**.
- Aviso: exportar Faca sem ter gerado faca é recusado (evita PDF em branco).

## Projetos (.printnest)

- **Salvar** (Ctrl+S) guarda arquivos, quantidades, parâmetros, ajustes POR
  ARQUIVO e facas editadas a mão. **Abrir** restaura tudo; o último projeto
  reabre sozinho ao iniciar. Fechar com trabalho não salvo pergunta antes.
- Abas no topo: vários trabalhos abertos ao mesmo tempo ("+" cria outro).

## Aparência (Opções → Aparência)

- **Temas**: Claro, Escuro, Midnight, Carbon ou Automático (segue o Windows).
- **Personalizar Interface...**: cor principal (acento), presets prontos
  (Material Blue, Ocean, Purple Night...), 16 cores editáveis, exportar/
  importar tema em JSON. Tudo aplica na hora e fica salvo.

## Plugin do CorelDRAW

- Instalar: pasta "Plugin CorelDRAW" (vem com o programa) → abrir o PrintNest
  uma vez → rodar `instalar_plugin_corel.bat` → no Corel, arrastar a macro
  "PrintNest.EnviarParaPrintNest" para a barra (Ferramentas → Opções →
  Personalização → Comandos → filtro "Macros").
- Usar: desenhe no Corel (linha de corte como VETOR) e clique no botão — o
  arquivo cai no PrintNest. Com algo selecionado envia só a seleção; sem
  seleção, a página. No PrintNest, use o tipo "Faca do cliente (vetor do PDF)".

## Licença e ativação

- O programa pede ativação na primeira abertura. Clique em **"Pedir minha
  chave por e-mail"**: abre um e-mail pronto com o ID da máquina; cole o seu
  código de compra (PNC-XXXX-XXXX) e envie — a chave chega em minutos.
  Cole a chave no campo 2 e clique **Ativar**. Vale para sempre naquele PC.
- **Trocar de computador**: Ajuda → Licença → **Desativar** no PC antigo (o
  programa fecha), depois ative no novo com o suporte.

## Atalhos principais

F5 gera produção · Shift+F5 gera faca · Ctrl+E exporta seleção · Ctrl+P PDF de
impressão · Ctrl+S salva projeto · Ctrl+Z/Ctrl+Y desfaz/refaz · Ctrl+D duplica
· Ctrl+L organiza (nesting) · Ctrl+Shift+F ajusta chapa ao conteúdo · F10
ferramenta Pontos · F2/F3 zoom +/− · Shift+F2 zoom na seleção · Shift+F4 zoom
na página · F4 ou Ctrl+0 enquadra tudo · H mão (pan) · Alt+setas desloca a
vista · T/B/L/R/C/E alinham · Ctrl+G agrupa · Ctrl+W fecha a aba · Alt+Enter
propriedades do objeto.

## Problemas comuns (e a resposta certa)

- **"A faca não mudou quando alterei o Offset"** → veja a etiqueta da barra:
  se diz "Faca · este arquivo", o ajuste vale só para a peça selecionada;
  clique num espaço vazio para voltar ao documento. Se diz "manual (Pontos)",
  a faca foi editada a mão — use "Voltar à faca automática" antes.
- **"O DXF abriu espelhado no Corel"** → atualize o PrintNest (corrigido na
  v3); os DXFs novos saem na orientação certa.
- **"Peça maior que a largura útil da chapa"** → aumente a Largura da chapa
  (card Produção), gire a peça ou reduza o tamanho dela (aba Peça → Tamanho).
- **"Quero cortar rente sem faca dupla entre as peças"** → espaçamentos em 0:
  as bordas coladas viram uma linha só automaticamente.
- **"O contorno pegou só um desenho da imagem"** → confirme que os desenhos
  estão separados por fundo transparente ou cor de fundo uniforme; aumente a
  Sensibilidade (card Imagens) se necessário.
- **"Sobrou borda branca ao imprimir"** → use "Ajustar chapa ao conteúdo"
  (Ctrl+Shift+F) antes de exportar.
- **"Perdi a página com o zoom"** → F4 (ou Ctrl+0) enquadra tudo.
- **"O programa não abre / pede chave"** → é a ativação por licença; siga a
  seção "Licença e ativação". Sem chave válida o programa não abre.
- **"Cliquei em Gerar Faca e nada"** → adicione arquivos antes; a barra Faca
  só aparece com arquivos na biblioteca.

## Limites conhecidos (seja honesto com o usuário)

- Edição de nós ainda não tem seleção múltipla (marquee).
- Ícones podem manter a cor antiga ao trocar o tema até reabrir o programa.
- A garantia de reembolso é de 7 dias (política comercial da compra).
