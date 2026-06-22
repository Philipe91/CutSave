# Arquitetura — Sistema de Nesting e Geração de Faca para Impressão Digital

> Documento de Arquitetura de Software (v2 — escopo definitivo)
> Projeto: **Cutph** — alternativa própria ao Print Factory, focada em **geração de faca, nesting e preparação de produção**.
> Plataforma: Windows 10/11 · 64 bits · Idioma: Português Brasileiro · 100% offline · 100% open source.

---

## Princípio Fundamental de Escopo

Este software é um **PREPARADOR DE PRODUÇÃO**, não um controlador de máquina.

```
Arquivos → Geração de Faca → Nesting → Exportação PDF → Exportação DXF
```

**O sistema NÃO possui** e a arquitetura NÃO deve abrir espaço para: integração IECHO/iBrightCut, comunicação com máquinas, controle de ferramentas/pressão/velocidade, drivers proprietários ou SDKs de fabricante. A fronteira de saída do sistema são **dois arquivos** (PDF de impressão + DXF de corte). O operador leva esses arquivos para os softwares de máquina já existentes.

Essa fronteira fechada é a decisão arquitetural mais importante: ela elimina a maior fonte de risco (comunicação com hardware) e torna o sistema **determinístico, testável e auditável** ponta a ponta.

---

## Sumário

1. [Arquitetura Geral (Clean Architecture)](#1-arquitetura-geral-clean-architecture)
2. [Diagrama Textual dos Módulos](#2-diagrama-textual-dos-módulos)
3. [Estrutura de Diretórios](#3-estrutura-de-diretórios)
4. [Responsabilidade de Cada Camada](#4-responsabilidade-de-cada-camada)
5. [Fluxo Completo de Dados](#5-fluxo-completo-de-dados)
6. [Tecnologias Recomendadas](#6-tecnologias-recomendadas)
7. [Estratégia de Nesting](#7-estratégia-de-nesting-recomendada)
8. [Estratégia de Geração de Faca](#8-estratégia-de-geração-de-faca)
9. [Estratégia de Exportação DXF](#9-estratégia-de-exportação-dxf)
10. [Sistema de Cache](#10-sistema-de-cache)
11. [Sistema de Paralelismo](#11-sistema-de-paralelismo)
12. [Persistência, Logs e Tratamento de Erros](#12-persistência-logs-e-tratamento-de-erros)
13. [Sistema de Plugins](#13-sistema-de-plugins)
14. [Plano de Escalabilidade](#14-plano-de-escalabilidade)
15. [Riscos Técnicos e Mitigações](#15-riscos-técnicos-e-mitigações)

---

## 1. Arquitetura Geral (Clean Architecture)

### 1.1 Estilo

**Clean Architecture estrita (regra de dependência para dentro) + Pipeline de Processamento + Plugins via Strategy/Registry.**

Quatro camadas concêntricas. O fluxo de controle entra pela borda (UI) e desce; as dependências de código apontam **sempre para o centro**. Nada do núcleo conhece PySide6, SQLite, PyMuPDF, OpenCV ou ezdxf — essas são detalhes de borda, plugáveis atrás de interfaces (ports).

```
        ┌─────────────────────────────────────────────┐
        │  FRAMEWORKS & DRIVERS (Infrastructure)        │
        │  PySide6 · SQLite · PyMuPDF · OpenCV · ezdxf  │
        │   ┌─────────────────────────────────────┐     │
        │   │  INTERFACE ADAPTERS (Application)     │     │
        │   │  Services · Commands · JobManager     │     │
        │   │   ┌─────────────────────────────┐     │     │
        │   │   │  USE CASES                    │     │     │
        │   │   │  Importar · GerarFaca ·       │     │     │
        │   │   │  Nesting · Exportar           │     │     │
        │   │   │   ┌─────────────────────┐     │     │     │
        │   │   │   │  ENTITIES (Domain)  │     │     │     │
        │   │   │   │  Project · Material │     │     │     │
        │   │   │   │  Artwork · CutPath  │     │     │     │
        │   │   │   │  Layout · Unidades  │     │     │     │
        │   │   │   └─────────────────────┘     │     │     │
        │   │   └─────────────────────────────┘     │     │
        │   └─────────────────────────────────────┘     │
        └─────────────────────────────────────────────┘
            Regra de dependência → SEMPRE para dentro
```

### 1.2 Princípios de qualidade aplicados

| Princípio | Aplicação concreta |
|---|---|
| **SRP** | Cada gerador de faca, cada estratégia de nesting e cada exporter é uma classe com uma responsabilidade. |
| **OCP** | Novos formatos/algoritmos entram como novas implementações de interface, sem alterar chamadores. |
| **LSP** | Toda `INestingStrategy` é substituível; o `NestingService` não conhece a concreta. |
| **ISP** | Ports pequenas e específicas (`IImporter`, `ICutGenerator`, `IExporter`, `IRepository`). |
| **DIP** | Núcleo define interfaces; infraestrutura as implementa e é injetada no startup (Composition Root). |

---

## 2. Diagrama Textual dos Módulos

```
PRESENTATION (PySide6 / MVVM)
   main_window · canvas_view (QGraphicsView) · painéis · drop zone · viewmodels · i18n pt-BR
        │  Commands / DTOs ▲ Qt Signals (progresso)
        ▼                  │
APPLICATION (Orquestração)
   services/    → ProjectService · ImportService · CutService · NestingService · ExportService
   commands/    → AddArt · SetCopies · SetMaterial · RunNesting · MoveItem (undo/redo)
   jobs/        → JobManager · fila · progresso · cancelamento
   ports/       → IImporter · ICutGenerator · INestingStrategy · IExporter · IRepository · IWorkerPool · ICache
   dto/         → objetos de fronteira UI↔App
        │  usa interfaces (ports)
        ▼
DOMAIN (Núcleo — Python puro + Shapely/NumPy)
   model/       → Project · Material · Artwork · CutPath · PlacedItem · Layout · Sheet
   units/       → conversão px/pt/mm + DPI (canônico interno = mm)
   cut/         → ICutGenerator · vector_pdf_gen · alpha_png_gen · rect_jpg_gen · offset_engine
   nesting/     → INestingStrategy · grid · maxrects · skyline · nfp(v2) · optimizers/(SA)
   geometry/    → wrappers Shapely/NumPy · validação · simplificação · limpeza
        ▲  implementado por
        │
INFRASTRUCTURE (Adapters / Detalhes)
   importers/   → pdf (PyMuPDF) · png/jpg (OpenCV+Pillow)
   exporters/   → pdf_print · dxf (ezdxf)
   raster/      → render final · proxies/thumbnails
   persistence/ → SQLite (repositórios + migrações)
   parallel/    → ProcessPool · particionamento
   cache/       → cache em disco (hash de conteúdo)
   plugins/     → registry + contracts (entry points)
   shared/      → config · logging · errors
```

---

## 3. Estrutura de Diretórios

```
Cutph/
├── docs/
│   └── ARQUITETURA.md
├── app/
│   ├── __main__.py                 # Composition Root (injeção de dependências)
│   │
│   ├── presentation/
│   │   ├── main_window.py
│   │   ├── canvas/                 # QGraphicsView, itens, réguas, zoom/pan
│   │   ├── panels/                 # arquivos, material, parâmetros, fila
│   │   ├── widgets/                # drop zone, sliders de offset, previews
│   │   ├── viewmodels/
│   │   └── i18n/                   # pt-BR (Qt Linguist .ts/.qm)
│   │
│   ├── application/
│   │   ├── services/
│   │   ├── commands/
│   │   ├── jobs/
│   │   ├── ports/                  # interfaces (contratos)
│   │   └── dto/
│   │
│   ├── domain/
│   │   ├── model/
│   │   ├── units/
│   │   ├── cut/
│   │   │   ├── generators/
│   │   │   └── offset_engine.py
│   │   ├── nesting/
│   │   │   ├── strategies/
│   │   │   └── optimizers/
│   │   └── geometry/
│   │
│   ├── infrastructure/
│   │   ├── importers/
│   │   ├── exporters/
│   │   ├── raster/
│   │   ├── persistence/
│   │   │   └── migrations/
│   │   ├── parallel/
│   │   └── cache/
│   │
│   ├── plugins/
│   │   ├── registry.py
│   │   └── contracts/
│   │
│   └── shared/
│       ├── config/
│       ├── logging/
│       └── errors/
│
├── data/
│   ├── materials.db                # SQLite (biblioteca de materiais, projetos)
│   └── cache/                      # proxies, vetorizações, layouts
├── logs/
├── tests/
│   ├── domain/                     # testes-ouro de geometria/nesting/offset
│   ├── application/
│   └── fixtures/                   # PDFs/PNGs/JPGs de referência
├── build/                          # PyInstaller spec, hooks
└── requirements.txt
```

---

## 4. Responsabilidade de Cada Camada

**Presentation** — Tudo que é Qt. Render do layout no `QGraphicsView` (área de material, peças, faca, réguas, medidas, zoom, pan), drag-and-drop, miniaturas, painéis de parâmetros. **Nenhuma regra de negócio**: cada ação do operador vira um `Command` despachado à Application. Recebe progresso por `Qt Signals`. Todo texto é pt-BR externalizado (Qt Linguist).

**Application** — Orquestra casos de uso completos sem conhecer Qt nem SQL. `Services` coordenam domínio + infraestrutura via *ports*. `Commands` encapsulam ações reversíveis (base de undo/redo e de futura automação headless). `JobManager` enfileira trabalho pesado, reporta progresso e suporta **cancelamento**. `ports/` define as interfaces que a infraestrutura implementa.

**Domain** — O núcleo de valor, Python puro:
- `model`: entidades e invariantes (espaçamento mínimo, validade de offset, margens do material).
- `units`: **fonte única de verdade** de unidades. Todo o domínio opera em **milímetros**; px/pt/DPI só são convertidos nas bordas.
- `cut`: geração de faca por origem + `offset_engine` (Shapely `buffer`: + para fora, − para dentro; trata furos e múltiplos contornos).
- `nesting`: estratégias intercambiáveis + meta-otimizadores; recebem geometria mm, devolvem posição/rotação.
- `geometry`: isola Shapely/NumPy (validação `make_valid`, simplificação Douglas-Peucker, limpeza).

**Infrastructure** — Detalhes plugáveis: importers (PyMuPDF/OpenCV/Pillow), exporters (PDF de produção + DXF via ezdxf), raster (render final e proxies), persistência SQLite, pool de processos e cache em disco. Cada item implementa uma port; nenhum é conhecido pelo núcleo.

---

## 5. Fluxo Completo de Dados

```
[1] DROP de arquivos (Presentation)  ──► miniaturas exibidas (proxies)
        │ caminhos
        ▼
[2] ImportService → IImporter por tipo
        ├─ PDF  → PyMuPDF: dimensão real (pt→mm), detecção de vetor, proxy raster
        ├─ PNG  → OpenCV/Pillow: px + DPI→mm, canal alpha
        └─ JPG  → OpenCV/Pillow: px + DPI→mm (sem alpha)
        ▼  Artwork (mm) + proxy em cache
[3] CutService → ICutGenerator
        ├─ PDF vetor → contorno externo → união → simplificação
        ├─ PNG alpha → threshold → morfologia → findContours → polígono
        └─ JPG       → bounding box retangular
        ▼  CutPath (polígono mm)
[4] OffsetEngine → buffer(+1/+3/+5/+10 | −1/−3/−5/−10 mm) → faca final
        ▼
[5] Operador: cópias por item · material · largura · espaçamento · offset · regras de rotação
        ▼
[6] NestingService → JobManager → ProcessPool
        │ detecta duplicatas → Grid | MaxRects/Skyline → (opcional) Simulated Annealing
        │ progresso via Qt Signals  ◄── cancelável
        ▼  Layout (PlacedItem[]: x, y, rotação, sheet)
[7] Canvas atualiza (proxies) → operador inspeciona (zoom/pan/réguas)
        ▼
[8] ExportService
        ├─ IMPRESSÃO → PDF de produção (vetorial + raster por tiles/streaming)
        └─ CORTE     → DXF (geometria limpa, contornos fechados, escala mm, layers)
        ▼
[9] Persistência SQLite: projeto, layout, parâmetros e job (reabertura/auditoria)
```

**Princípio:** o domínio trabalha **sempre em milímetros**. Conversões DPI/pt/px acontecem **somente nas bordas** — elimina a classe inteira de bugs de escala de software print-and-cut.

---

## 6. Tecnologias Recomendadas

Todas gratuitas e open source, 100% offline:

| Função | Tecnologia | Papel |
|---|---|---|
| Linguagem/Backend | **Python 3.12+ (64-bit)** | Núcleo e orquestração |
| Interface | **PySide6** (LGPL) | Presentation; `QGraphicsView` no canvas |
| Banco | **SQLite** + Repository | Materiais, projetos, jobs |
| Geometria | **Shapely** (GEOS) | Offset, união, validação, NFP |
| PDF | **PyMuPDF** | Dimensão real, extração de vetor, proxy |
| Imagem | **OpenCV** + **Pillow** | Alpha, contornos, leitura de DPI |
| Matemática | **NumPy** | Transformações vetorizadas |
| DXF | **ezdxf** | Exportação de corte |
| SVG (futuro) | **svgpathtools** | Entrada SVG em versão futura |
| Empacotamento | **PyInstaller** | Instalador Windows 10/11 64-bit |
| Testes | **pytest** + golden files | Regressão de geometria/nesting/offset |

> **Licença:** PySide6 é LGPL — uso comercial OK com *dynamic linking* (padrão). Manter inventário de licenças no build para sustentar a regra "100% gratuito" também juridicamente.

---

## 7. Estratégia de Nesting Recomendada

### 7.1 Natureza do problema

Material de **largura fixa e comprimento aberto** → **Strip Packing / Open-Dimension Bin Packing** (minimizar comprimento). Três regimes:

| Regime | Caso típico | Técnica |
|---|---|---|
| Peças idênticas em massa | 1 arte × milhares de cópias | **Grid/Array Packing** (quase ótimo, custo trivial) |
| Retangulares variadas | catálogo de adesivos | **MaxRects + Skyline** |
| Contorno irregular real | facas orgânicas | **NFP / Polygon Nesting** (v2/plugin) |

### 7.2 Comparação das abordagens

| Abordagem | Velocidade | Aproveitamento | Manutenção | Veredito |
|---|---|---|---|---|
| Grid Packing | ★★★★★ | ★★★★★ (p/ idênticas) | ★★★★★ | **v1 — caminho rápido** |
| MaxRects | ★★★★★ | ★★★☆ | ★★★★★ | **v1 — base variada** |
| Skyline | ★★★★ | ★★★ | ★★★★ | **v1 — heurística alt.** |
| Rectangle Packing | ★★★★ | ★★★ | ★★★★ | família do acima |
| NFP / Polygon Nesting | ★★ | ★★★★★ | ★★ | **v2 — plugin** |
| Simulated Annealing | ★★ | ★★★★ | ★★★ | **meta-otimizador opt-in** |

**Chave:** Simulated Annealing **não posiciona peças** — otimiza ordem de inserção e rotações por cima de uma heurística de posicionamento.

### 7.3 Recomendação progressiva

1. **Detector de duplicatas** (hash da faca) → peças idênticas vão a **Grid Packing**. Resolve a maior parte do volume de uma gráfica com custo quase zero.
2. Peças variadas → **MaxRects-BSSF** (Best Short Side Fit), com Skyline como alternativa, rotação 0°/90° e **restrições de rotação** por peça/material.
3. **Simulated Annealing opcional** com *time budget* configurável (ex.: "otimizar por até 30 s") sobre ordem+rotação. Ganho típico de 5–15% de comprimento — a medir com jobs reais.
4. **v2:** plugin **NFP** para encaixe irregular real, ativado quando o ganho justificar o custo de CPU.

Tudo atrás de `INestingStrategy` → **troca de algoritmo sem alterar o restante do sistema** (requisito explícito).

> O ganho de 5–15% do SA é faixa típica de experiência; depende do mix e deve ser medido antes de prometer ao cliente.

---

## 8. Estratégia de Geração de Faca

Pipeline comum: **origem → contorno bruto → limpeza/validação → simplificação → offset → faca final (polígono fechado em mm)**.

**PDF com vetor**
- Extrair paths via PyMuPDF → identificar **contorno externo** → união (Shapely) → simplificar.
- *Fallback* para bounding box quando o vetor for ambíguo (clipping, transparência, múltiplos grupos).

**PNG com transparência**
- Isolar **canal alpha** → threshold → morfologia (fechamento para remover ruído) → `findContours` (OpenCV) → polígono → vetorização → Shapely.
- Tolerância de simplificação (Douglas-Peucker) e limite de vértices **configuráveis** para evitar faca "serrilhada" e pesada.

**JPG**
- v1: **bounding box retangular** automático (sem alpha).
- Futuro: detecção de objeto por IA/segmentação (GrabCut e/ou modelo offline).

**Offset (`offset_engine`)**
- Shapely `buffer`: **positivo = externo** (+1/+3/+5/+10 mm), **negativo = interno** (−1/−3/−5/−10 mm).
- `join_style` controlado (cantos), tratamento de **furos** e **múltiplos contornos**, validação `make_valid` antes e depois.
- Garantia de **contorno fechado** — pré-requisito do DXF de corte.

---

## 9. Estratégia de Exportação DXF

DXF é o **único formato de corte** (não há mais decisão de formato — escopo fechou nisso). Via **ezdxf**, com foco em geometria limpa e previsível:

- **Unidades em milímetros** explícitas no cabeçalho (`$INSUNITS`), escala 1:1 com a faca.
- **Contornos fechados** como `LWPOLYLINE`/`POLYLINE` fechadas (preferível a sequências de `LINE` soltas); curvas aproximadas por polilinha com tolerância configurável (DXF não preserva Bézier de forma universalmente confiável).
- **Layers nomeadas por função**: `CUT` (corte), `CREASE` (vinco), `MARK` (referência/registro), permitindo que o software de máquina do operador mapeie ferramentas.
- **Geometria limpa**: sem auto-interseções, sem duplicatas, sem segmentos degenerados — validação Shapely antes de serializar.
- **Versão DXF estável** (ex.: R2010/AC1024) para máxima compatibilidade de importação.
- Coordenadas no **mesmo referencial do PDF de impressão**, para que faca e arte coincidam quando reunidas no destino.

O **PDF de produção** (impressão) é gerado em paralelo: vetorial onde possível + raster por tiles/streaming para arquivos grandes, evitando materializar a chapa inteira em RAM.

---

## 10. Sistema de Cache

Cache em disco (`data/cache/`) **chaveado por hash de conteúdo** (SHA do arquivo + parâmetros relevantes), com camada em memória LRU para o que está em uso:

| O que se cacheia | Chave | Ganho |
|---|---|---|
| Proxies/thumbnails | hash do arquivo + dimensão alvo | UI instantânea, sem re-render |
| Vetorização de faca | hash do arquivo + parâmetros de geração | evita re-processar OpenCV/PyMuPDF |
| Offset computado | hash da faca + valor de offset | offset é puro → cacheável |
| Layout de nesting | hash(conjunto de peças + material + parâmetros) | reabrir projeto sem recalcular |
| NFPs (v2) | par de polígonos | NFP é caro; reuso massivo |

Política: invalidação por mudança de hash, *eviction* LRU por tamanho-limite configurável, e cache **idempotente** (recomputável a qualquer momento — apagar o cache nunca corrompe um projeto). Tudo offline.

---

## 11. Sistema de Paralelismo

**Regra inviolável: a interface nunca trava.** Nada pesado roda na thread Qt.

| Tipo de trabalho | Mecanismo | Por quê |
|---|---|---|
| I/O leve, coordenação | `QThread` / `QThreadPool` | Mantém UI fluida |
| CPU-bound (vetorização, offset em massa, nesting, render) | **ProcessPoolExecutor** | Contorna o **GIL** com processos reais |

- **Particionamento:** importação e geração de faca são *embaraçosamente paralelas* (uma tarefa por arquivo). O nesting paraleliza por candidato/região e nas iterações do Simulated Annealing.
- **JobManager:** fila com prioridade, **progresso** reportado por `Qt Signals` e **cancelamento** cooperativo — requisito de operação contínua.
- **Serialização entre processos:** trafegar **geometria leve** (coordenadas mm), nunca imagens full-res; o raster pesado fica em disco/cache e é referenciado por caminho.
- **Backpressure:** limitar nº de processos ao nº de núcleos; fila absorve picos de "centenas de arquivos" sem estourar memória.

---

## 12. Persistência, Logs e Tratamento de Erros

**Persistência (SQLite + Repository Pattern):**
- Biblioteca de **materiais** (Adesivo, Lona, PVC, ACM, PS, UV…), cada um com largura, margem, espaçamento padrão e offset padrão.
- Projetos, parâmetros, layouts e histórico de jobs (reabertura e auditoria).
- Migrações versionadas em `persistence/migrations/`. O domínio nunca vê SQL.

**Logs (`shared/logging` → `logs/`):**
- Log estruturado, com níveis (DEBUG/INFO/WARN/ERROR), rotação por tamanho, e **correlation id por job** para rastrear um lote ponta a ponta.

**Tratamento de Erros (`shared/errors`):**
- Hierarquia de exceções de **domínio** (ex.: `FacaInvalidaError`, `MaterialMenorQuePecaError`, `ArquivoNaoSuportadoError`) separadas de erros técnicos.
- Erros em um arquivo de um lote **não derrubam o lote**: o item falho é marcado, registrado e o processamento continua (resiliência de produção).
- Mensagens ao operador em pt-BR, acionáveis; detalhe técnico vai para o log.

---

## 13. Sistema de Plugins

Base já presente desde a v1 via **Strategy + Registry**, ativada plenamente no futuro:

- `plugins/contracts/`: contratos públicos estáveis — `IImporter`, `ICutGenerator`, `INestingStrategy`, `IExporter`.
- `plugins/registry.py`: descoberta e registro por **entry points**; o Composition Root injeta as implementações disponíveis.
- Extensões candidatas: novos formatos de entrada (**SVG** primeiro), novos algoritmos de nesting (NFP), novos geradores de faca (IA para JPG), novos perfis de exportação.
- Nenhuma extensão altera o núcleo — apenas registra novas implementações de interface (OCP na prática).

---

## 14. Plano de Escalabilidade

**Fase 1 — MVP de produção**
Import PDF/PNG/JPG + dimensão real; faca (vetor PDF, alpha PNG, retângulo JPG); offset interno/externo; biblioteca de materiais; nesting Grid+MaxRects; canvas com réguas/zoom/pan; exportação PDF de produção + DXF; SQLite; cache; undo/redo; logs.

**Fase 2 — Qualidade e throughput**
Simulated Annealing opt-in; restrições de rotação avançadas; **modo batch headless** (mesmos services, sem GUI) para filas noturnas; cache e paralelismo endurecidos.

**Fase 3 — Nesting irregular**
Plugin **NFP/Polygon Nesting** para encaixe real de contornos.

**Fase 4 — Plataforma e plugins**
API de plugins estável; entrada **SVG** (svgpathtools); novos perfis de exportação.

**Fase 5 — Inteligência**
JPG com **detecção automática de objeto por IA** (segmentação offline); sugestão automática de material/largura por histórico; otimização multi-chapa.

---

## 15. Riscos Técnicos e Mitigações

| # | Risco | Impacto | Mitigação |
|---|---|---|---|
| 1 | **Erros de escala/unidade** (DPI, pt→mm) | Alto — peça/faca no tamanho errado | Módulo `units` como fonte única; canônico mm; conversão só nas bordas; testes-ouro de dimensão |
| 2 | **Polígonos inválidos** da vetorização (auto-interseção, furos) | Alto — offset/nesting/DXF falham | `make_valid`/buffer(0); Douglas-Peucker; validação obrigatória antes de nesting e antes do DXF |
| 3 | **Vetorização de PNG ruidosa/pesada** | Médio — faca serrilhada, lentidão | Morfologia + simplificação com tolerância configurável; limite de vértices; suavização opcional |
| 4 | **Performance do nesting** em grandes volumes | Alto — viola operação contínua | Detector de duplicatas → grid; heurística rápida + SA opt-in com time budget; NFP só sob demanda |
| 5 | **Consumo de memória** com milhares de cópias | Alto — travamento | Flyweight (1 Artwork ↔ N PlacedItem); proxies; render por tiles; cache em disco |
| 6 | **GIL** congelando a UI | Médio — UX ruim, viola requisito | ProcessPool para CPU-bound; nada pesado na thread Qt; JobManager com cancelamento |
| 7 | **PDF vetorial complexo** (clipping, transparência, contorno ambíguo) | Médio — faca incorreta | Heurística de contorno externo + união; *fallback* para bounding box; revisão visual antes de exportar |
| 8 | **Fidelidade do DXF** (curvas, unidades, contorno aberto) | Alto — corte errado no destino | Polilinha fechada com tolerância; `$INSUNITS`=mm; versão DXF estável; validação geométrica pré-serialização |
| 9 | **Empacotamento Windows** (DLLs nativas GEOS/OpenCV) | Médio — instalação quebrada | PyInstaller com hooks testados; build reproduzível; teste de instalação limpa |
| 10 | **Falha em um arquivo derrubar o lote** | Médio — perda de produtividade | Isolamento por item; erro marcado e logado; lote continua |
| 11 | **Licenciamento** de dependências | Baixo/jurídico | Inventário de licenças no build; PySide6 com linking dinâmico |

---

*Documento de arquitetura — escopo definitivo (v2). Software de preparação de produção: a fronteira de saída são os arquivos PDF e DXF; nenhuma comunicação com máquinas é prevista ou desejada.*
