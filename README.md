# PrintNest

**Preparador de produção gráfica** para Windows: importa PDF/imagens, gera a **faca** (linha de corte), faz o **nesting** (encaixe na chapa) e exporta **PDF de impressão + DXF de corte**.

> Software 100% offline, em português. A fronteira de saída são dois arquivos (PDF + DXF) levados aos softwares de máquina já existentes — o PrintNest **não** controla máquinas.

---

## Início rápido (desenvolvimento)

```bash
# 1) ambiente virtual
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell/CMD)

# 2) dependências
pip install -r requirements.txt
pip install -r requirements-dev.txt   # para rodar os testes

# 3) rodar o app
python -m app.presentation
# (ou)
python printnest_main.py

# 4) rodar os testes
python -m pytest
```

## Build do executável (Windows)

```bash
build.bat            # gera o .exe via PyInstaller (PrintNest.spec)
```
Veja [docs/build/BUILD.md](docs/build/BUILD.md) para detalhes do empacotamento.

---

## O que ele faz

| Recurso | Resumo |
|---|---|
| **Importação** | PDF (vetorial/raster) e imagens PNG/JPG/WEBP, com dimensão real em mm |
| **Faca** | Retângulo automático, **contorno automático** de imagens, e **faca por contorno** de PDF (rasteriza) |
| **Faca por arquivo** | Cada arquivo pode ter sangria/recorte/giro/suavização próprios |
| **Nesting** | Encaixe em grade na largura da chapa (comprimento aberto) |
| **Modo Corte** | Fluxo só-corte true-shape: SVG/PDF vetorial e texto→curvas, encaixe com giro e preencher furos, mover/girar no preview, DXF de dentro para fora, plugin CorelDRAW ida-e-volta |
| **Marcas de registro** | 6 formas (bolinhas, L, bolinhas+L, quadrados, cruzes, L de canto) com distância, tamanho e espessura ajustáveis — idênticas no preview, PDF e DXF |
| **Faca do cliente** | Reaproveita a faca desenhada no arquivo (traço magenta 100% sem preenchimento) |
| **Edição** | Mover, alinhar, distribuir, agrupar, ordem (frente/trás), duplicar, repetir em grade, guias, snap, desfazer/refazer |
| **Unidades** | mm/cm em todo o sistema (réguas, campos, medidas) |
| **Exportação** | PDF de impressão e DXF de corte (única chapa ou por chapa); imagem PNG/JPEG |
| **Projeto** | Salvar/abrir `.printnest` com arquivos e parâmetros |

Atalhos no padrão CorelDRAW (`Ctrl+I` importar, `Ctrl+O` abrir, `Ctrl+G/Ctrl+U` agrupar/desagrupar, `Shift+PageUp/PageDown` ordem, `Ctrl+Z/Ctrl+Shift+Z` desfazer/refazer, `F4` ajustar à tela…).

---

## Documentação

Toda a documentação está organizada por tema em **[docs/](docs/README.md)** — comece pelo índice:

| Área | Documento |
|---|---|
| 🏛️ Arquitetura | [docs/arquitetura/ARQUITETURA.md](docs/arquitetura/ARQUITETURA.md) · [GUIA-DO-CODIGO.md](docs/arquitetura/GUIA-DO-CODIGO.md) · [DESIGN.md](docs/arquitetura/DESIGN.md) |
| 🗺️ Produto | [docs/produto/ROADMAP.md](docs/produto/ROADMAP.md) · [PLANO-COMERCIALIZACAO.md](docs/produto/PLANO-COMERCIALIZACAO.md) |
| 📐 Especificações | [docs/especificacoes/FACA-CONTORNO-SPEC.md](docs/especificacoes/FACA-CONTORNO-SPEC.md) |
| 🛠️ Build | [docs/build/BUILD.md](docs/build/BUILD.md) |
| ✅ QA | [docs/qa/](docs/qa/) — charters e relatórios de qualidade (último: [RELATORIO-QA-2026-07-22.md](docs/qa/RELATORIO-QA-2026-07-22.md)) |
| ⚖️ Jurídico | [docs/produto/juridico/](docs/produto/juridico/) — EULA, privacidade, termos de venda |
| 📓 Histórico | [docs/historico/](docs/historico/) — session logs (um por sessão) |

Mudanças por versão: [CHANGELOG.md](CHANGELOG.md).

---

## Stack

Python 3.10+ · PySide6 (Qt) · pypdfium2 + pikepdf (PDF, licenças livres) · OpenCV + Pillow · Shapely · NumPy · ezdxf · fontTools · pytest.

> PyMuPDF/fitz é **dev-only** (AGPL): nunca entra em `app/`.

## Estrutura (resumo)

```
app/
  presentation/   # interface (PySide6): janela, canvas, painéis, widgets
  application/    # casos de uso, DTOs, ports (interfaces)
  domain/         # núcleo puro: modelo, geometria, faca, nesting
  infrastructure/ # adaptadores: importadores, exportadores, render
  shared/         # config, logging, erros
tests/            # testes (domínio, aplicação, apresentação)
scripts/          # ferramentas (ex.: benchmark de desempenho)
corel/            # integração CorelDRAW (macro + guia do cliente)
docs/             # documentação organizada por tema (ver docs/README.md)
```
