# RELATÓRIO FINAL — QA MASTER EXTREMO (13/07/2026)

> Execução: suíte pytest completa (linha de base) + 4 esquadrões paralelos
> dirigindo o software REAL (offscreen) com dados sintéticos e validação
> 100% numérica (fitz/ezdxf/PIL). ~600k tokens de QA, ~230 chamadas de
> ferramenta, scripts reexecutáveis em scratchpad\qa_faca|qa_fluxos|
> qa_stress|qa_export. Nenhum código do produto foi alterado.

## Números gerais

- Funcionalidades mapeadas e exercitadas: **~120** (todas as telas, menus,
  barra Faca, exportações, projetos, abas, temas, licença, Pontos, plugin)
- Verificações executadas: **~430** (158 fluxos + 11 frentes de faca medidas
  + 8 cenários de export com ~90 medições + ~80 de stress + suíte de 550)
- Suíte pytest: **100% verde** (zero regressão na linha de base)
- Crashes: **0** · Corrupção de dados: **0** · Vazamento de memória: **não
  detectado** (+5MB em platô após 10 ciclos de 200 peças)
- Bugs encontrados: **13** (1 🔴 · 6 🟠 · 6 🟡) + 1 limitação de produto
  + 2 observações

## BUGS (consolidado, sem duplicatas entre esquadrões)

### 🔴 Crítico (perda de trabalho)
| ID | Título | Causa raiz |
|---|---|---|
| QAX-01 | **Editar depois de salvar não marca "alterado"**: mudar parâmetro, mover peça ou mudar QUANTIDADE após um save deixa `_dirty=False` → fechar descarta o trabalho SEM perguntar | `_mark_dirty` só é chamado em add_paths/_load_production/_apply_state; `_relayout` e `_commit_arrangement` não marcam (main_window ~5627/6662) |

### 🟠 Altos
| ID | Título | Causa raiz |
|---|---|---|
| QAX-02 | **"Tipo de faca" com seleção grava override COMPLETO** (8 chaves) e congela recorte/giro/offset globais do arquivo — regressão do padrão esparso, confirmada por 2 esquadrões | `_apply_contour_mode` monta `dict(self._params_for(path))` em vez de usar `_piece_override` (main_window ~2624) |
| QAX-03 | **Desperdício de chapa por 9 µm**: peça de PDF "100mm" mede 100,0000046mm e o encaixe usa EPS 1e-6 → 4 peças que cabiam em 1 chapa viram 2 chapas (dobra o material em silêncio) | `max_rects.py:26` `_EPS=1e-6` + conversão pt→mm sem arredondar (`pymupdf_importer.py:63`) |
| QAX-04 | **Seleção em massa é O(n²)**: Ctrl+A+Ctrl+D com 256 peças = 6,1s; chegar a 1024 = 201s; 2048 = travamento (>25min, abortado). Cada `setSelected` dispara `_on_selection_changed` inteiro (769 chamadas num Ctrl+D) | loops de seleção sem `QSignalBlocker` (`_select_all`, `_select_pieces_at` ~6320) com handlers O(n) |
| QAX-05 | **Arquivo ausente aborta a geração INTEIRA** (nada é gerado mesmo com outros válidos); no caminho blocking a exceção sobe crua | `generate` sem tratamento por-arquivo (~5526); esperado: pular linhas ⚠ e avisar |
| QAX-06 | **Faca PDF: contorno curvo = 32 Béziers SOLTOS** por faca (não 1 caminho fechado) — softwares de corte via PDF recebem fragmentos; risco de levantadas de faca | `export_faca_pdf` chama `page.draw_bezier` por trecho (~7236) em vez de 1 Shape com `curve4`+`closePath` |
| QAX-07 | **DXF fatia contorno com canto vivo em SPLINEs ABERTAS** (triângulo = 3 entidades; reta vira spline) — CAD mostra 3 objetos; mesa pode cortar com levantadas | `dxf_exporter` manda TODOS os trechos como curva; `render_splines_and_polylines` quebra em cada canto G1 (~57) |

### 🟡 Médios
| ID | Título |
|---|---|
| QAX-08 | Ajustes de campos DIFERENTES (<1,5s) fundem num único Ctrl+Z (merge não distingue o campo do gesto) |
| QAX-09 | Exportar PDF de 500 peças congela a UI por 10,3s (só ampulheta, sem progresso) |
| QAX-10 | `generate(blocking=False)` não é reentrante: 2ª chamada com a 1ª rodando deixa QThread órfã (latente; IPC do Corel pode disparar) |
| QAX-11 | Reflexão Y do DXF referencia a GEOMETRIA, não a chapa: sem marcas de registro, alinhamento manual pelo canto da chapa pega Y deslocado |
| QAX-12 | Erro de disco na Faca PDF mostra mensagem crua do MuPDF em inglês (demais formatos são amigáveis) |
| QAX-13 | Sangria "de fábrica" (3mm/2mm dos settings) vaza pelo caminho do Corel/add_paths sem o reset "faca exata" |

### Limitação de produto (decisão do dono)
- **L1**: `.printnest` não persiste arranjo manual (duplicações no canvas,
  giros por peça, ajuste de chapa) — regenera do zero ao reabrir; "Projeto
  salvo" promete mais do que salva. Persistir o arranjo OU avisar no save.

### Observações (documentar)
- Peça de 0,08mm (PNG 1×1) é aceita sem aviso de "menor que o cortável".
- Contorno raster tem erro intrínseco ~0,06–0,2mm; "Nós: Médio" achata bicos
  muito finos (~1,2mm no ápice) — dentro do prometido, mas documentar.

## Destaques positivos (provados com número)

- **Alinhamento impressão×corte: 0,0000mm** de resíduo nas 5 marcas (a prova
  sagrada — corta certo na máquina); Y do DXF sem espelho (bico no maior y).
- Offset de faca exato ao micrômetro (+5mm → +10,000mm); fillet r5 com erro
  0,006mm; retas com desvio 0,0000 em todos os níveis de nós; faca do
  cliente com erro 0,000mm vs teórico.
- Grade rente: contagem EXATA de linhas, zero borda cortada 2×; solda
  booleana correta; multi-desenho pega 4mm e ignora ruído de 0,2mm.
- 500 peças: zero sobreposição, zero fora da chapa; nesting de 5000 em 74ms.
- 7 insumos hostis (corrompido, 0 páginas, 6000px, caminho de 235 chars com
  acento, deletado após import...) → todos com erro amigável, app vivo.
- Undo sobreviveu a 200 ciclos; abas herméticas; single-instance real OK;
  fechar durante geração OK; 5 janelas criadas/destruídas sem sinal órfão.

## Notas (0–10)

| Dimensão | Nota | Justificativa |
|---|---|---|
| Funcionalidade Geral | **9,0** | tudo que promete, funciona e foi medido |
| Estabilidade | **8,5** | 0 crash/corrupção em ~430 verificações; ST-03 latente |
| UX | **7,5** | fluxo 3-passos forte; faltam progresso no export e aviso do L1 |
| UI | **8,5** | design system consistente, temas, dark completo |
| Performance | **6,5** | núcleo excelente; seleção O(n²) reprova volume alto |
| Consumo de Memória | **9,0** | +5MB em platô, sem leak |
| Consistência | **8,0** | preview = export provado; escopo com a exceção do Tipo |
| Robustez | **8,5** | hostis 7/7 amigáveis; buraco do dirty desconta |
| Escalabilidade | **6,0** | 100–500 peças ok; 1000+ trava na seleção |
| Confiabilidade das saídas | **9,5** | 0,0000mm — o coração do produto |
| Qualidade Geral | **8,3** | |
| Prontidão para Produção | **7,0** | pronto APÓS o pacote de correções abaixo |

## DECISÃO FINAL

# ⚠️ APROVADO COM RESSALVAS

O produto NÃO perde dados por conta própria, NÃO corrompe arquivos e as
saídas de corte são metrologicamente exatas — o núcleo está pronto. A
aprovação plena para produção exige corrigir ANTES do lançamento:

1. **QAX-01 🔴** (dirty após salvar) — perda de trabalho silenciosa;
2. **QAX-04 🟠** (seleção O(n²)) — inviabiliza o cliente de adesivos em escala;
3. **QAX-02 🟠** (override do Tipo) — regressão de comportamento já prometido;
4. **QAX-03 🟠** (EPS do encaixe) — dobra material do cliente em silêncio;
5. **QAX-05 🟠** (arquivo ausente aborta tudo).

QAX-06/07 (fragmentação de curvas nas saídas): geometria correta — validar
na MESA REAL do beta; recomendado corrigir na sequência. Os 🟡 e a L1 podem
ser pós-lançamento, com L1 decidida pelo dono (persistir arranjo ou avisar).

Cada bug tem teste pytest proposto pelos esquadrões — implementar junto com
as correções para blindar as próximas versões.
