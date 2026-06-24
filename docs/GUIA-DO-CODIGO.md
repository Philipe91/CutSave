# Guia do Código — PrintNest

> Mapa prático do código **como ele é hoje** (não aspiracional). Serve para entender o sistema rápido e saber onde mexer. Para a visão de design/decisões, ver [ARQUITETURA.md](ARQUITETURA.md).

## Como o programa sobe

```
printnest_main.py  →  app/presentation/__main__.py : main()
```
`__main__.py` é o **Composition Root**: cria os casos de uso e adaptadores (importadores, exportadores, renderer), aplica o tema e abre a `MainWindow`. Para entender as dependências, comece por aqui.

## Caminho do dado (do arquivo ao DXF)

```
Arquivo (PDF/imagem)
  → import (infrastructure/importers)         # vira Artwork em mm
  → faca (domain/cut + use_cases)             # gera o contorno de corte
  → nesting (domain/nesting/grid)             # posiciona na chapa
  → ProductionResult (sheets + artworks)      # estado central
  → preview no canvas (presentation)
  → exportação PDF (impressão) / DXF (corte)
```

## Camadas e onde fica cada coisa

### `app/domain/` — núcleo puro (sem Qt, sem libs de borda)
| Pasta/arquivo | Responsabilidade |
|---|---|
| `model/artwork.py`, `image_artwork.py` | Arte importada (tamanho, tipo, faca) |
| `model/cut_contour.py` | A faca como polígono (pontos em mm) |
| `model/layout.py`, `placement.py`, `material.py` | Chapa, peças posicionadas, material |
| `geometry/` | `Point2D`, `Size`, `BoundingBox`, `Polygon` (área/perímetro), vetor |
| `cut/contour_ops.py` | **Operações da faca**: `offset_contour` (sangria, junção round), `smooth_contour` (Chaikin), `crop_and_rotate_contour` |
| `cut/rectangular.py` | Faca retangular |
| `cut/vector.py` | Gera faca a partir de anéis vetoriais (usado pela faca de PDF por contorno — ver roadmap) |
| `cut/registration.py`, `mimaki.py`, `shared.py` | Marcas de registro, Mimaki, faca compartilhada |
| `nesting/grid.py` | Encaixe em grade (largura fixa, comprimento aberto) |

### `app/application/` — orquestração (conhece domínio + ports, não conhece Qt/SQL)
| Arquivo | Responsabilidade |
|---|---|
| `use_cases/run_production_pipeline.py` | **Pipeline**: importar → faca retangular → nesting → `ProductionResult` |
| `use_cases/import_pdf.py`, `import_image.py` | Casos de uso de importação |
| `use_cases/generate_rectangular_cut.py`, `generate_vector_cut.py` | Geração de faca |
| `use_cases/run_grid_nesting.py` | Nesting em grade |
| `use_cases/export_print_pdf.py`, `export_dxf.py` | Exportação |
| `footprint.py` | Área que cada peça ocupa (arte ∪ faca) — base do nesting |
| `positioning.py` | Marcas de registro / Mimaki |
| `project_io.py` | Salvar/abrir `.printnest` (`PROJECT_SETTING_KEYS`) |
| `ports/` | **Interfaces** que a infraestrutura implementa (DIP) |
| `dto/` | Objetos de fronteira (ex.: `print_placement.py`) |

### `app/infrastructure/` — adaptadores (libs de borda)
| Arquivo | Responsabilidade |
|---|---|
| `importers/pymupdf_importer.py` | PDF → artworks (PyMuPDF); `classify_kind` (vetor/raster) |
| `importers/cv2_image_importer.py` | Imagem → artwork + **detecção de contorno** (OpenCV/Pillow). `detect_contour` é reusado pela faca de PDF por contorno |
| `importers/pymupdf_vector_extractor.py` | Extrai anéis vetoriais do PDF (faca do cliente — roadmap) |
| `exporters/pymupdf_print_exporter.py` | PDF de impressão |
| `exporters/dxf_exporter.py` | DXF de corte (ezdxf) |
| `rendering/pymupdf_renderer.py` | Rasteriza página PDF (preview, miniatura, contorno) |

### `app/presentation/` — interface (PySide6)
| Arquivo | Responsabilidade |
|---|---|
| `main_window.py` | **Janela principal (grande — ver abaixo)**: canvas, painéis, ações, faca, nesting em tempo real, preview, drag-drop, guias, overlay |
| `units.py` | Unidade de exibição mm/cm (interno é sempre mm) |
| `measurements.py`, `messages.py` | Cálculo de medidas / avisos (lógica pura testável) |
| `theme.py`, `icons.py` | Tema (QSS) e ícones SVG |
| `panels/ribbon.py`, `panels/status_bar.py` | Barra de ações e barra de status |
| `widgets/` | `alert`, `card` (CollapsibleCard), `fields` (MeasureField), `toast` |

### `app/shared/` — utilidades transversais
`config/settings.py` (AppSettings + persistência JSON), `config/paths.py`, `logging/`, `errors/`.

## `main_window.py` — guia interno (é o arquivo mais denso, ~3000 linhas)

Classes principais (no topo do arquivo):
- `ZoomableGraphicsView` — canvas com zoom/pan, setas (nudge), **drop de arquivos** e **guias**.
- `Ruler` — réguas em mm/cm; arrastar da régua cria **guia**.
- `MeasureOverlay` — caixinha de medidas no canto.
- `GuideItem` — guia arrastável/selecionável.
- `LengthSpin` — campo de comprimento que guarda **mm** mas exibe na unidade atual (mm/cm).
- `MoveCommand` / `ArrangementCommand` — desfazer/refazer (mover / excluir-duplicar-repetir).
- `PieceItem` — peça na chapa (arte + faca), com snap.
- `MainWindow` — o resto.

Métodos-chave do `MainWindow` (use Ctrl+F):
| Método | O que faz |
|---|---|
| `_build_ui`, `_build_work_area`, `_build_properties_panel` | Monta a janela (biblioteca \| canvas \| painel de abas) |
| `_build_faca_group`, `_build_piece_page`, `_build_object_page` | Painéis de Faca, Seleção (faca por arquivo) e Objeto |
| `generate` / `_relayout` | Gera/recalcula produção (importa → faca → nesting) |
| `_faca_for` / `_image_faca` / `_contour_faca` / `_transform` | Geração de faca por peça (por arquivo via `_params_for`) |
| `_params_for` / `_global_faca_params` / `_file_overrides` | **Faca por arquivo** (override vs padrão do Documento) |
| `_draw_preview` / `_draw_sheets` | Desenha o preview no canvas |
| `_add_file_to_production` | **Arrastar arquivo da biblioteca** para a produção já gerada |
| `_pdf_raster_contour` | Faca de **PDF pelo contorno** (rasteriza + detecta) |
| `_on_selection_changed` | Atualiza abas/medidas/overlay conforme a seleção |
| `_load_settings` / `_save_settings` | Persistência das configurações |

> **Nota de manutenção:** `main_window.py` concentra muita responsabilidade. Uma evolução natural (sem urgência) é extrair as classes do canvas (`ZoomableGraphicsView`, `Ruler`, `GuideItem`, `PieceItem`, overlays) e os widgets `LengthSpin`/comandos para módulos próprios em `presentation/canvas/`. Isso é refatoração **estrutural** (mover código), a ser feita com a suíte de testes verde — não altera comportamento.

## Testes

`tests/` espelha as camadas (`domain/`, `application/`, `presentation/`, `tools/`). Os testes de UI usam `QT_QPA_PLATFORM=offscreen` e constroem a `MainWindow` real. Rodar: `python -m pytest`.

## Regras de ouro do projeto
1. **Tudo em milímetros** internamente; px/pt/DPI e mm/cm só nas bordas (exibição).
2. O **domínio** não importa Qt nem libs de borda; a infraestrutura entra por **ports**.
3. A **interface nunca trava**: trabalho pesado vai para `ProductionWorker`/thread.
4. A saída são **dois arquivos** (PDF + DXF); o sistema não fala com máquinas.
