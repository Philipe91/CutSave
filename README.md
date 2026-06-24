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
Veja [DOCUMENTAÇÃO/README_BUILD.txt](DOCUMENTAÇÃO/README_BUILD.txt) para detalhes do empacotamento.

---

## O que ele faz

| Recurso | Resumo |
|---|---|
| **Importação** | PDF (vetorial/raster) e imagens PNG/JPG/WEBP, com dimensão real em mm |
| **Faca** | Retângulo automático, **contorno automático** de imagens, e **faca por contorno** de PDF (rasteriza) |
| **Faca por arquivo** | Cada arquivo pode ter sangria/recorte/giro/suavização próprios |
| **Nesting** | Encaixe em grade na largura da chapa (comprimento aberto) |
| **Edição** | Mover, alinhar, distribuir, agrupar, ordem (frente/trás), duplicar, repetir em grade, guias, snap, desfazer/refazer |
| **Unidades** | mm/cm em todo o sistema (réguas, campos, medidas) |
| **Exportação** | PDF de impressão e DXF de corte (única chapa ou por chapa); imagem PNG/JPEG |
| **Projeto** | Salvar/abrir `.printnest` com arquivos e parâmetros |

Atalhos no padrão CorelDRAW (`Ctrl+I` importar, `Ctrl+O` abrir, `Ctrl+G/Ctrl+U` agrupar/desagrupar, `Shift+PageUp/PageDown` ordem, `Ctrl+Z/Ctrl+Shift+Z` desfazer/refazer, `F4` ajustar à tela…).

---

## Documentação

Toda a documentação está na pasta **[DOCUMENTAÇÃO/](DOCUMENTAÇÃO/)**:

| Documento | Conteúdo |
|---|---|
| [ARQUITETURA.md](DOCUMENTAÇÃO/ARQUITETURA.md) | Arquitetura de software (Clean Architecture, camadas, decisões) |
| [GUIA-DO-CODIGO.md](DOCUMENTAÇÃO/GUIA-DO-CODIGO.md) | **Mapa do código atual** — por onde começar, onde fica cada coisa |
| [ROADMAP.md](DOCUMENTAÇÃO/ROADMAP.md) | Próximos passos |
| [PLANO-COMERCIALIZACAO.md](DOCUMENTAÇÃO/PLANO-COMERCIALIZACAO.md) | **Tudo o que falta para vender** (licenciamento, segurança, legal, desempenho) |

---

## Stack

Python 3.10+ · PySide6 (Qt) · PyMuPDF · OpenCV + Pillow · Shapely · NumPy · ezdxf · pytest.

## Estrutura (resumo)

```
app/
  presentation/   # interface (PySide6): janela, canvas, painéis, widgets
  application/    # casos de uso, DTOs, ports (interfaces)
  domain/         # núcleo puro: modelo, geometria, faca, nesting
  infrastructure/ # adaptadores: importadores, exportadores, render
  shared/         # config, logging, erros
tests/            # 380+ testes (domínio, aplicação, apresentação)
scripts/          # ferramentas (ex.: benchmark de desempenho)
DOCUMENTAÇÃO/     # toda a documentação
```
