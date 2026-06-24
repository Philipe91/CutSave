# Roadmap Oficial de Desenvolvimento — Projeto PrintNest

> MVP → Produção · Software Windows de preparação de produção gráfica
> Documento complementar a [ARQUITETURA.md](ARQUITETURA.md)

---

## Visão Geral

Construir um software profissional para Windows focado em:

- Importação de PDF, PNG e JPG
- Geração automática de faca (CutContour)
- Offset interno e externo
- Nesting inteligente e otimização de material
- Exportação PDF (impressão) e DXF (corte)

**O objetivo NÃO é controlar máquinas.** O objetivo é entregar **arquivos prontos para produção**. O operador segue usando os softwares de máquina já existentes.

---

## Filosofia de Desenvolvimento

Ordem de prioridade — **núcleo antes da interface, sempre**:

```
1. Motor de processamento
2. Geometria
3. Nesting
4. Exportação
5. Interface
```

> A interface nunca deve ser desenvolvida antes do núcleo. Cada fase entrega valor testável de forma isolada (testes-ouro de geometria/nesting), sem depender da GUI.

---

## Mapa de Marcos (Milestones)

As 23 fases se agrupam em quatro marcos. Cada marco é um ponto de validação real.

| Marco | Fases | Resultado |
|---|---|---|
| **M1 — Fundação** | 1–2 | Projeto roda; logs, config e modelo de domínio prontos |
| **M2 — Núcleo de Processamento** | 3–13 | Importação, faca, offset, materiais e nesting v1 funcionando (sem GUI rica) |
| **M3 — Produção Visual** | 14–18 | Visualizador, jobs em background, exportação PDF/DXF, testes de carga |
| **M4 — Maturidade e Release** | 19–23 | Nesting v2, cache, performance, beta interno, Release 1.0 |

---

# Fases Detalhadas

## FASE 1 — Estruturação do Projeto
**Objetivo:** criar a fundação técnica.
**Entregas:** estrutura de diretórios (conforme arquitetura); ambiente virtual Python 3.12+; PySide6; SQLite; logging estruturado; sistema de configurações.
**Resultado esperado:** aplicação inicial abre corretamente, logs funcionando, configurações persistidas.
**Camadas:** `shared/`, `__main__.py` (Composition Root).

## FASE 2 — Modelo de Domínio
**Objetivo:** criar as entidades principais.
**Entidades:** `Project`, `Artwork`, `Material`, `CutContour`, `PlacedItem`, `Layout`, `ExportJob`.
**Resultado esperado:** toda a estrutura de dados definida, em Python puro, com unidade canônica em **milímetros**.
**Camadas:** `domain/model`, `domain/units`.

## FASE 3 — Importação PDF
**Objetivo:** importar PDFs corretamente (PyMuPDF).
**Recursos:** leitura de largura, altura e resolução (pt→mm); extração de vetores e miniaturas.
**Resultado esperado:** PDFs carregados com dimensão real correta.
**Camadas:** `infrastructure/importers/pdf`, `application/services/ImportService`.

## FASE 4 — Importação PNG
**Objetivo:** suporte a PNG transparente (OpenCV/Pillow).
**Recursos:** leitura de canal alpha, DPI e dimensões (px+DPI→mm).
**Resultado esperado:** PNG carregado corretamente, alpha detectado.

## FASE 5 — Importação JPG
**Objetivo:** suporte completo a JPG.
**Recursos:** leitura de DPI, largura e altura.
**Resultado esperado:** JPG carregado corretamente.

## FASE 6 — Sistema de Miniaturas
**Objetivo:** visualização rápida.
**Recursos:** Thumbnail Cache, Preview Cache, Disk Cache (chaveado por hash de conteúdo).
**Resultado esperado:** visualização instantânea, sem re-render.
**Camadas:** `infrastructure/cache`, `infrastructure/raster`.

## FASE 7 — Geração de Faca PDF
**Objetivo:** criar faca baseada em vetor.
**Recursos:** identificação do contorno externo; união de vetores (Shapely); *fallback* para bounding box quando ambíguo.
**Resultado esperado:** faca vetorial automática.
**Camadas:** `domain/cut/generators/vector_pdf_gen`.

## FASE 8 — Geração de Faca PNG
**Objetivo:** criar faca baseada em transparência.
**Recursos:** canal alpha → threshold/morfologia → `findContours` → vetorização → simplificação (Douglas-Peucker, tolerância configurável).
**Resultado esperado:** contorno automático limpo (sem serrilhado).
**Camadas:** `domain/cut/generators/alpha_png_gen`.

## FASE 9 — Geração de Faca JPG
**Objetivo:** primeira versão.
**Recursos:** faca retangular (bounding box).
**Resultado esperado:** todos os JPGs recebem faca.
**Camadas:** `domain/cut/generators/rect_jpg_gen`.

## FASE 10 — Motor de Offset
**Objetivo:** criar sangrias com precisão industrial.
**Recursos:** offset externo +1/+3/+5/+10 mm; offset interno −1/−3/−5/−10 mm (Shapely `buffer`); tratamento de furos e múltiplos contornos; garantia de contorno fechado.
**Resultado esperado:** precisão industrial validada por testes-ouro.
**Camadas:** `domain/cut/offset_engine`.

## FASE 11 — Sistema de Quantidades
**Objetivo:** duplicação automática.
**Recursos:** quantidade individual por item; duplicação em lote.
**Resultado esperado:** milhares de cópias suportadas via modelo *flyweight* (1 `Artwork` ↔ N `PlacedItem`).

## FASE 12 — Biblioteca de Materiais
**Objetivo:** cadastrar materiais reutilizáveis (Adesivo, Lona, PVC, ACM, PS, UV…).
**Campos:** nome, largura, margem, espaçamento, offset padrão.
**Resultado esperado:** perfis reutilizáveis persistidos.
**Camadas:** `infrastructure/persistence` (Repository), `domain/model/Material`.

## FASE 13 — Nesting V1
**Objetivo:** primeira versão funcional.
**Algoritmos:** Grid Packing (peças idênticas) + MaxRects (variadas).
**Recursos:** rotação 0° / 90° / 180° / 270° com restrições por peça/material.
**Resultado esperado:** nesting automático funcionando, atrás de `INestingStrategy` (troca de algoritmo sem alterar o resto).
**Camadas:** `domain/nesting/strategies`.

## FASE 14 — Visualizador de Layout
**Objetivo:** visualizar o resultado.
**Recursos:** zoom, pan, grade, réguas, medidas (QGraphicsView com proxies).
**Resultado esperado:** layout visual completo.
**Camadas:** `presentation/canvas`.

## FASE 15 — Sistema de Jobs
**Objetivo:** processamento em background.
**Recursos:** fila, cancelamento cooperativo, progresso (Qt Signals), logs por *correlation id*.
**Resultado esperado:** a interface nunca trava.
**Camadas:** `application/jobs/JobManager`, `infrastructure/parallel`.

## FASE 16 — Exportação PDF
**Objetivo:** arquivo final para impressão.
**Recursos:** PDF vetorial, PDF de produção, escala real (mm); raster por tiles/streaming para arquivos grandes.
**Resultado esperado:** arquivo pronto para impressão.
**Camadas:** `infrastructure/exporters/pdf_print`.

## FASE 17 — Exportação DXF
**Objetivo:** arquivo de corte (ezdxf).
**Recursos:** geometrias limpas, contornos fechados (`LWPOLYLINE`), escala em milímetros (`$INSUNITS`), layers configuráveis (`CUT`/`CREASE`/`MARK`), versão DXF estável.
**Resultado esperado:** DXF pronto para uso, no mesmo referencial do PDF.
**Camadas:** `infrastructure/exporters/dxf`.

## FASE 18 — Testes Reais de Produção
**Objetivo:** validar operação em escala.
**Testes:** 100, 500, 1.000 e 5.000 arquivos.
**Avaliar:** tempo, RAM, precisão geométrica, aproveitamento de material.
**Resultado esperado:** metas de carga estabelecidas e medidas (baseline para a Fase 21).

## FASE 19 — Nesting V2
**Objetivo:** melhorar aproveitamento.
**Recursos:** Skyline; Simulated Annealing; otimização por *time budget* configurável.
**Resultado esperado:** ganho de material (faixa típica 5–15%, a confirmar com jobs reais da Fase 18).
**Camadas:** `domain/nesting/optimizers`.

## FASE 20 — Sistema de Cache
**Objetivo:** evitar reprocessamentos.
**Cache:** miniaturas, vetores, facas, layouts (hash de conteúdo + parâmetros; LRU; idempotente).
**Resultado esperado:** aumento de velocidade ao reabrir/reprocessar.
**Camadas:** `infrastructure/cache`.

## FASE 21 — Otimização de Performance
**Objetivo:** preparar para produção pesada.
**Recursos:** ProcessPool (CPU-bound, fora do GIL), multithreading (I/O leve), cache avançado, renderização otimizada.
**Resultado esperado:** processamento industrial contínuo, validado contra a baseline da Fase 18.

## FASE 22 — Beta Interno
**Objetivo:** utilização diária real.
**Duração:** 30 dias.
**Avaliar:** erros, travamentos, usabilidade.
**Resultado esperado:** lista de correções priorizada antes do release.

## FASE 23 — Release 1.0
**Objetivo:** entrar em produção.
**Entrega:** instalador Windows (PyInstaller), 64-bit, offline.

---

## Funcionalidades da Versão 1.0

✓ PDF · ✓ PNG · ✓ JPG
✓ Faca automática · ✓ Offset · ✓ Quantidades
✓ Biblioteca de materiais · ✓ Nesting automático · ✓ Rotação
✓ Visualizador · ✓ PDF de impressão · ✓ DXF de corte
✓ Cache · ✓ Multithread · ✓ Processamento em lote

---

## Meta Final

- Substituir completamente o fluxo de nesting do Print Factory.
- Eliminar custos recorrentes de licença.
- Possuir tecnologia própria.
- Criar uma base sólida para futuras evoluções.

---

## Fora do Escopo da Versão 1.0

NÃO desenvolver na 1.0 (fica para versões futuras, após estabilizar o núcleo):

- Integração IECHO / iBrightCut
- Comunicação com máquinas
- Controle de ferramentas / pressão / velocidade
- Leitura de câmera / marcas de registro automáticas
- IA para remoção de fundo (JPG inteligente)
- ERP
- Sistema Web

---

## Notas de Sequenciamento (visão do arquiteto)

Observações sobre dependências entre fases, para planejamento — não alteram o escopo que você definiu:

- **Fase 6 (miniaturas) usa o cache da Fase 20.** Na prática, um cache mínimo de thumbnails nasce na Fase 6; a Fase 20 o generaliza (vetores, facas, layouts). Vale tratar a Fase 6 como "cache de miniaturas" e a Fase 20 como "cache unificado".
- **Fase 13 (nesting v1) se beneficia do Sistema de Jobs (Fase 15).** Rodar nesting de milhares de peças sem background trava a UI. Sugestão: um `JobManager` mínimo já na Fase 13, expandido na Fase 15.
- **Fases 16 e 17 compartilham o referencial de coordenadas.** Devem ser desenvolvidas em conjunto (mesmo *Layout* de origem) para que faca (DXF) e arte (PDF) coincidam no destino.
- **A baseline de performance é a Fase 18.** As metas medidas ali definem o critério de aceite das Fases 19, 20 e 21 — sem ela, "otimização" não tem alvo objetivo.

Essas são recomendações de ordem de execução. Se preferir manter a numeração exatamente como está, basta antecipar os "mínimos" (cache de thumbnail, job manager) dentro das fases que dependem deles.
