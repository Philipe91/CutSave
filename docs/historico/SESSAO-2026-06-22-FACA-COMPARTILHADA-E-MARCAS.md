# Sessão 22/06/2026 — Faca compartilhada + Marcas de registro (PC de casa)

> Resumo do que foi implementado nesta sessão, para retomar o contexto depois.
> Tudo testado (238 testes passando) e com lint limpo (ruff).

## Objetivo da sessão

Adicionar duas opções novas na geração da **faca**:

1. **Faca compartilhada** ("linha de fora a fora") — alternativa à faca de quadrados isolados.
2. **5 marcas de registro** (bolinhas) ao redor dos cortes de cada chapa.

Ambas são **opcionais** (ligadas/desligadas por checkbox na interface) e refletem
em tempo real no preview, no PDF de impressão e no DXF de corte.

---

## 1. Faca compartilhada (grade "fora a fora")

**O que faz:** em vez de cada peça ter seu próprio quadrado de corte (linhas
duplicadas entre vizinhos), desenha uma **grade de linhas que atravessam o bloco
inteiro de ponta a ponta**, com **uma única linha separando peças vizinhas** (no
meio do vão entre elas). Peça isolada degrada para o próprio contorno (4 linhas).

**Como liga:** checkbox **"Faca compartilhada (grade fora a fora)"**.

**Saída:** no DXF vira segmentos de reta (`LINE`) na camada `CUT`.

**Lógica:** projeta os retângulos de faca posicionados nos eixos X e Y para
descobrir colunas/linhas; separadores internos ficam no ponto médio de cada vão.

- Domínio: `app/domain/cut/shared.py` (`Segment`, `build_shared_grid`).
- Aplicação: `shared_cut_segments` / `shared_cut_segments_sheets` em
  `app/application/positioning.py`.

---

## 2. Marcas de registro (5 bolinhas)

**O que faz:** cria um quadro imaginário **15 mm afastado das facas** de cada
chapa e posiciona **5 círculos de Ø6 mm**:

- 3 no topo: topo-esquerdo, topo-meio, topo-direito;
- 2 no fundo: inferior-esquerdo, inferior-direito.

O padrão assimétrico (3 em cima, 2 embaixo) é o que a câmera da máquina de corte
de contorno usa para identificar a orientação.

**Como liga:** checkbox **"Marcas de registro (5 bolinhas)"**.

**Saídas:**
- **PDF (impressão):** bolinhas **pretas preenchidas** (a câmera lê). A página
  ganha uma borda automática (padding = 15 + 6 mm) para as marcas caberem; todo o
  conteúdo é deslocado e a folha cresce nos dois eixos.
- **DXF (corte):** círculos na camada separada **`REGMARK`** (azul), como referência.

**Lógica:**
- Domínio: `app/domain/cut/registration.py`
  (`RegistrationMark`, `RegistrationMarkGenerator`). Padrões: margem 15 mm, Ø 6 mm.
- Aplicação: `cuts_bounding_box`, `registration_marks`,
  `registration_marks_sheets` em `app/application/positioning.py`.

---

## Arquivos alterados / criados

**Novos (domínio):**
- `app/domain/cut/registration.py`
- `app/domain/cut/shared.py`

**Alterados:**
- `app/domain/cut/__init__.py` — exporta os novos tipos.
- `app/application/positioning.py` — helpers de bbox, segmentos e marcas (por chapa e multi-chapa).
- `app/application/dto/print_placement.py` — `PrintCircle` + campo `circles` em `PrintSheet`.
- `app/application/ports/dxf_exporter.py` — assinatura aceita `segments` e `marks`.
- `app/application/use_cases/export_dxf.py` — repassa segmentos/marcas.
- `app/application/use_cases/export_print_pdf.py` — calcula marcas e padding da página.
- `app/infrastructure/exporters/dxf_exporter.py` — desenha `LINE` (faca compartilhada)
  e `CIRCLE` na camada `REGMARK`.
- `app/infrastructure/exporters/pymupdf_print_exporter.py` — desenha círculos preenchidos.
- `app/shared/config/settings.py` — novos campos: `shared_faca`, `reg_marks`,
  `reg_margin` (15.0), `reg_diameter` (6.0).
- `app/presentation/main_window.py` — 2 checkboxes; preview, export PDF e export DXF
  passam a respeitar as opções.

**Testes adicionados (22 novos, total 238):**
- `tests/domain/cut/test_shared.py`, `tests/domain/cut/test_registration.py`
- ampliados: `test_positioning.py`, `test_dxf_exporter.py`,
  `test_export_dxf_use_case.py`, `test_export_print_pdf.py`, `test_settings.py`.

---

## Como rodar / testar

A venv usa **Python 3.14** (o projeto exige >=3.12; a `python` global é 3.11).
Chamar o python da venv direto (não precisa ativar):

```powershell
.\.venv\Scripts\python.exe -m pytest          # 238 testes
.\.venv\Scripts\python.exe -m ruff check .     # lint
.\.venv\Scripts\python.exe -m app.presentation # abre a GUI
```

Na GUI: adicionar PDFs → **Gerar Produção** → ligar/desligar os checkboxes
**Faca compartilhada** e **Marcas de registro** (preview atualiza na hora) →
**Exportar PDF** / **Exportar DXF**.

---

## Pendências / ideias para a próxima sessão

- Os valores **15 mm** (afastamento) e **Ø6 mm** (bolinha) estão fixos com padrão
  sensato (salvos em settings), mas **ainda não há campo na interface** para
  ajustá-los. Próximo passo natural: expor esses dois campos na GUI.
- Avaliar se, no modo faca compartilhada, vale **remover o espaçamento** entre
  peças para a linha compartilhada coincidir exatamente com a borda (hoje a linha
  fica no meio do vão).
