# Relatório QA Master — 02/07/2026

Auditoria completa executada por 4 frentes paralelas (fluxos/arquivos hostis,
stress/performance, consistência UI e caça-bugs/undo), com **prova de execução**
para cada achado (testes reais contra a `MainWindow` offscreen + suíte de 446
testes). Nenhum achado é especulação; suspeitas sem prova estão marcadas.

## Veredito da auditoria

**NÃO APROVADO PARA PRODUÇÃO** no estado auditado — 3 críticos + 1 alto.
**Todos os 4 bloqueadores foram corrigidos na mesma sessão** (ver seção
"Correções aplicadas"); com eles fechados + beta em gráficas reais, o produto
fica aprovável.

| Categoria | Nota |
|-----------|------|
| Estabilidade | 8/10 |
| UX | 7/10 |
| UI | 7,5/10 |
| Performance | 8,5/10 |
| Consistência | 6/10 |
| Escalabilidade | 7/10 |
| Confiabilidade | 6/10 (antes das correções) |

## Bugs críticos/altos encontrados (e corrigidos em 02/07)

### QA-01 🔴 Desfazer giro de peça era ilusório
- **Repro:** girar peça → Ctrl+Z (visual volta) → mudar qualquer parâmetro
  (sangria/espaçamento) → **a peça voltava girada sozinha**.
- **Causa:** `_piece_rotations` mutado antes do snapshot e fora do undo.
- **Correção:** snapshot de undo agora carrega `(chapas, artes, giros)`;
  `_rotate_selected` captura o estado **antes** de mutar e registra o comando
  manualmente. Teste: `test_desfazer_giro_de_peca_limpa_o_giro_de_verdade`.

### QA-02 🔴 Falha de exportação era silenciosa
- **Repro:** exportar PDF para pasta inexistente/sem permissão → exceção crua
  `FzErrorSystem` (PyMuPDF ≥ 1.26 não herda de RuntimeError/OSError) → no exe,
  o clique "não fazia nada".
- **Correção:** (a) exportador captura também a base do PyMuPDF
  (`_EXPORT_ERRORS` em `pymupdf_print_exporter.py`); (b) decorator
  `@_guard_export` nos 5 `export_*` da janela — qualquer falha vira diálogo
  amigável. Teste: `test_falha_de_exportacao_mostra_dialogo_e_nao_estoura`.

### QA-03 🔴 Exportar Faca sem faca gerada gravava PDF em branco
- **Repro:** soltar arquivo (modo sem faca) → esquecer "Gerar Faca" → Exportar
  Faca → PDF válido de 530 bytes **sem nenhuma linha de corte** ia pra máquina.
- **Correção:** `export_faca_pdf` valida o payload antes de pedir o nome do
  arquivo; recusa gravar e avisa ("Clique em Gerar Faca antes"). Teste:
  `test_exportar_faca_sem_faca_nao_grava_pdf_em_branco`.

### QA-04 🟠 Mesmo arquivo importado 2× = quantidade errada silenciosa
- **Repro:** mesmo PNG em 2 linhas, qtd 3 e 5 → esperado 8, saía **10** (IDs e
  quantidades são indexados por caminho; a última linha sobrescrevia).
- **Correção:** `add_paths` não cria mais linha duplicada — soma +1 na
  quantidade da linha existente (modelo de dados é por-arquivo; overrides,
  recortes e tamanhos também são por caminho). Teste:
  `test_mesmo_arquivo_importado_2x_soma_quantidade`.

### QA-05 🔴→✅ Combo "Tipo de faca" cortava o texto (corrigido na hora)
`AdjustToContents` — o combo dimensiona pelo item mais longo.

## Pendências — status pós-correções (02/07, 2ª rodada)

| # | Sev. | Achado | Status |
|---|------|--------|--------|
| QA-06 | 🟠 | Drift de cores do canvas vs. tokens (`CUT`/`MARK`/`EMPTY`, "azul do tema" errado, vermelho fora da paleta, brancos) | ✅ **corrigido** — canvas 100% nos tokens |
| QA-07 | 🟡 | Duplicar/undo em cadeia degrada (redraw total por operação) | 🔶 **mitigado** (-20%: memoização de footprint/params por id no redesenho). Correção definitiva = redesenho incremental (backlog) |
| QA-08 | 🟡 | Fechar durante geração: QThread órfã (crash "fechou sozinho") | ✅ **corrigido** — `closeEvent` espera a thread (`quit`+`wait`) |
| QA-09 | 🟡 | Alt+O ambíguo (Organizar × Opções) | ✅ **corrigido** — Opções virou Alt+P |
| QA-10 | 🟡 | 100+ strings de UI sem acento | ✅ **corrigido** — passada via tokenize (só strings/comentários; identificadores e dados intactos; QSS simétrico) |
| QA-11 | 🟡 | Suíte: segfault de teardown do Qt após 100% verde (exit 139) | ✅ **corrigido** — causa: shutdown do PySide6 (caches de QPixmap + QLocalServer no detach das DLLs). Solução no conftest: fechar janelas em `pytest_sessionfinish` e desarmar em `pytest_unconfigure` via `TerminateProcess` (pula o detach), preservando o exitstatus real (falha continua saindo ≠ 0 — validado) |
| QA-12 | 🟢 | Clipboard de peças não era por-aba | ✅ **corrigido** — limpo em `_apply_session` |
| QA-13 | 🟢 | Espaçamentos 6/2px deliberados em `fields.py` | mantido (decisão de design documentada) |

## O que aguentou o tranco (verificado)

- Motor: 5.000 peças nested em 65ms; 60 arquivos importados+organizados em 0,8s;
  benchmarks oficiais dentro das metas.
- Robustez: PDF corrompido, 0 bytes, JPEG CMYK, PNG 1×1, imagem 4000², nome com
  emoji/acento/&, arquivo sumido do disco → erro amigável, zero crash.
- Salvar/reabrir preserva tudo (inclusive faca contorno + sangria); abas
  independentes; zoom 1000×; sem leak de memória detectável (10 ciclos);
  undo de duplicar/colar com round-trip perfeito; foco de teclado e tooltips 100%.

## Não verificável neste ambiente (checklist manual)

- Monitor 4K físico e escala Windows 125/150/200% ao vivo (por código: DPI
  delegado ao Qt6, correto; sem px fixo de alto risco).
- Múltiplos monitores; 200 PDFs reais de clientes (recomendado no beta).
