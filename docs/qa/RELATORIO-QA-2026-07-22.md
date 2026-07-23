# Relatório QA MASTER PREMIUM — 22/07/2026

> Charter: `docs/produto/QA-MASTER.md`. Branch `v1.3-redesign`, pós E3/E4/A2-A3.
> **Linha de base: 723 testes, 100% verdes** (10×72+3 pontos; o sumário final
> foi engolido pelo crash conhecido 0xC0000005 no teardown do Qt — fato
> conhecido, não conta como achado). E4 está commitada dentro do checkpoint
> `5644afc`; A2/A3 é `fe0045b` — pré-requisitos cumpridos.
> Método: 3 fontes de evidência, sempre declaradas — TESTE (tests/qa/),
> MEDIÇÃO (scripts) e LEITURA DE CÓDIGO (= "suspeita", nunca bug confirmado).
> Nada foi corrigido nem commitado nesta missão.

Nota de execução: o PC desligou no meio da primeira rodada das Fases 2A/3/5/8;
os agentes foram retomados e re-executaram tudo — nenhum número abaixo vem de
medição perdida.

---

## Sumário executivo

| Fase | Status | Resultado |
|---|---|---|
| 1 Inventário × cobertura | ✅ | ~60 ações mapeadas; 13 buracos de cobertura |
| 2A E2E janela principal + registro | ✅ | 42 testes (37✅ 5 xfail): 🔴1 🟠2 🟡1 |
| 2B E2E Modo Corte (E3) | ✅ | 15 testes novos, 15 verdes, 0 bugs |
| 3 Entradas hostis | ✅ | 28 testes (20✅ 8 xfail): 🔴2 🟠1 🟡1; 16/16 casos |
| 4 UX por código | ✅ | 🟠1 🟡2 (+1 🟠 compartilhado c/ F9) |
| 5 Performance | ✅ | 🔴1 (O(n²) fora do motor) 🟠1 🟡2 |
| 6 Roteiro manual | ✅ | 20 itens (fim deste relatório) |
| 7 Consistência | ✅ | tudo checado; achados 🟢 |
| 8 Dia de produção | ✅ | 3 ciclos estáveis; gargalo export_dxf 7,1 s (=A10) |
| 9 Bug hunting por código | ✅ | 🟠2 🟡3 🟢3; 6 suspeitas descartadas c/ evidência |

---

## ACHADOS

Formato: Título · Descrição/Passos · Esperado × Obtido · Evidência · Impacto ·
Probabilidade · Prioridade · Sugestão (NÃO aplicada).

### 🔴 A0 — Arranjo manual NÃO sobrevive a salvar+reabrir (duplicatas, posições, giro por peça)
- **Passos**: gerar produção → Ctrl+D numa peça / mover peças à mão / girar
  UMA peça (Ctrl+[ ou ]) → Ctrl+S → fechar → reabrir o .printnest.
- **Esperado** (promessa do produto e do charter): "TUDO igual — posições,
  quantidades, overrides".
- **Obtido**: `_collect_project()` grava só a QUANTIDADE da tabela +
  overrides por arquivo; o arranjo manual (`self._result`) e o giro por peça
  (`_piece_rotations`) nunca entram no `.printnest`. Reabrir perde a cópia
  extra, a posição movida volta ao nesting automático e o giro da peça some.
  SEM nenhum aviso ao salvar (contraste: "Resetar arranjo" avisa que
  descarta). Giro de ARQUIVO persiste corretamente (teste verde).
- **Evidência**: TESTE —
  `tests/qa/test_qa_f2a_roundtrip.py::test_duplicar_e_mover_sobrevive_ao_salvar_e_reabrir`
  e `::test_girar_peca_individual_sobrevive_ao_salvar_e_reabrir` (ambos
  xfail QA-F2A-01/02 enquanto o bug existir).
- **Impacto**: o operador monta a chapa à mão (recurso vendido!), salva
  confiando no Ctrl+S e perde o trabalho ao reabrir — perda silenciosa de
  trabalho no fluxo central. **Probabilidade**: alta (fluxo diário).
- **Prioridade: 🔴 Crítico** (se for decisão de design, precisa no mínimo
  de aviso "o arranjo manual não é salvo" — hoje não há).
- **Sugestão**: persistir `placements`/`_piece_rotations` no
  ProjectDocument (campo aditivo, projeto antigo continua abrindo), ou
  avisar explicitamente ao salvar.

### 🔴 A13 — Girar peça duplicada re-seleciona TODAS as cópias; girar+duplicar cresce exponencial
- **Passos**: 1 peça → Ctrl+D (2 peças, 1 selecionada) → girar (Ctrl+] — a
  seleção vira TODAS as cópias) → Ctrl+D (duplica as 2 → 4) → girar → Ctrl+D
  (→ 8)… Cada ciclo DOBRA em vez de +1; em 39 iterações chegou a 1024 peças.
- **Causa**: `_rotate_selected` (~7435-7468) chama `_reselect_by_artwork`
  (`main_window.py:7474`), que seleciona todas as peças com o mesmo
  `artwork_id` — e as cópias de Ctrl+D herdam o id do original.
- **Evidência**: TESTE —
  `tests/qa/test_qa_f3_stress.py::test_girar_depois_duplicar_nao_deveria_multiplicar_todas_as_copias`
  (xfail).
- **Impacto**: fluxo plausível ("girar, duplicar mais uma") multiplica a
  quantidade sem aviso — produção com quantidade muito maior que a
  pretendida = desperdício de material real. De quebra, com 512 peças o
  `_rotate_selected` levou ~35 s (agrava o A10).
  **Probabilidade**: média-alta. **Prioridade: 🔴 Crítico**.
- **Sugestão**: após girar, restaurar a SELEÇÃO original (itens
  específicos), não "todas do mesmo artwork".

### 🔴 A14 — Gerar produção síncrona estoura exceção crua com PDF vazio/corrompido/0 páginas
- **Passos**: importar PDF de 0 bytes (ou bytes aleatórios com extensão
  .pdf, ou PDF válido sem páginas) por um dos caminhos que usam
  `generate(blocking=True)`: "Gerar Faca" sem produção (~5426), soltar 1
  arquivo da biblioteca na área vazia (~7058/7074), reaplicar recorte
  (~5898/5905).
- **Obtido**: o ramo `if blocking:` (`main_window.py:6174-6182`) não tem
  try/except — `PdfImportError`/`ValidationError` sobem cru (no app real =
  janela de erro do Python/estado indefinido). O caminho por thread
  (`ProductionWorker`) trata e avisa direito — provado por teste verde.
- **Evidência**: TESTE — `tests/qa/test_qa_f3_malformed_files.py::
  test_pdf_vazio_0_bytes_nao_estoura`, `::test_pdf_corrompido_bytes_aleatorios_nao_estoura`,
  `::test_pdf_sem_paginas_nao_estoura` (xfail) vs
  `::test_pdf_corrompido_via_thread_worker_mostra_erro_amigavel` (verde).
- **Impacto**: arquivo ruim de cliente é rotina em gráfica; o caminho mais
  comum (F5) avisa, os atalhos síncronos estouram.
  **Prioridade: 🔴 Crítico** (é crash de cara para o operador).
- **Sugestão**: envolver o ramo blocking no mesmo padrão do `_on_failed`.

### 🟠 A15 — .printnest com lixo binário estoura UnicodeDecodeError sem aviso
- **Causa**: `ProjectStore.load()` (`project_io.py:159-162`) faz
  `read_text(encoding="utf-8")` e o `except (OSError, json.JSONDecodeError)`
  não cobre `UnicodeDecodeError`. Truncado e versão futura são tratados; lixo
  binário não.
- **Evidência**: TESTE — `tests/qa/test_qa_f3_lifecycle.py::
  test_printnest_lixo_binario_avisa_e_nao_perde_trabalho_atual` (xfail).
- **Prioridade: 🟠**. **Sugestão**: incluir `UnicodeDecodeError` no except.

### 🟠 A1b — "Substituir arquivo" deixa a produção com o conteúdo do arquivo antigo
- **Passos**: produção gerada → biblioteca → Substituir arquivo selecionado →
  escolher outro arquivo.
- **Obtido**: `replace_selected()` troca o caminho na tabela mas só chama
  `_relayout()` (recalcula geometria dos artworks JÁ importados) — a chapa
  continua mostrando/cortando o CONTEÚDO antigo até um "Gerar Produção"
  manual. O nome exibido é o novo; a arte é a velha.
- **Evidência**: TESTE —
  `tests/qa/test_qa_f2a_buracos.py::test_substituir_arquivo_selecionado_atualiza_producao`
  (xfail QA-F2A-04; workaround "gerar de novo" confirmado verde).
- **Impacto**: risco direto de imprimir/cortar a arte errada achando que já
  trocou — o próprio tooltip vende o caso "arquivo não encontrado".
  **Prioridade: 🟠 Alto**. **Sugestão**: reimportar o novo arquivo no
  próprio `replace_selected` (ou disparar a re-geração automaticamente).

### 🟠 A1 — Recorte de página ignorado em silêncio quando o "bake" falha
- **Passos**: importar PDF → Recortar página → definir recorte → OK (toast
  "Recorte aplicado a N página(s)" já dispara AQUI, antes do processamento
  real) → Gerar Produção com qualquer falha no bake (PDF com objeto exótico,
  %TEMP% sem espaço/permissão).
- **Esperado**: aviso claro de que o recorte não pôde ser aplicado.
- **Obtido**: `_bake_cropped_pdf`/`_bake_cropped_image` terminam em
  `except Exception: return None` e `_effective_path` devolve o arquivo
  ORIGINAL inteiro — a produção sai SEM o recorte e nenhum aviso aparece.
  O toast de sucesso já tinha aparecido.
- **Evidência**: LEITURA DE CÓDIGO — `app/presentation/main_window.py:5936-6004`
  (bake), `:5930-5931` (fallback), `:5899` (toast precoce), `:5862-5863`
  (preview do diálogo de recorte também silencia falhas).
- **Impacto**: impressão sai com bordas/marcas que o operador mandou remover —
  trabalho entregue errado sem ninguém saber. **Probabilidade**: baixa (exige
  falha no bake), mas o custo é alto. **Prioridade: 🟠 Alto**.
- **Sugestão**: quando o bake devolver None com crop configurado, mostrar
  aviso ("Recorte de X não pôde ser aplicado — imprimindo original") e mover o
  toast de sucesso para depois do bake real (ou removê-lo).

### 🟠 A2 — Colar descarta peças em silêncio se o número de chapas diminuiu
- **Passos**: produção com 5 chapas → copiar peças da chapa 5 (Ctrl+C) →
  reduzir quantidade/trocar material (produção agora tem 2 chapas) → Ctrl+V.
- **Esperado**: peças coladas em alguma chapa válida, ou aviso.
- **Obtido**: `_paste_clipboard` valida `art_id` mas não `sheet_index`;
  `_add_placed` só itera as chapas ATUAIS — entradas com índice inexistente
  nunca são lidas. As peças somem sem erro nem toast.
- **Evidência**: LEITURA DE CÓDIGO — `app/presentation/main_window.py:7173-7189`
  e `:6986-7008`. (Teste de reprodução: [PENDENTE — Fase 2A/3].)
- **Impacto**: perda silenciosa de parte de um colar. **Probabilidade**: média
  (sequência plausível no dia a dia). **Prioridade: 🟠 Alto**.
- **Sugestão**: clampar `sheet_index` para a última chapa existente (ou colar
  na chapa atual), e/ou avisar "N de M peças coladas".

### 🟠 A3 — Exceção não prevista chega crua ao operador (inglês/técnica)
- **Descrição**: a "última linha de defesa" de exportações
  (`_guard_export`), da geração (`ProductionWorker`→`_on_failed`) e do Modo
  Corte (`_guarded`, `_on_nest_done`) exibe `str(exc)` de QUALQUER exceção:
  um `PermissionError: [Errno 13] Permission denied: 'C:\...'` de
  pikepdf/PIL/OS aparece assim, em inglês, num QMessageBox.
- **Esperado**: erros imprevistos com moldura amigável ("Erro inesperado —
  envie esta mensagem ao suporte: …").
- **Evidência**: LEITURA DE CÓDIGO — `main_window.py:1418-1439`, `:1040-1053`,
  `:6235-6237`; `cut_mode_dialog.py:763-764, 778-779, 1137-1143`. Erros de
  domínio conhecidos (ValidationError/ProjectError) já saem em português —
  o problema é só o caminho imprevisto.
- **Impacto**: operador de gráfica sem instrução do que fazer; percepção de
  produto frágil. **Probabilidade**: baixa por definição (só bugs/ambiente).
  **Prioridade: 🟠 Alto** (é a cara do produto na pior hora).
- **Sugestão**: padronizar a última defesa com prefixo amigável + detalhe
  técnico copiável.

### 🟡 A4 — Marcas de registro no PDF saem DeviceRGB(0,0,0), não K 100% puro
- **Descrição**: todas as marcas (antigas e novas A2/A3) são desenhadas no PDF
  de impressão com operador `rg` (DeviceRGB 0,0,0). Em RIP CMYK, RGB-preto
  costuma converter para "rich black" (CMY+K), o que pode prejudicar leitura
  óptica (OPOS/ARMS/câmeras) e registro fino nas bordas.
- **Evidência**: **TESTE** (confirmado — QA-F2A-03):
  `tests/qa/test_qa_f2a_registro.py::test_marcas_de_registro_pdf_usa_operador_k_e_nao_rg`
  lê o content stream real com pikepdf: nenhuma marca usa `k`/`K`, todas
  `0 0 0 rg/RG`. Código: `pikepdf_print_exporter.py:58-76` + `pdf_writer.py`.
  Padrão PRÉ-EXISTENTE (não é regressão da A2/A3). Impacto prático depende
  do RIP (a maioria trata RGB(0,0,0) como preto puro) → roteiro manual.
- **Impacto**: potencial falha de leitura da marca na máquina de corte
  dependendo do fluxo de cor da gráfica. **Prioridade: 🟡 Médio** (🟠 se o
  público-alvo imprime via RIP com conversão de perfil).
- **Sugestão**: emitir marcas em DeviceGray 0 ou DeviceCMYK (0,0,0,1).

### 🟡 A5 — Ações de seleção falham mudas (Agrupar/Alinhar/Distribuir/Copiar…)
- **Descrição**: `_group_selected`, `_ungroup_selected`, `_align`,
  `_distribute`, `_duplicate_selected`, `_copy_selected` fazem `return`
  silencioso com seleção insuficiente — sem toast, sem desabilitar o botão.
  Inconsistente com `_rotate_selected` (toast) e `generate()` (aviso).
- **Evidência**: LEITURA DE CÓDIGO — `main_window.py:6858-6958, 7140-7164`.
- **Impacto**: usuário acha que o clique "não pegou". **Prioridade: 🟡**.
- **Sugestão**: toast informativo ("Selecione 2+ peças para alinhar") ou
  habilitar/desabilitar conforme a seleção.

### 🟡 A6 — Cache de recorte nunca é reaproveitado entre sessões e acumula lixo
- **Descrição**: nome do arquivo de cache usa `hash()` builtin de strings —
  salgado por processo (PYTHONHASHSEED nunca fixado): a cada abertura do app
  o nome muda; o cache da sessão anterior nunca é lido nem apagado. Não há
  NENHUMA rotina de limpeza de `%TEMP%\printnest_crops` nem das pastas
  `printnest-faca-*` (pdfium_knife.py:85).
- **Evidência**: LEITURA DE CÓDIGO — `main_window.py:5967, 6000`;
  contraste: `cv2_image_importer.py:305` já usa `hashlib.md5` (determinístico).
- **Impacto**: disco do cliente crescendo para sempre; cache inútil entre
  sessões. **Prioridade: 🟡**.
- **Sugestão**: trocar por `hashlib.md5`/sha1 do (path, sig) e limpar
  arquivos velhos no boot (ou atexit).

### 🟡 A7 — Ícones/miniaturas sem devicePixelRatio (blur provável em 4K/150%+)
- **Descrição**: `faca_icons.py` e `icons.py` desenham QPixmap no tamanho
  lógico (ex. 26×26) sem `setDevicePixelRatio` — em HiDPI o Qt upscala a
  imagem única → ícones borrados.
- **Evidência**: LEITURA DE CÓDIGO (causa raiz confirmada: 0 ocorrências de
  devicePixelRatio nos 2 arquivos). Efeito visual → item 4 do roteiro manual.
- **Prioridade: 🟡**. **Sugestão**: gerar em `size*dpr` + setDevicePixelRatio.

### 🟡 A8 — Rótulo "Offset" em inglês (único do app)
- **Evidência**: LEITURA DE CÓDIGO — `main_window.py:2535`; vizinhos todos em
  português de gráfica ("Sangria", "Folga", "Margem").
- **Prioridade: 🟡**. **Sugestão**: "Offset da faca" → "Afastamento da faca"
  (ou manter "Offset" se for o jargão que o cliente usa — decisão de produto).

### 🟡 A16 — Falha ao gravar config.json durante o salvar não vira aviso
- `save_project()` → `_collect_project()` chama `_save_settings()` FORA do
  try/except de ProjectError (`main_window.py:~2112`) — ConfigError (disco
  cheio/permissão no config) sobe cru. Evidência: TESTE —
  `tests/qa/test_qa_f3_lifecycle.py::test_config_sem_permissao_de_escrita_durante_salvar_projeto`
  (xfail). **Prioridade: 🟡**.

### 🟢 A9 — Baixos / cosméticos / registrados
- Título dos avisos: "Modo Corte" no diálogo × "PrintNest" no resto; e
  `licensing_dialog.py:157` "Ativacao" sem cedilha na tela do cliente
  PAGANTE (`:142-144` "codigo", "ate" idem). LEITURA DE CÓDIGO. 🟢/🟡.
- Espessura do traço (A2/A3) não muda o preview (pen cosmético 1px,
  documentado no código) — operador pode achar que o controle não funciona.
  `main_window.py:6576-6579`. 🟢.
- Menu Organizar mistura itens com e sem ícone na mesma seção
  (`main_window.py:1834-1854` lista curada). 🟢 + roteiro manual.
- `Qt.white` literal em miniaturas de chapa em vez de `theme.SHEET`
  (`main_window.py:7634, 7690`) — sem efeito visual (mesmo valor). 🟢.
- Espaçamentos fora de theme.SPACE_* em HUDs/popups pequenos (6 pontos,
  valores próximos dos tokens) — manutenção, não visual. 🟢.
- `knife_free_pdf` é fail-open documentado: erro no nível do documento
  reintroduz a linha magenta do cliente na impressão (`pdfium_knife.py:40-63`).
  Difícil de disparar; decisão de design registrada. 🟢.
- Zoom sem teto/piso: 2000 zooms seguidos não geram NaN nem travam (TESTE
  verde), mas a escala passa de 1e6× — falta um clamp sensato
  (`main_window.py:~326-329, ~6772`). 🟢.
- Suspeita geométrica NÃO confirmada: padding da página para
  squares/crosses não soma `reg_thickness` (corner_l soma) — meia-espessura
  pode encostar na borda com traço 2,0 mm (`export_print_pdf.py:79-83`).
  Especulativo, requer render real. 🟢/verificar.

### Suspeitas DESCARTADAS com evidência (não são bugs)
- Colisão de atalhos: NENHUMA — inclusive R do Modo Corte × R de Alinhar
  (diálogo é modal via `.exec()`); mnemônicos de menu únicos (QA-09 ok).
- Combos ilustrados: 25/25 chaves dos `*_HINTS` batem com os itens dos 6
  combos (inclusive os 7 tipos de registro) — nenhum ícone/dica vazio.
- Tooltips: as ~57 QActions e os botões do Modo Corte todos têm dica
  (os 3 do diálogo ganham via `_sync()` no __init__).
- Atalhos anunciados em tooltip = atalhos reais (F4/Ctrl+0, R, Ctrl+Z,
  Shift+F5 conferidos).
- Sinais: sem double-connect; `theme_changed` tem disconnect no closeEvent;
  `_on_nest` tem guarda de clique duplo.
- Undo do Modo Corte (E3): grava (folha, índice, item) e desfaz na folha
  certa; Organizar/mudar quantidade/remover peça limpam a pilha — sem
  entradas órfãs. CONFIRMADO também por TESTE (Fase 2B).
- Cópias rasas nos snapshots: seguras — `_faca_manual` nunca é mutado
  in-place; `_piece_rotations` só guarda int; `_result` sempre substituído.
- `project_io.py`: versão futura → erro amigável; campos ausentes →
  default (reg_thickness 0.8); unicode ok (utf-8 + ensure_ascii=False).
- `reg_thickness` fora do range em projeto velho → clamp nativo do spin.
- `contour_ops.py`: os 3 `except Exception` devolvem o contorno original
  (fallback documentado e seguro).
- Ícones Lucide: 28/28 usados existem em assets/icons (7 nomes restantes
  são glifos gerados — não são lookups de arquivo).

---

## FASE 2B — Modo Corte E2E (CONCLUÍDA, 0 bugs)

15 testes novos, todos verdes (FONTE=TESTE):
`tests/qa/test_qa_f2b_fluxo.py` (2), `test_qa_f2b_e3_bordas.py` (8),
`test_qa_f2b_estado.py` (5). Cobrem: fluxo SVG+PDF+Texto→qty→nest→arrasto
por MOUSE real→giro pela TECLA R real→DXF ≡ layouts ≡ cena (com flip Y);
1 DXF por folha batendo folha a folha; clamp fora da chapa e pós-giro;
undo por folha (combo volta sozinho); Organizar limpa o undo; mudar
quantidade/remover peça invalida e BLOQUEIA export desatualizado;
sobreposição manual é permitida por design e sai no DXF (escolha do
operador); clique duplo em Organizar não duplica thread; fechar durante o
cálculo é segurado com aviso; Corel ausente/pasta inválida → aviso amigável;
diálogo reaberto não vaza estado.

## FASE 2A — Janela principal E2E (CONCLUÍDA — FONTE=TESTE)

42 testes novos: **37 verdes, 5 xfail (bugs reais)**, 0 falhas.
`tests/qa/test_qa_f2a_roundtrip.py` (5) · `test_qa_f2a_registro.py` (19) ·
`test_qa_f2a_abas.py` (4) · `test_qa_f2a_buracos.py` (14).
Comando: `.venv/Scripts/python.exe -m pytest tests/qa/test_qa_f2a*.py -q`

Confirmado FUNCIONANDO (destaques): roundtrip completo PDF+PNG+JPG com
quantidades variadas + overrides (giro de arquivo, tipo de faca) + export nos
4 formatos com CONTEÚDO verificado (fitz/ezdxf/pikepdf) + salvar/reabrir —
quantidades e overrides batem 100%; **os 7 tipos de marca de registro batem
em coordenadas reais (mm) entre preview, PDF e DXF** (varrendo margem 0/10/50,
tamanho 2/10, espessura 0,3/0,8/2,0) e os 4 campos persistem no projeto;
fechar aba suja pergunta e respeita Cancelar/Descartar (QMessageBox real
interceptado); clipboard não atravessa aba (por design); alinhar D/T/B/
centros e distribuir vertical corretos; limpar guias limpa cena e estado;
zoom F2/F3 reversível; girar 4×90° = original; Sobre/Licença abrem; nenhum
atalho ambíguo em runtime.

Observação (não bug): reabrir projeto e regerar pode reordenar peças na
mesma fileira (mesmos tamanhos, zero sobreposição) — o motor congelado não
promete determinismo de ordem; expectativa do teste ajustada.

## FASE 3 — Entradas hostis (CONCLUÍDA — FONTE=TESTE)

28 testes: **20 verdes, 8 xfail (bugs)**, 16/16 casos do charter cobertos.
`tests/qa/test_qa_f3_malformed_files.py` (8) · `test_qa_f3_lifecycle.py` (9) ·
`test_qa_f3_stress.py` (7) · `test_qa_f3_ipc.py` (4). ~70 s, estável em 2
execuções.

Confirmado ROBUSTO: MediaBox 0×0; imagem 12000×12000 (~3-4 s, sem
MemoryError); PNG 100% transparente (fallback retângulo); JPEG CMYK+ICC;
arquivo sumido do disco após gerar → export avisa amigável (@_guard_export);
nome com acento+emoji+200 chars+espaço antes da extensão importa/salva/reabre;
UNC fantasma no projeto abre com ⚠ sem travar (neste ambiente — timeout SMB
real vira suspeita, ver abaixo); salvar em pasta sem permissão → aviso;
.printnest truncado e "version": 99 → aviso amigável SEM perder o trabalho da
aba; PDF 300 páginas (~3-4 s); quantidade 999 correta (<20 s); Ctrl+D×50
linear com undo/redo exatos; 100 operações mistas com undo ao fundo e redo ao
topo restaurando estados exatos; zoom 1000 passos sem NaN; segunda instância
com PROCESSOS reais entrega os arquivos à primeira e desiste rápido sem
servidor.

Suspeitas por código registradas (não automatizáveis com segurança):
`Path.exists()` em UNC de host inexistente pode sofrer timeout SMB de vários
segundos em máquina real (aqui resolveu instantâneo);
`forward_to_running()` cria QLocalSocket sem referência viva — funciona no
uso real (processos separados), padrão frágil (`single_instance.py:25-39`).

## FASE 5 — Performance (CONCLUÍDA — FONTE=MEDIÇÃO)

Scripts em `scratchpad/fase5_*.py` + `bench_common.py` (fora do repo).

| Medição | Resultado | Veredicto |
|---|---|---|
| Importar 1/50/200 PDFs | ~2,3 ms/arq (parse) · ~23 ms/arq (UI+thumb) | linear ✅ |
| Gerar 100/1000/5000 peças | 0,19 s / 3,47 s / 19,0 s | dentro do motor congelado ✅ |
| `_draw_preview` 1000 peças | **2,65 s/chamada** | 🔴 ver A10 |
| Snap: 500 peças, 100 moves | ~7 ms/evento, O(n) confirmado | 🟠 ver A11 |
| export_pdf / export_dxf 1000 peças | 0,46 s / **2,98 s** | 🔴 mesma causa A10 |
| Gerar+Novo ×20 (mesma janela) | +1,3% RSS | estável ✅ |
| Modo Corte abrir/fechar ×20 | +0,1% RSS | estável ✅ |

### 🔴 A10 — `merge_touching_rect_cuts` é O(n²): redesenho e export DXF degradam quadrático
- **Descrição**: `app/domain/cut/shared.py:98-125` compara peça-a-peça
  (1000 peças = 499.500 comparações). É chamado a CADA `_draw_preview`
  (66% do tempo: 1,5 s de 2,3 s) e no `_dxf_payload`/`export_dxf` (o grosso
  dos ~7 s do export real da Fase 8). Está FORA do motor de nesting
  congelado — o merge de facas encostadas é pós-processamento.
- **Passos**: gerar 1000+ peças → mover qualquer peça (redesenho ~2,6 s por
  gesto) ou exportar DXF.
- **Evidência**: MEDIÇÃO — `fase5_03_draw_preview.py`, `fase5_03b_profile.py`
  (perfil apontando o loop), `fase5_05_export.py`, `fase8_producao_v2.py`.
- **Impacto**: com chapas grandes o app "rasteja" a cada interação — é o
  irmão direto do QAX-04 (seleção O(n²)) que o charter mandou caçar.
  **Prioridade: 🔴 Crítico** para trabalhos grandes (500+ peças por chapa).
- **Sugestão** (não aplicada): índice espacial (grid hash por célula ~maior
  aresta) para só comparar vizinhos — troca O(n²) por ~O(n).

### 🟠 A11 — `PieceItem._snapped` varre a cena inteira a cada mouse-move
- **Descrição**: `main_window.py:547-565` percorre `scene().items()` por
  evento de arrasto com snap ligado. Medido: 10× peças = 10× tempo (~7 ms
  com 500 peças — ainda dentro do frame de 16 ms; estoura a partir de
  ~1500-2000 peças).
- **Evidência**: MEDIÇÃO — `fase5_04_snap.py`.
- **Prioridade: 🟠** (hoje ok, degrada linear no tamanho da cena a cada
  pixel de arrasto). **Sugestão**: cachear a lista de retângulos-alvo no
  início do gesto (mouse press) em vez de varrer a cena por movimento.

### 🟡 A12 — Resíduo de memória ~12-13 MB por ciclo no dia de produção
- 3 ciclos completos: RSS 532→545→557 MB. Leve e pode estabilizar, mas 3
  ciclos não bastam para afirmar. Evidência: MEDIÇÃO `fase8_producao_v2.py`.
  **Prioridade: 🟡** (acompanhar; num dia de 20+ ciclos seriam ~250 MB).
- Nota de metodologia registrada: medir memória de widget Qt fechado com um
  único processEvents() dá falso "vazamento" (DeferredDelete pendente);
  e `ToastManager.notify()` (toast.py:57, singleShot 3200 ms) prende janela
  fechada por 3,2 s — irrelevante no app real (uma MainWindow só), mas
  derrubou um falso positivo de +350 MB/ciclo na primeira medição.

## FASE 8 — Dia de produção simulado (CONCLUÍDA — FONTE=MEDIÇÃO)

Lote realista: 200 PDFs variados (com/sem faca magenta) + 30 PNG + 20 JPG,
~750 peças, janela única, ciclo completo importar→gerar→faca→exportar
(IMPRESSÃO.pdf + Faca PDF + DXF)→salvar→reabrir→re-exportar, repetido 3×.
- Tempos ESTÁVEIS entre ciclos (±3%) — sem degradação de sessão.
- Nenhuma etapa passou de 20 s. **Gargalo nº 1: Gerar Produção ~11,1 s**
  (motor congelado — só cronometrado, sem julgamento). **Gargalo nº 2 e
  elegível a correção: export_dxf ~7,1 s** (causa = A10).
- Memória: +12-13 MB/ciclo (A12).

---

## FASE 1 — Buracos de cobertura (mapa para a suíte crescer)

Sem teste de integração hoje: Substituir arquivo (replace_selected); zoom
F2/F3/Shift+F2/Shift+F4 + pan Alt+setas + Mão (H); Alinhar
direita/topo/base/centros; Distribuir vertical; Limpar guias; fechar aba com
trabalho sujo; atalho R do Modo Corte (coberto agora pela Fase 2B);
Texto… no nível do diálogo (coberto agora pela Fase 2B); Sobre/Licença
smoke; ambiguidade de atalhos em runtime; girar 4× = original; segunda
instância lado cliente. Os itens cobertos pelas fases 2A/2B/3 desta missão
ficam em tests/qa/ como cobertura nova.

---

## NOTAS 0–10

| Dimensão | Nota | Justificativa (uma frase) |
|---|---|---|
| Estabilidade | 7,0 | 723 verdes + 16/16 casos hostis quase todos limpos, mas o caminho síncrono de gerar estoura cru com PDF ruim (A14). |
| UX | 6,5 | Tooltips/combos ilustrados/guias exemplares, porém quatro perdas SILENCIOSAS de intenção do usuário (A0, A1, A1b, A2) e ações mudas (A5). |
| UI | 8,0 | Tema/tokens consistentes, zero colisão de atalho, hardcodes legítimos — resta o risco 4K sem devicePixelRatio (A7, confirmar no roteiro). |
| Performance | 6,5 | Escala realista (250 arquivos/750 peças) roda estável e <20 s por etapa, mas o O(n²) do merge (A10) derruba redesenho/export em chapas de 1000+ peças. |
| Consistência | 8,5 | As varreduras de cores/ícones/hints/atalhos bateram ~100%; sobram acentos na tela de licença e um "Offset". |
| Escalabilidade | 6,0 | Importação linear e memória estável, porém A10 (quadrático) e A11 (snap O(n)) põem teto prático na cena; +12 MB/ciclo a acompanhar (A12). |
| Confiabilidade | 5,5 | A classe de bugs "o app fez diferente do que o operador mandou e não avisou" (A0, A1, A1b, A2, A13) é exatamente a que quebra confiança de gráfica. |
| Prontidão para lançamento | 5,0 | O produto encanta na demo e trai no dia seguinte: salvar não salva o arranjo manual e girar+duplicar multiplica material. |

## VEREDITO

**NÃO APROVADO PARA PRODUÇÃO.**

O motor, a suíte e o acabamento visual estão maduros — mas há quatro 🔴 e
uma classe inteira de "perda silenciosa" que uma gráfica pagante encontraria
na primeira semana. Lista MÍNIMA que destrava o lançamento:

1. **A0** — persistir o arranjo manual/giro por peça no `.printnest` (ou, no
   mínimo, avisar ao salvar que o arranjo manual será perdido).
2. **A13** — girar não pode re-selecionar todas as cópias (duplicação
   exponencial de material).
3. **A14** — try/except no ramo `blocking` do `generate()` (PDF ruim de
   cliente é rotina, não exceção).
4. **A1b** — Substituir arquivo tem de reimportar (hoje corta a arte antiga
   com o nome novo).
5. **A15** — `.printnest` binário corrompido precisa do mesmo aviso amigável
   que o truncado já tem (1 linha no except).
6. **A1** — falha no bake do recorte precisa avisar (e o toast de sucesso
   sair só depois do bake real).

Recomendados antes de vender para gráficas grandes (não bloqueiam MVP):
**A10** (índice espacial no merge — hoje 1000 peças = 2,6 s por redesenho e
7 s de DXF), **A2** (colar sem perder peças), **A3** (moldura amigável na
última linha de defesa), **A4** (marcas em K puro — decidir com base no RIP
dos clientes-alvo).

O que já está PRONTO e provado por teste: Modo Corte/E3 inteiro (15/15),
marcas A2/A3 idênticas nos 3 lugares com persistência completa, abas com
confirmação de descarte, undo/redo exatos em 100 operações mistas, robustez
contra 16 tipos de entrada hostil, instância única com processos reais, e
performance estável no dia de produção simulado de 250 arquivos × 3 ciclos.

### Saldo de testes desta missão
85 testes novos em `tests/qa/` (42 F2A + 15 F2B + 28 F3): **72 verdes de
cobertura nova + 13 xfail** (verificado numa rodada única consolidada de
`pytest tests/qa -q`: 72 `.` + 13 `x`, 0 falhas) documentando os bugs em aberto (somem da lista
de xfail conforme forem corrigidos — cada um vira o teste de regressão da
própria correção). Nada foi commitado; a decisão é do Philipe.

---

## ROTEIRO MANUAL para o Philipe (o que só olho humano valida)

1. Redimensione a janela ao MÍNIMO: biblioteca, cards e barra Faca continuam
   usáveis? Algo corta/sobrepõe?
2. Produção grande (50+ peças): maximizar → restaurar → minimizar →
   restaurar. Canvas re-enquadra? Alguma chapa some?
3. FullHD 1920×1080: a ribbon inteira cabe? "Exportar" caiu no overflow (»)?
4. 4K: ícones da ribbon e miniaturas dos combos nítidos ou borrados?
   (Suspeita A7 prevê blur — confirme.)
5. Escala Windows 100/125/150/200% (reiniciando o app em cada): texto cortado
   (atenção "Marcas: espessura do traço")? miniaturas 26×26 nítidas? réguas
   legíveis?
6. Dois monitores com DPI diferente: arrastar a janela entre eles; abrir o
   Modo Corte no 2º monitor.
7. Tema claro→escuro AO VIVO com produção na tela: canvas, réguas, cards e
   TODAS as miniaturas redesenham? (combo Tipo de registro em especial).
8. Tema "Automático": mudar o modo do Windows com o app aberto — acompanha?
9. Personalizar Interface: mudar acento, fechar, reabrir — persiste?
10. Modo Corte maximizado e pequeno: preview × lista dividem bem? tooltip
    longo do preview cabe na tela?
11. Arrastar peça rente às outras em zoom máximo: seleção legível? peça
    "treme" ao soltar?
12. Durante Organizar (10 s+): dicas rotativas trocam suaves? janela responde?
13. Para CADA tipo de registro (Círculos, L Mimaki, Círculos+L, Quadrados,
    Cruzes, L de canto): olhe os 4 cantos no preview (abertura do L para
    fora?); exporte o PDF e abra no Corel/Acrobat com zoom: preto CHAPADO?
    posição/tamanho = preview? **Verifique no separador de cores: a marca
    deve ser K puro — hoje sai RGB (achado A4).**
14. Espessura 0,3/0,8/2,0 nas Cruzes e L de canto: diferença visível e
    proporcional no PDF (no preview NÃO muda — achado A9/espessura)?
15. Imprima UMA folha real com Quadrados e teste a leitura no plotter
    (Summa/OPOS) — nenhum script cobre isso.
16. Arraste contínuo com 200+ peças e snap ligado: acompanha o mouse?
17. Zoom com a roda em cena grande: fluido?
18. Duplo clique rápido em vários pontos da biblioteca: janela duplicada?
19. Abra dois PrintNest: o segundo foca o primeiro?
20. Arraste 30 arquivos do Explorer de uma vez: todos entram? congela?
21. Abra o menu Organizar e repare: itens com e sem ícone misturados
    incomodam? (achado A9/menu)
22. Diálogo de licença: leia os textos — "Ativacao"/"codigo" sem acento
    (achado A9/licença) na tela do cliente pagante.
