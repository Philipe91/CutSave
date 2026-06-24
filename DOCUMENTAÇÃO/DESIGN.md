# PrintNest Premium — Guia de Design (Design System)

> Padrão visual e de interação do software. **Toda nova tela, painel ou componente deve seguir este guia.** O objetivo não é só "ficar bonito": é reduzir a carga cognitiva do operador de produção gráfica e parecer um software profissional de 2025 (referências: Affinity, LightBurn, Figma, CorelDRAW).

---

## 1. Princípios

1. **Clareza acima de tudo.** Mostre só o que importa naquele momento. Menos é mais.
2. **Contexto, não tudo de uma vez.** O painel de propriedades muda conforme a seleção (Documento → Peça → Grupo). Nunca empilhe todas as opções.
3. **Nunca falhe em silêncio.** Toda situação ambígua vira um **Alerta** claro; toda ação concluída vira um **Toast**. Quando possível, ofereça a correção (botão de ação no alerta).
4. **Ensine durante o uso.** Tooltips, legendas curtas e mensagens contextuais orientam o usuário.
5. **Consistência.** Mesmos espaçamentos, raios, cores e tipografia em toda parte — sempre via tokens (`theme.py`), nunca hex solto.
6. **Espaço em branco é design.** Respiro entre blocos; evite caixas enormes e excesso de bordas.

---

## 2. Tokens (origem única: `app/presentation/theme.py`)

**Nunca** escreva cores/medidas literais na UI. Importe de `theme`.

### Espaçamento (grade de 4/8 px)
`SPACE_XS=4` · `SPACE_SM=8` · `SPACE_MD=12` · `SPACE_LG=16` · `SPACE_XL=24`
Raio: `RADIUS=8` · `RADIUS_SM=6`

### Cores
| Papel | Token | Hex |
|---|---|---|
| Fundo da janela | `BG` | `#eef0f3` |
| Superfície (cards) | `SURFACE` | `#ffffff` |
| Superfície sutil | `SURFACE_ALT` | `#f6f7f9` |
| Borda | `BORDER` | `#e3e6ea` |
| Texto primário | `TEXT` | `#1f2733` |
| Texto secundário | `TEXT_SECONDARY` | `#5b6675` |
| Texto apagado | `TEXT_MUTED` | `#9097a3` |
| Acento (marca) | `ACCENT` / `ACCENT_HOVER` | `#2f6fed` / `#2257c4` |
| Info | `INFO` | `#2f6fed` |
| Sucesso | `SUCCESS` | `#1f9d57` |
| Aviso | `WARNING` | `#c77700` |
| Erro | `ERROR` | `#d33a2c` |

Canvas/produção: `CUT` (faca vermelha `#dc2626`), `MARK` (registro `#0a5ab4`), `SHEET` (chapa branca), `CANVAS_BG` (mesa cinza).

### Tipografia
Família `FONT_FAMILY` (Segoe UI / Inter). Tamanhos: `FONT_SM=11` (legendas), `FONT_MD=12` (corpo), `FONT_LG=14` (títulos). Peso 600 para títulos/valores.

A folha global vem de `theme.build_app_qss()` e é aplicada uma vez no `__main__`. O tema é **travado em Claro** (`setColorScheme(Light)`) para ficar idêntico em qualquer PC.

---

## 3. Estrutura da tela (5 regiões)

```
┌───────────────────────── Menu superior ─────────────────────────┐
├──────────────── Ribbon (1 linha, agrupada) ─────────────────────┤
│ [Faixa de Alerta — só quando há aviso]                          │
├───────────┬───────────────────────────────┬─────────────────────┤
│ Biblioteca│     Área de trabalho (canvas) │ Propriedades         │
│ (miniatura│        + réguas em mm         │ (contextual:         │
│  + medidas│                               │  Documento/Peça/Grupo)│
├───────────┴───────────────────────────────┴─────────────────────┤
│ Barra de status: peças · chapas · área% · zoom · cursor · modo  │
└──────────────────────────────────────────────────────────────────┘
```

- **Ribbon** (`panels/ribbon.py`): grupos **Arquivo · Editar · Organizar · Produção · Exibir**, separados por linha. Ação primária (Gerar) em destaque (`accent`). Menus suspensos para conjuntos (Exportar, Alinhar, Distribuir). Ícones Lucide. Ações secundárias ficam **só com ícone** (tooltip); ações primárias levam ícone+texto.
- **Biblioteca** (`_build_library_panel`): cada arquivo mostra miniatura, nome, medida (L×A), páginas e tipo. Nunca só o nome.
- **Propriedades** (`_build_properties_panel`, `QStackedWidget`): troca por `_on_selection_changed`. Documento = ajustes globais em `CollapsibleCard`s; Peça = medidas (largura, altura, **área**, **perímetro**, posição) + ações; Grupo = medidas totais + alinhar/distribuir.
- **Status bar** (`panels/status_bar.py`): métricas vivas (não modal).

---

## 4. Componentes reutilizáveis (`app/presentation/widgets/`)

Sempre prefira reutilizar; só crie um componente novo se nenhum servir — e então documente-o aqui.

| Componente | Quando usar |
|---|---|
| **`CollapsibleCard`** | Agrupar ajustes/medidas em seções recolhíveis. Substitui faixas coloridas. Cabeçalho discreto com seta. |
| **`Alert` / `AlertLevel`** | Aviso **persistente e contextual** (info/success/warning/error) numa faixa. Use ação quando houver correção (ex.: "Trocar"). |
| **`ToastManager`** | Confirmar uma ação concluída sem interromper: "Produção gerada", "PDF exportado", "Projeto salvo". Some sozinho. |
| **`MeasureField`** | Exibir uma métrica somente-leitura (rótulo pequeno + valor em destaque). |
| **`labeled(text, widget)`** | Padronizar um controle com legenda acima. |

**Mensagens (`messages.py`) e medidas (`measurements.py`) são lógica PURA** (sem Qt) e **testadas**. A UI só consome o resultado. Mantenha cálculo e regra fora dos widgets.

---

## 5. Ícones (Lucide, ISC)

- Arquivos em `assets/icons/*.svg` (traço `currentColor`). Licença em `assets/icons/LICENSE.txt`.
- Use sempre via `icons.icon("nome", cor, tamanho)` — nunca carregue SVG na mão.
- **Adicionar um ícone:** baixe o SVG do Lucide (`https://unpkg.com/lucide-static@1.21.0/icons/<nome>.svg`, seguindo redirect com `curl -L`) para `assets/icons/`, e referencie pelo nome.
- Tamanho padrão 18 px na ribbon, 14 px na status bar, 16 px em cabeçalhos.

---

## 6. Padrões de interação

- **Sucesso → Toast** (canto inferior direito). Não use diálogo modal para confirmar sucesso.
- **Aviso/risco → Alert** na faixa (com ação corretiva quando der). Ex.: faca compartilhada quadrando contorno de imagem → ação "Trocar".
- **Erro grave/bloqueante → diálogo** (`QMessageBox.critical`).
- **Seleção dirige o contexto.** Selecionou peça? Mostre a peça. Clicou no vazio? Volta ao Documento.
- **Tempo real.** Mudou um parâmetro → `_relayout()` atualiza preview, status e avisos imediatamente.

Catálogo mínimo de avisos a cobrir (ver `messages.py`): faca compartilhada × imagem, peça maior que a chapa, nenhuma peça selecionada, arquivo inexistente, exportação sem corte, medida inválida.

---

## 7. Regras para manter o padrão (checklist de PR)

Ao criar/alterar interface, confirme:

- [ ] Cores, espaçamentos e fontes vêm de `theme.py` (zero hex literal novo).
- [ ] Ícones via `icons.icon(...)` (Lucide), nunca emoji/PNG avulso.
- [ ] Agrupei ajustes em `CollapsibleCard`; não empilhei tudo de uma vez.
- [ ] Sucesso = Toast; aviso = Alert; erro grave = diálogo. Nada falha em silêncio.
- [ ] Cálculo/regra ficou em módulo **puro** (`measurements.py`/`messages.py`) com teste; o widget só exibe.
- [ ] Reusei componente existente em vez de duplicar.
- [ ] **Contrato de testes preservado**: não renomeei atributos/métodos que `tests/presentation/test_main_window.py` acessa (`_width, _offset, _table, _view, _scene, _result, generate, export_*`...). `_table` continua `QTableWidget` (col0 = nome/⚠, col1 = QuantityStepper).
- [ ] `python -m pytest` e `ruff check .` limpos.
- [ ] Validei abrindo o app (`python -m app.presentation`) ou via screenshot offscreen.

---

## 8. Anti-padrões (evite)

- Faixas/cabeçalhos coloridos berrantes (estilo antigo `_section`).
- Caixas gigantes com dezenas de campos sempre visíveis.
- Hex e medidas mágicas espalhados pela UI.
- Diálogo modal para confirmar coisas triviais.
- Lógica de cálculo dentro do widget.
- Botões duplicados (mesma ação em vários lugares) — uma ação, um lar (ribbon/menu).
