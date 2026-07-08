# Relatório QA MASTER 2.0 — 08/07/2026

> 4 auditores paralelos (charter: `QA-MASTER-2.0.md`), modo "não tenha pena",
> causa raiz obrigatória. **53 achados**: Design System 14 · Responsividade/DPI
> 13 · UX/Carga Cognitiva 15 · Microinterações/Estados 11.
> Veredito honesto do auditor de UX: *"interface em desenvolvimento com forte
> camada visual premium por cima — arquitetura de informação em obra"*.

## As 4 causas raiz transversais (resolvem ~80% dos achados)

1. **Dimensões absolutas em px para conteúdo que depende da fonte**
   (setFixedWidth/Height/Size) — a família do bug do Suavizar 52px, replicada
   em ≥7 lugares (2003, 2054, 2062, 2147, 2160, 1074, 4198). Cura: helpers
   `_field()/_combo()/_bar_button()` derivando mínimos de `fontMetrics()`.
2. **Mesmo parâmetro em 3–4 superfícies espelhadas por código**
   (offset em 4 lugares; suavizar em 3; tipo/raio/nós/grade em 2–3; L/A em 2;
   ajustar-chapa em 3 botões). Cura: **fonte única visível = barra Faca**;
   cards só com override por arquivo; espelhos eliminados.
3. **Faltam 3 abstrações de feedback**: flag `_dirty` + `_confirm_discard()`
   (trabalho se perde sem aviso!), wrapper `_run_blocking()` (exportações
   travam a UI sem cursor de espera) e política toast-vs-modal única.
4. **Tokens faltantes no theme + estilos inline** (13 setStyleSheet locais,
   hex/px hardcoded, `theme.apply(app)` inexistente → License Studio nasce sem
   design system).

## 🔴 CRÍTICOS (corrigir antes de vender)

| # | Achado | Local | Causa raiz |
|---|---|---|---|
| C1 | Barra Faca NÃO CABE em 1366px (mín ~1500px lógicos); em 150% faltam ~590px — corta "Ajustar chapa", "Grade", "Nós" | main_window 2114-2252, 2012 | 18 widgets fixos numa linha, sem overflow/stretch |
| C2 | propBar `setFixedHeight(40)` corta botões (precisam 38px + margens) — pior em 125/150% | main_window 2003 | altura fixa < conteúdo dependente de fonte |
| C3 | ~~"Gerar Produção" sem botão~~ **DESCARTADO pelo produto (08/07)**: "Gerar Faca" É a ação principal — a hierarquia atual (azul na barra Faca) está correta | — | decisão de produto |
| C4 | Sangria/offset em **4 lugares** (_offset, _auto_offset, _pf_offset, _ct_offset) — operador pode cortar errado | 4047, 4120, 3486, 2146 | sem fonte única |
| C5 | **Trabalho descartado sem aviso**: novo/abrir/fechar app/fechar aba não perguntam "salvar alterações?" | 1905, 1937, 5143, 2881 | não existe flag _dirty |
| C6 | Exportações e Gerar Faca **travam a UI** sem cursor de espera/progresso (zero WaitCursor no código) | 6549-6825, 4530 | síncronas na thread da UI |
| C7 | **Estado vazio morto** — abre o app e nada orienta ("arraste aqui") | 2948 | sem overlay de onboarding |
| C8 | License Studio sem design system (parece outro app) + diálogos de licença SEM ACENTO (tela do cliente pagante!) | license_studio 100-104; licensing_dialog várias | falta theme.apply(app); strings ASCII |
| C9 | Combos truncam com reticências (sem AdjustToContents) sob compressão | 2136, 2221, 2233 + todos | sem política de conteúdo |

## 🟠 IMPORTANTES

- Modo Compacto `setMaximumHeight(24)` corta campos que precisam de 36px (4198)
- `LengthSpin.setFixedWidth(90)` não cabe "20000.00 mm" (2054, 2147)
- Painéis com `setMaximumWidth` fixo cortam rótulos em 150–200% (3192, 3963)
- Splitter `setSizes([300,780,320])`=1400 > 1366; mínimos estouram em escala (2915)
- Grupo ribbon "Produção" só tem exportações — renomear "Exportar"; ordem dos grupos ≠ fluxo (1756)
- Barra Faca sempre visível com ~11 controles ANTES de existir arquivo (2114) → aparecer só com produção/arquivo
- Tipo de faca com fonte de verdade num widget-fantasma (_faca_mode órfão) espelhado à mão (4066-4078, 2314)
- "Ajustar chapa" em 3 botões + atalho → manter 1 (barra) + atalho
- Aba "Objeto" ≠ página "Objeto" da barra (dois significados) → renomear
- L/A editável em 2 lugares (2051 vs 3455)
- Remover arquivo da biblioteca apaga produção SEM undo (4816 não passa pelo commit)
- ProgressBar sempre montada, parada em 0 na fase mais demorada (2919, 5158)
- QMessageBox vs toast inconsistente p/ mesma classe de erro (5101 vs 4532)
- Toasts .info() azul para o que é warning (3385, 3420, 6288, 6498, 6334, 2488)
- Overlay translúcido com alfas divergentes 235≠232 (610, 650) → token SURFACE_OVERLAY
- `#FFFFFF` literal em vez de ICON_ON_ACCENT (2129; theme 123, 213, 383)
- border-radius/padding mágicos fora dos tokens (2006, 1155, 2721)
- Botões-ícone com 3 tamanhos (30×28, 28×28, 34×38) → fábrica única
- Título de card inline repetido → criar role "cardTitle" (1102, 3903, 613)

## 🟡 POLIMENTO (seleção)

- Espaçamentos fora da grade 4/8 (7, 3, 5, 1 px soltos) → SPACE_2XS + varredura
- Alturas mágicas (84 vs 96 em áreas de chave; QuantityStepper 26)
- font-size 26px/16px inline fora da escala FONT_*
- role "accentTag"/"dot" p/ tags e separadores inline repetidos
- Ícone 15px fora do padrão 18 (642)
- "Desativar" sem property danger (licensing_dialog 98)
- Jargão: "Offset"/"sangria"/"Caixa de Apara" sem tradução p/ operador
- Card Produção mistura chapa + sangria de faca (4054) → só chapa
- ~19 decisões visíveis antes do 1º arquivo → revelação progressiva
- Raio global vs por-arquivo sem sinalizar precedência (badge "personalizado")
- Biblioteca sem hierarquia (Remover compete com Adicionar)
- Toasts sem fade e sem reposicionar no resize (toast.py 55-79)
- Exportar habilitado durante regeneração (busy não centralizado, 5139 vs 5195)
- closeEvent espera 10s sem feedback (5149)
- Diálogo exportação mín 720×480 aperta notebook em 175%+ (1087)

## O que já está certo (reconhecido pelos auditores)

Tema/tokens bem estruturados; ícones Lucide consistentes (18px); tooltips com
boa cobertura; cursores dos elementos interativos ok (alças, nós, guias,
mãozinha); confirmação de desativar licença é o modelo certo a propagar;
undo robusto no arranjo.

## Plano de correção proposto (fases)

**FASE 1 — estrutural 🔴 (destrava as demais):**
1. Barra Faca responsiva: overflow "⋯" quando faltar espaço + altura por
   fontMetrics + aparecer só com arquivo carregado (C1, C2, e metade dos 🟠)
2. Hierarquia: botão azul "Gerar Produção"; "Gerar Faca" secundário; grupo
   "Exportar"; ordem do ribbon = fluxo (C3)
3. Fonte única de faca: barra = global visível; cards Produção/Acabamento/
   Imagens perdem os duplicados; card Peça = só override (C4)
4. `_dirty` + `_confirm_discard()` nos 4 pontos de perda (C5)
5. `_run_blocking()` com WaitCursor + progresso nas exportações (C6)
6. Estado vazio com orientação no canvas + biblioteca (C7)
7. Acentuação + theme.apply(app) no licenciamento (C8)
8. Helper `_combo()`/`_field()` com AdjustToContents/fontMetrics (C9)

**FASE 2 — consistência 🟠:** tokens novos (SURFACE_OVERLAY, cardTitle,
accentTag, ICON_BTN, SPACE_2XS), varredura de inlines/hex/px, undo na
remoção da biblioteca, política única de feedback, progressbar show/hide.

**FASE 3 — polimento 🟡:** fades, jargão, badges de override, disabled
centralizado, ajustes de diálogos.

*Regra do charter: nenhum item se encerra sem causa raiz eliminada — as
correções acima são estruturais (helpers/tokens/política), não tapa-buracos.*
