# Documentação — PrintNest Pro

Índice central da documentação do projeto. Organizada por tema.

> **Software Windows (PySide6)** de preparação de produção gráfica: importa
> PDF/PNG/JPG, gera **faca de corte**, faz **nesting** e exporta **PDF de
> impressão** e **DXF de corte**. Núcleo em arquitetura limpa (domínio →
> aplicação → infraestrutura → apresentação), unidade canônica **mm**.

---

## 🏛️ Arquitetura
Como o sistema é construído por dentro.

- [ARQUITETURA.md](arquitetura/ARQUITETURA.md) — camadas, módulos e decisões estruturais.
- [DESIGN.md](arquitetura/DESIGN.md) — princípios de design/UX.
- [GUIA-DO-CODIGO.md](arquitetura/GUIA-DO-CODIGO.md) — guia de código para desenvolvedores.

## 🗺️ Produto
Direção do produto e negócio.

- [ROADMAP.md](produto/ROADMAP.md) — fases, marcos e o que já foi feito.
- [PLANO-COMERCIALIZACAO.md](produto/PLANO-COMERCIALIZACAO.md) — bloqueadores e plano de venda.
- [LICENCIAMENTO.md](produto/LICENCIAMENTO.md) — como funciona a licença/ativação.
- [ROBO-ATIVACAO.md](produto/ROBO-ATIVACAO.md) — robô que emite chave por e-mail sem operador.
- [FACA-DO-CLIENTE.md](produto/FACA-DO-CLIENTE.md) — faca vinda do arquivo do cliente (traço magenta).
- [FASE6-PRENCHER-FUROS.md](produto/FASE6-PRENCHER-FUROS.md) — nesting true-shape com furos.
  **Topo do arquivo: motor de nesting CONGELADO (decisão de 22/07).**
- [TUTOR-IA.md](produto/TUTOR-IA.md) — tutor de boas-vindas dentro do app.
- [COPY-SITE-VENDAS.md](produto/COPY-SITE-VENDAS.md) — textos do site de vendas
  (o site em si vive em `site/`, ponto de retomada em `site/ESTADO-SITE.md`).

### ⚖️ Jurídico
- [EULA.md](produto/juridico/EULA.md) · [POLITICA-DE-PRIVACIDADE.md](produto/juridico/POLITICA-DE-PRIVACIDADE.md) · [TERMOS-DE-VENDA-E-GARANTIA.md](produto/juridico/TERMOS-DE-VENDA-E-GARANTIA.md)

### 🤖 Processo com IA (interno, não vai para o cliente)
- [PROMPTS-BACKLOG.md](produto/PROMPTS-BACKLOG.md) — prompts mestres das tarefas
  (uma tarefa por conversa; cabeçalho fixo no topo). Estado atual: F1 entregue,
  F2 (persistir arranjo manual) em andamento.
- [QA-MASTER.md](produto/QA-MASTER.md) — charter da missão de QA (o prompt que gera
  os relatórios de `docs/qa/`).

## ✅ QA
Charters e relatórios de qualidade, do mais recente para o mais antigo.

- [RELATORIO-QA-2026-07-22.md](qa/RELATORIO-QA-2026-07-22.md) — **QA MASTER PREMIUM**:
  veredito, 20+ achados, notas 0–10, roteiro manual de 22 itens. Correções: F1
  entregue (commit `1963870`), F2 em andamento. Testes da missão em `tests/qa/`.
- [RELATORIO-QA-EXTREMO-2026-07-13.md](qa/RELATORIO-QA-EXTREMO-2026-07-13.md)
- [RELATORIO-QA-2026-07-08.md](qa/RELATORIO-QA-2026-07-08.md)
- [RELATORIO-QA-2026-07-02.md](qa/RELATORIO-QA-2026-07-02.md)
- [QA-MASTER-3.0-FUNCIONAL.md](qa/QA-MASTER-3.0-FUNCIONAL.md) · [QA-MASTER-2.0.md](qa/QA-MASTER-2.0.md) — charters antigos.
- [ROTEIRO-HOMOLOGACAO.md](qa/ROTEIRO-HOMOLOGACAO.md) — homologação manual na máquina real.

## 📐 Especificações
Especificações técnicas de features.

- [FACA-CONTORNO-SPEC.md](especificacoes/FACA-CONTORNO-SPEC.md) — ferramenta de contorno /
  gerador de faca (densidade, cantos, edição manual), estilo CorelDRAW.

## 🛠️ Build & Release
Como empacotar e versionar.

- [BUILD.md](build/BUILD.md) — como gerar o executável (PyInstaller).
- [VERSAO.txt](build/VERSAO.txt) — versão atual.
- Mudanças por versão: [CHANGELOG.md](../CHANGELOG.md) na raiz.

## 📓 Histórico (session logs)
Registro cronológico do que foi feito em cada sessão (não apagar — é o histórico
do projeto). Ordem do mais recente para o mais antigo:

- [ESTADO-2026-07-09.md](historico/ESTADO-2026-07-09.md)
- [ESTADO-2026-07-06.md](historico/ESTADO-2026-07-06.md)
- [ESTADO-2026-07-03.md](historico/ESTADO-2026-07-03.md)
- [ESTADO-2026-07-02.md](historico/ESTADO-2026-07-02.md) — ponto de retomada do redesign v1.3.
- [ESTADO-2026-06-30.md](historico/ESTADO-2026-06-30.md) — V2.0 UX: barra de propriedades
  contextual, ferramenta Contorno, alças de mouse, enxugar duplicações.
- [ESTADO-2026-06-29.md](historico/ESTADO-2026-06-29.md) — rotação por peça, marcas na faca,
  duplicar página, centralizar, quantidade, correção da sangria.
- [ESTADO-2026-06-25.md](historico/ESTADO-2026-06-25.md) — redimensionar, Ctrl+Z ilimitado,
  MaxRects, Centro de Exportação, integração CorelDRAW.
- [ESTADO-2026-06-24.md](historico/ESTADO-2026-06-24.md)
- [ESTADO-2026-06-23.md](historico/ESTADO-2026-06-23.md)
- [SESSAO-2026-06-22-FACA-COMPARTILHADA-E-MARCAS.md](historico/SESSAO-2026-06-22-FACA-COMPARTILHADA-E-MARCAS.md)

> A partir de 07/2026 o registro por sessão migrou para o
> [CHANGELOG.md](../CHANGELOG.md) + relatórios de QA; os ESTADO-*.md antigos
> ficam como histórico.

---

## Convenções
- **Idioma:** documentação em português; código e identificadores em inglês/pt neutro.
- **Unidade canônica:** milímetros (mm) em todo o domínio.
- **Testes:** `python -m pytest` (suíte em `tests/`; missões de QA em `tests/qa/`);
  `ruff` para lint.
- **PDF:** `pypdfium2` + `pikepdf` no app; PyMuPDF/fitz é **dev-only** (AGPL),
  nunca em `app/`.
- **Decisões vigentes:** motor de nesting congelado (só bug reabre); Cartelas
  desligado por flag (`CARTELAS_ENABLED=False`); Modo Corte não se integra ao
  canvas de impressão (E1 cancelada — ver PROMPTS-BACKLOG.md).

## Integração CorelDRAW
Guia do cliente e macro ficam na pasta [`corel/`](../corel/) na raiz do repositório.
