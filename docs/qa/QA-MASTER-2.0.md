# QA MASTER 2.0 — charter de auditoria (QA + UX + UI + Stress)

> Roteiro definido pelo Philipe em 08/07/2026 para auditorias da interface.
> Rodar antes de cada release: 4 agentes paralelos, um por dimensão, e
> consolidar em `docs/qa/RELATORIO-QA-<data>.md`.

## Papéis simultâneos
Senior UX Designer · UI Designer · Especialista em Design System · PySide6 ·
Responsividade Desktop · Windows DPI Scaling · Arquitetura de Interface.

## Regras obrigatórias
1. **Modo "não tenha pena"**: até 1px de desalinhamento é defeito; cada
   imperfeição reduz a percepção de qualidade (o produto compete com
   CorelDRAW, Illustrator, LightBurn, SigmaNEST...).
2. **Causa raiz obrigatória**: nenhum bug é "resolvido" sem identificar POR QUE
   aconteceu (layout? arquitetura? UX? responsividade? design system?
   dimensionamento? excesso de informação? falta de hierarquia?).
3. **Solução estrutural, nunca pontual**: se o padrão é sistêmico (todos os
   botões, todos os cards, todos os diálogos), propor refatoração GLOBAL.
4. Sempre perguntar: esse bug pode aparecer em outras telas? o componente
   existe em outros lugares? a solução evita a reincidência?

## Dimensões auditadas

### 1. Responsividade Desktop + DPI
- Alvos: notebook 1366×768/FullHD, monitor FullHD/2K/4K/ultrawide; Windows
  Scaling 100/125/150/175/200%.
- PROIBIDO em qualquer cenário: texto/botão cortado, label truncada,
  reticências desnecessárias, widget comprimido/sobreposto, scrollbar sem
  motivo, toolbar congestionada, informação escondida.
- Suspeitos de causa raiz: setFixedWidth/Height/Size, QSizePolicy errado,
  falta de stretch/spacer, layouts aninhados errados, posicionamento absoluto,
  falta de adaptação ao DPI.
- Preferir: redimensionar, mover, overflow inteligente, agrupar em menus/
  dropdowns, transformar secundários em menu "Mais...".

### 2. Design System
- Consistência de: border radius, padding, margens, espaçamentos, tipografia
  (tamanhos/pesos), altura de campos, tamanho de botões, ícones, cores,
  sombras, contraste.
- Estados: hover, focus, disabled, loading, selected — para TODOS os widgets.
- Fonte da verdade: `app/presentation/theme.py` — estilos inline hardcoded
  são suspeitos por definição.

### 3. UX comercial + carga cognitiva
- Persona: operador de gráfica SEM manual, sem vídeo, com minutos para
  aprender. Priorizar: menos cliques, menos leitura, menos configurações
  visíveis, mais velocidade, mais clareza, mais previsibilidade.
- Perguntas-guia: sabe onde clicar? entende o que aconteceu? excesso de
  informação? algo que só interessa a avançados? algo repetido? hierarquia
  visual correta? o botão principal PARECE principal? o fluxo é intuitivo?
  transmite confiança/modernidade?
- Poluição visual: pode virar menu? recolher? tooltip? aparecer só com
  arquivo carregado / com seleção?
- Contar: botões, informações, painéis, menus, cliques, opções simultâneas —
  e reduzir.

### 4. Microinterações + estados
- Feedback visual de toda ação; loading em operação longa; cursores
  (mãozinha etc.); transições; tooltips; confirmações na medida; estados
  vazio/erro/sucesso orientando o usuário.

## Formato do achado
`ID · severidade (🔴 crítico / 🟠 importante / 🟡 polimento) · tela/local ·
sintoma · arquivo:linha · CAUSA RAIZ · onde mais o padrão aparece · solução
estrutural proposta`.
