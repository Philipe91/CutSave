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

## 📐 Especificações
Especificações técnicas de features.

- [FACA-CONTORNO-SPEC.md](especificacoes/FACA-CONTORNO-SPEC.md) — ferramenta de contorno /
  gerador de faca (densidade, cantos, edição manual), estilo CorelDRAW.

## 🛠️ Build & Release
Como empacotar e versionar.

- [BUILD.md](build/BUILD.md) — como gerar o executável (PyInstaller).
- [VERSAO.txt](build/VERSAO.txt) — versão atual.

## 📓 Histórico (session logs)
Registro cronológico do que foi feito em cada sessão (não apagar — é o histórico
do projeto). Ordem do mais recente para o mais antigo:

- [ESTADO-2026-06-30.md](historico/ESTADO-2026-06-30.md) — V2.0 UX: barra de propriedades
  contextual, ferramenta Contorno, alças de mouse, enxugar duplicações.
- [ESTADO-2026-06-29.md](historico/ESTADO-2026-06-29.md) — rotação por peça, marcas na faca,
  duplicar página, centralizar, quantidade, correção da sangria.
- [ESTADO-2026-06-25.md](historico/ESTADO-2026-06-25.md) — redimensionar, Ctrl+Z ilimitado,
  MaxRects, Centro de Exportação, integração CorelDRAW.
- [ESTADO-2026-06-24.md](historico/ESTADO-2026-06-24.md)
- [ESTADO-2026-06-23.md](historico/ESTADO-2026-06-23.md)
- [SESSAO-2026-06-22-FACA-COMPARTILHADA-E-MARCAS.md](historico/SESSAO-2026-06-22-FACA-COMPARTILHADA-E-MARCAS.md)

---

## Convenções
- **Idioma:** documentação em português; código e identificadores em inglês/pt neutro.
- **Histórico:** cada sessão gera um `ESTADO-AAAA-MM-DD.md` em `historico/`. Nunca
  reescrever os antigos — só acrescentar o novo.
- **Unidade canônica:** milímetros (mm) em todo o domínio.
- **Testes:** `python -m pytest` (suíte na pasta `tests/`); `ruff` para lint.

## Integração CorelDRAW
Guia do cliente e macro ficam na pasta [`corel/`](../corel/) na raiz do repositório.
