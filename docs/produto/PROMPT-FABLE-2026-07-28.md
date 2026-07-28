# Prompt para o Fable — PrintNest, 28/07/2026

Cole **uma tarefa por conversa nova**. O histórico é reprocessado a cada turno:
duas tarefas na mesma conversa custam o dobro na segunda.

---

## CABEÇALHO FIXO (cole junto com a tarefa)

```
Projeto: PrintNest (c:\projetos\Cutph), branch v1.3-redesign. App PySide6.
Python do venv: .venv\Scripts\python.exe

REGRAS
1. NÃO quebrar o que funciona. Motor de nesting CONGELADO (só bug).
2. Não reescrever arquivo inteiro: Edit em trecho, nunca Write por cima.
3. Não ler main_window.py inteiro (8k+ linhas). Use as âncoras de linha do
   pedido e leia só a janela indicada (offset/limit).
4. Nada de screenshot para validar: imagem custa muito token. Valide com
   pytest direcionado (-k) ou um script curto que imprime números.
5. Não rodar a suíte inteira; rode só o arquivo de teste afetado.
6. Comentário em português, no padrão do repositório: explique o PORQUÊ
   (o que quebrava antes), não o que a linha faz.
7. Terminou: rode o teste do arquivo afetado e diga o que verificou e o que
   NÃO verificou. Não commite sem eu pedir.
```

---

## TAREFA 1 — Travamento ao soltar PDF com muitas páginas (prioridade)

```
SINTOMA: soltar um PDF de muitas páginas trava a janela por um tempão antes de
as peças aparecerem. Quanto mais páginas, pior.

DOIS SUSPEITOS (confirme com medição ANTES de mexer):
a) app/presentation/main_window.py, add_paths() ~linha 6067: chama
   self._thumbnail(path) por arquivo, que rasteriza pela pdfium na thread da UI.
b) main_window.py, generate() ~linha 6640 e ProductionWorker.run ~linha 1041:
   rasteriza UMA PNG POR PÁGINA em png_map, e no caminho blocking=True isso
   roda inteiro na thread da UI.

COMO MEDIR (sem screenshot): script curto que monta a MainWindow com
QT_QPA_PLATFORM=offscreen, cronometra add_paths() e generate(blocking=True)
com um PDF de 1, 10 e 60 páginas gerado na hora por
app.infrastructure.exporters.pdf_writer.PdfWriter, e imprime os tempos.
Só depois de ver onde estão os segundos, proponha a correção.

NÃO comece a otimizar antes de me mostrar os números.
```

## TAREFA 2 — Tutorial guiado com arquivo de exemplo

```
HOJE: só existe o tour de balões em app/presentation/onboarding.py
(TourOverlay/TourStep), chamado por MainWindow._start_tour ~linha 2172, com
guarda de PYTEST_CURRENT_TEST.

PEDIDO: no primeiro acesso, o tutorial deve usar um ARQUIVO DE EXEMPLO que
vem junto da instalação e ensinar o fluxo real com ele: adicionar → gerar faca
→ exportar. O arquivo fica na raiz da instalação; use
app.shared.resources.resource_path para achá-lo (funciona no .exe do
PyInstaller e rodando do fonte). O instalador é installer/printnest.iss —
o arquivo precisa entrar lá também.

O arquivo de exemplo em si o Philipe vai fornecer; deixe o caminho
parametrizado e um fallback silencioso se ele não existir (nunca travar a
abertura por falta do exemplo).
```

## TAREFA 3 — Menu "Tutoriais" no topo

```
Menu novo ao lado de "Ajuda" (a barra é montada por volta da linha 2019 de
main_window.py: bar.addMenu("A&juda")). Itens: Modo Corte, Marca de registro,
Gerar faca, Duplicar em cadeia — cada um dispara o tour já existente com uma
lista de passos própria (TourStep aponta para o widget e escreve o texto).
Reaproveite TourOverlay; não crie um segundo sistema de tutorial.
```

---

## JÁ FEITO EM 28/07 — não refazer

- **Modo escuro:** zerados os hardcodes de cor em `app/presentation/` (fora dos
  arquivos de tema). O padrão do repositório agora é:
  **folha de estilo com cor do tema congela na montagem** → todo widget que usa
  `setStyleSheet` com token precisa de um `apply_theme()` chamado também em
  `MainWindow._on_theme_changed` (~linha 2239). Já seguem esse padrão:
  `_apply_doc_tabs_theme()`, `_apply_resumo_theme()`, `AnchorCell.apply_theme()`.
- Sub-abas do Documento em estilo aba de fichário (`_build_doc_nav`).
- Seleção de páginas do PDF: só pelo botão "Páginas do PDF..." ou pelo menu do
  botão direito — **não** ao soltar o arquivo.
- Âncora direcional com setas; duplicar em cadeia; recorte de imagem na escala
  certa; faca sem barriga em reta longa.

## PENDÊNCIAS CONHECIDAS (contexto, não são tarefas)

- **Crash `0xc0000374`** (heap corruption) ao mexer na cena: endurecido em
  28/07 mas **sem reprodução**. Se aparecer, ler
  `%APPDATA%\PrintNest\logs\crash.log` (faulthandler ligado).
- **Segfault no encerramento do pytest** (exit 139): ANTIGO, existe desde o
  commit 13a5412. A suíte passa inteira; o tombo é no teardown e mascara o
  resumo do pytest. Não é regressão, não perca tempo com ele.
- **Bug de repaint** (fundo "abaixa" ao clicar em alguma opção, só volta ao
  minimizar/maximizar): causa desconhecida, falta o gatilho exato. Suspeita não
  confirmada: `QGraphicsView` usa o `MinimalViewportUpdate` padrão.
