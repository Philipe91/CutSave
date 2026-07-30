# AUDITORIA DE PRÉ-LANÇAMENTO — 30/07/2026

Auditoria completa da jornada do cliente (instalação → primeira execução → fluxo de
trabalho → exportação), feita por 6 varreduras independentes e paralelas do código:
**responsividade/DPI**, **instalação/onboarding**, **UX do fluxo**, **performance/
estabilidade**, **UI/acessibilidade** e **textos/documentação**. Nenhum arquivo foi
modificado. Todos os achados foram confirmados por leitura direta do código — nada é
suposição. Achados apontados por mais de uma varredura estão marcados com (×2)/(×3).

**Contexto**: lançamento comercial na semana de 03/08. A regra da auditoria foi
"refinar, não reinventar": nenhuma sugestão muda regra de negócio ou arquitetura.

---

## VEREDITO GERAL

A fundação é **sólida e acima da média**: design system real com tokens e zero cor
chumbada fora do tema; undo/redo robusto no arranjo; estados vazios que ensinam o
próximo passo; tooltips que explicam consequência; proteção contra perda de trabalho
no fluxo principal; nesting do Modo Corte em thread com espera bem comunicada;
mensagens do `messages.py` exemplares (dizem o quê + o que fazer); onboarding com
tour + tutoriais mão-na-massa raros no mercado nacional; instalador pt-BR que
preserva a licença na desinstalação; startup sem rede síncrona e com `faulthandler`.

Os problemas encontrados são **numerosos porém cirúrgicos** — quase todos com
correção pequena e localizada. Os 10 críticos abaixo cabem, somados, em 1–2 dias de
trabalho.

---

## 🔴 CRÍTICOS (impedem o lançamento)

### C1. EULA exibida no instalador com placeholders de rascunho (×2)
- **Local**: `installer/EULA.txt:5-6, 46, 91-94` (é o `LicenseFile` de `installer/printnest.iss:32`); `printnest.iss:18-19` tem o mesmo pendente no `MyAppPublisher`.
- **Problema**: todo comprador verá, na tela de licença do instalador, `[RAZAO SOCIAL / NOME DO VENDEDOR]`, `[NUMERO]`, `[CIDADE/UF]`, `[DEFINIR: atualizacoes incluidas por X meses/anos ou vitalicias]`, `Contato: [SUPORTE]`. O documento inteiro está sem acentos e a cláusula 8 tem erro ("violacao das clausulas 2").
- **Motivo**: texto ficou em rascunho.
- **Impacto**: imagem de produto inacabado na PRIMEIRA tela; contrato juridicamente incompleto (não identifica vendedor nem foro).
- **Correção**: preencher os 5 placeholders, acentuar, corrigir concordância. Alinhar `MyAppPublisher`.
- **Risco**: nenhum (texto). **Validar**: recompilar instalador e passar pela tela de licença.

### C2. pdfium usado FORA do `PDFIUM_LOCK` em 2 pontos — provável causa do crash 0xc0000374
- **Local**: `app/presentation/main_window.py:6827-6830` (`_crop_pages_dialog`) e `:6945-6951` (`_pdf_page_count`, usado por "Páginas do PDF…" e `_refresh_library_metadata`).
- **Problema**: ambos criam `pdfium.PdfDocument(path)` sem o lock. Durante uma geração, o `ProductionWorker` usa pdfium em outra thread, e `_set_busy` só desabilita Gerar/Adicionar (`:7420-7422`) — o usuário PODE abrir esses diálogos no meio. Dois threads dentro do pdfium = corrupção de heap. O próprio projeto já viveu isso (comentário em `pdfium_boxes.py:22-27`, access violation de 16/07 que motivou o lock). Assinatura 100% compatível com o 0xc0000374 "sem repro".
- **Impacto**: crash aleatório e irreproduzível na máquina do cliente.
- **Correção**: `with PDFIUM_LOCK:` nos dois trechos (~4 linhas cada, zero mudança de comportamento).
- **Risco**: praticamente nulo (RLock; pior caso espera o worker terminar a página corrente).
- **Validar**: gerar produção de PDF de 60 páginas e, durante a barra de progresso, abrir "Páginas do PDF…" repetidamente; nada pode tombar (crash.log limpo).

### C3. Fechar a janela durante geração longa: até 10s congelado e possível abort (×2)
- **Local**: `main_window.py:7437-7440` (`closeEvent`: `thread.quit(); thread.wait(10000)`); o loop de `_render_page_images` (`:1066-1077`) não tem flag de cancelamento.
- **Problema**: `quit()` não interrompe o worker; gerações reais de 19–29s são conhecidas. Fechar nesse intervalo = janela "não respondendo" por 10s e, se o worker não acabou, o QThread vivo é destruído → Qt aborta o processo ("fechou sozinho"). Soma-se o `thread.wait(8000)` do update check (`update_check.py:92`) no pior caso.
- **Correção**: (a) flag de cancelamento checada a cada página em `_render_page_images`, setada no `closeEvent` antes do `wait`; (b) enquanto isso, aviso "Terminando a geração…" ou ignorar o close com toast, como o Modo Corte já faz (`cut_mode_dialog.py:1146`).
- **Risco**: baixo — cancelamento só encurta o loop.
- **Validar**: importar PDF de 60 páginas, fechar no meio da barra, repetir 10×; sem abort e sem entrada nova no crash.log.

### C4. Modo Corte não cabe em notebook 1366×768 @125% — botões fora da tela
- **Local**: `cut_mode_dialog.py:387` (`setMinimumSize(900, 600)`), conteúdo sem `QScrollArea` (`_build_left`/`_build_right`, 410-538).
- **Problema**: altura útil em 1366×768 @125% ≈ 545px; o mínimo rígido de 600px estoura ~55-90px. A linha Organizar / Enviar p/ Corel / Exportar DXF / Fechar fica FORA da tela — e este é o diálogo standalone que a macro do CorelDRAW abre (`--modo-corte`, `__main__.py:183-195`), sem MainWindow por trás: o operador fica sem saída visível.
- **Correção**: baixar o mínimo para ~860×520 e envolver a coluna esquerda (ou `_build_params`) numa `QScrollArea` (mesmo padrão do `_painel_rolavel`). Alternativa mínima: `setMinimumSize(900, 540)` + prévia com `setMaximumHeight` em vez de `setFixedHeight`.
- **Risco**: baixo (só geometria). **Validar**: `QT_SCALE_FACTOR=1.25` em janela 1366×768; os 4 botões do rodapé visíveis; teste headless do Modo Corte verde.

### C5. Nome do produto: cliente compra "PrintNest Pro" e instala "PrintNest Premium" (×3)
- **Local**: *Premium*: `main_window.py:1824` (título), `:2650-2661` (Sobre), `installer/printnest.iss:15`, `VERSAO.txt`. *Pro*: site de vendas (R$ 397), `licensing_dialog.py:159`, `docs/cliente/LEIA-ME.txt:2`, logo do painel (`PRINTNEST PRO`), `CHANGELOG.md:3`.
- **Impacto**: "comprei o produto certo?" — dúvida real no recibo, na ativação por e-mail e em todo chamado de suporte.
- **Correção**: decidir UM nome (o site vende "Pro") e alinhar título da janela, Sobre, instalador, VERSAO.txt, EULA. Troca de strings.
- **Risco**: nenhum. **Validar**: `grep -r "Premium\|Pro"` nos textos visíveis.

### C6. Canal de atualização nasce morto: URL do manifesto vazia (×2)
- **Local**: `app/infrastructure/updates.py:42` (`URL_MANIFESTO_PADRAO = ""` — o comentário nas linhas 32-41 diz "Preencha AQUI antes de rodar o build"); consumida em `main_window.py:2364-2382`.
- **Problema**: (a) nenhum cliente da 1.0.0 saberá de uma 1.0.1 — grave numa semana de lançamento em que hotfix é provável; (b) o menu **Ajuda → Procurar atualizações** mostra ao leigo *"Defina 'update_url' na configuração"* (`update_check.py:66-71`) — mensagem de desenvolvedor.
- **Correção**: publicar um `manifesto.json` estático em qualquer hosting e preencher a constante antes do build. Se decidir lançar sem, esconder o item de menu quando `url_efetiva()` vier vazia.
- **Risco**: baixo (a infra já engole erros de rede). **Validar**: check manual com manifesto de versão maior, igual, e com servidor fora.

### C7. Trabalho não salvo em aba inativa se perde SEM aviso (`_dirty` é global, não por aba)
- **Local**: `main_window.py:2843-2844` (`_mark_dirty`), `:4050-4075` (`_snapshot_session` não fotografa `_dirty`), `:2944` (salvar zera o global), `:7429` (`closeEvent` consulta o global).
- **Problema**: edita a aba A → troca para a B → Ctrl+S salva a B (`_dirty=False` global) → fecha o app: `_confirm_discard` não pergunta nada e o trabalho da aba A morre em silêncio. Exatamente o fluxo multi-projeto que a barra de abas convida a usar.
- **Correção**: incluir `"dirty"` no snapshot/restore de sessão e, no `closeEvent`/`_confirm_discard`, checar `any(sessão dirty)`.
- **Risco**: baixo; cuidar para `_apply_session` não re-sujar via `_mark_dirty` colateral.
- **Validar**: teste pytest — editar aba 1, criar aba 2, salvar, fechar → confirmação deve aparecer.

### C8. Fechar o Modo Corte descarta minutos de nesting + retoques manuais sem confirmação
- **Local**: `cut_mode_dialog.py:1142-1155` (`reject`/`closeEvent` só seguram a thread), `:535` (botão "Fechar" colado em "Exportar DXF"); o diálogo é recriado do zero a cada abertura (`main_window.py:9021-9028`).
- **Problema**: um Esc acidental joga fora o cálculo mais caro do programa, sem volta.
- **Correção**: em `reject`/`closeEvent`, se há `self._layouts` e nada foi exportado/enviado na sessão, perguntar "Fechar descarta o arranjo organizado. Fechar mesmo assim?" (botões custom pt-BR; manter a guarda de testes headless).
- **Risco**: baixo. **Validar**: organizar → Esc → pergunta; exportar DXF → fechar → não pergunta.

### C9. Tooltip ilegível em TODOS os temas escuros (branco sobre branco)
- **Local**: `app/presentation/theme.py:200-207` — `QToolTip { background: {TEXT}; color: #ffffff; }`. Nos temas Escuro/Midnight/Carbon, `TEXT = #ffffff` → contraste 1,0:1.
- **Impacto**: o app tem 104 tooltips (e são bons!); no dark mode — recurso vendido — todos viram balões vazios.
- **Correção**: uma linha — `color: {BG}` (ou tokens `TOOLTIP_BG/TOOLTIP_TEXT` nas paletas).
- **Risco**: nenhum. **Validar**: tema Escuro → hover em qualquer botão da ribbon.

### C10. Texto branco do botão de destaque reprova contraste nos presets que o app oferece
- **Local**: `themes/palettes.py:80-90` (`accent_set` não recalcula `ICON_ON_ACCENT`) + `theme.py:287-294` (`QPushButton[accent]` com `#ffffff` fixo) e `theme.py:453-459` (cabeçalho de card).
- **Problema** (razões WCAG calculadas): Verde `#22c55e` = 2,28; Turquesa = 2,49; Graphite = 2,52; Laranja = 2,80; Carbon = 2,80; Midnight = 3,20; Escuro = 3,65 — tudo abaixo de 4,5:1, atingindo o botão GERAR FACA e os cabeçalhos de todos os cards. O teste de contraste existente (`tests/presentation/test_themes.py:22`) não cobre `ICON_ON_ACCENT × ACCENT`.
- **Correção**: em `accent_set()`, derivar `ICON_ON_ACCENT` por luminância (branco se `contrast(#fff, base) >= 4.5`, senão `#111827`) — a função `contrast()` já existe no arquivo — e trocar os `#ffffff` do QSS por `{ICON_ON_ACCENT}`.
- **Risco**: baixo (presets claros passam a ter texto escuro no botão — comportamento correto).
- **Validar**: preset Emerald/Graphite → botão Gerar Faca legível; estender o teste de contraste para todos os PRESETS.

---

## 🟠 ALTO IMPACTO

### Responsividade / DPI

**H1. Toda a iconografia rasterizada sem devicePixelRatio — o app inteiro fica borrado em 125–200%**
- **Local**: `app/presentation/icons.py:28-39` (`_pixmap` com DPR=1); `faca_icons.py:91, 219, 439-459, 577, 669`; `widgets/collapse_strip.py:62`; `panels/status_bar.py:30,40`; `widgets/toast.py:39`.
- É o A7 do QA de 22/07, ainda pendente — e a **provável causa do "desconforto" relatado nos testes em outros PCs** (150% é o padrão do Windows em notebooks 14" FHD). Ribbon, combos ilustrados, status bar, toasts e a faixa de passos do canvas vazio saem upscalados ("fora de foco").
- **Correção**: em `icons._pixmap` e nas fábricas de `faca_icons`: obter o `devicePixelRatio()`, criar o pixmap em `size*dpr`, pintar com `painter.scale(dpr, dpr)`, `setDevicePixelRatio(dpr)` e incluir o dpr na chave do cache. 2 arquivos; call sites não mudam. **Maior ganho visual por esforço de toda a auditoria.**
- **Validar**: `QT_SCALE_FACTOR=1.5` e comparar nitidez; suíte verde.

**H2. Diálogo de Ativação pode estourar a tela em 125% — e é bloqueante no startup**
- **Local**: `licensing_dialog.py:35-141` (~13 linhas empilhadas, chave com `setFixedHeight(84)`, sem rolagem; altura mínima efetiva ≈ 620-650px vs ~545px úteis em 1366×768 @125%).
- Botões "Ativar"/"Sair" podem ficar abaixo da borda **na primeira execução do produto comprado** — o pior momento possível.
- **Correção**: reduzir a chave para ~64px, espaçamento `SPACE_SM`, e/ou `QScrollArea` no miolo.
- **Validar**: `QT_SCALE_FACTOR=1.25` + 1366×768, fluxo de startup do .exe.

### Instalação / licenciamento / robustez

**H3. "Licença ativada" sem ter gravado a licença no disco**
- **Local**: `app/licensing/manager.py:57-61` — escrita do `license.key` dentro de `contextlib.suppress(OSError)`, sucesso retornado incondicionalmente.
- Se a escrita em `%APPDATA%\PrintNest` falhar (antivírus, perfil restrito, disco cheio): cliente vê sucesso, usa a sessão, e na próxima abertura cai de novo na ativação — loop sem saída para o público leigo.
- **Correção**: falhou a escrita → `(False, "não consegui salvar a licença em %APPDATA%\PrintNest — verifique antivírus/permissões")`.
- **Validar**: teste com `license_file` em pasta somente-leitura.

**H4. Fingerprint inclui o MAC — licença pode "quebrar" sem o cliente trocar de PC**
- **Local**: `app/licensing/fingerprint.py:37-38` (`uuid.getnode()`).
- Adaptador USB, dock, driver ou VM mudam o MAC → `machine_id` muda → "Esta licença é de outro computador". **Decisão a tomar ANTES de emitir as primeiras chaves** — depois do lançamento não dá mais para mudar sem invalidar licenças.
- **Correção**: remover o MAC da fonte (o `MachineGuid` já é estável e único) ou preparar reemissão rápida no suporte.

**H5. Sem handler global de exceções Python — erro em produção vira silêncio**
- **Local**: `app/presentation/__main__.py` (zero ocorrências de `excepthook` no projeto). Com `console=False` (`PrintNest.spec:93`), exceção não tratada num slot Qt não aparece em lugar nenhum: a ação simplesmente "não acontece", sem log no `printnest.log`.
- **Correção**: `sys.excepthook` no início de `main()` — loga traceback + `QMessageBox` "Ocorreu um erro inesperado. Detalhes em %APPDATA%\PrintNest\logs" (~15 linhas). Não engolir `KeyboardInterrupt`; conferir suíte.

**H6. Sem assinatura digital: SmartScreen no download**
- **Local**: `build.bat` (sem `signtool`), `printnest.iss` (sem `SignTool=`).
- O aviso azul aparece ANTES do LEIA-ME que o explica (que está dentro do pacote).
- **Correção mínima**: repetir a instrução "Mais informações → Executar assim mesmo" na página de download/e-mail de entrega. Ideal: certificado de code signing.

**H7. Instalador não detecta o app aberto**
- **Local**: `printnest.iss` sem `AppMutex`; a instância única é `QLocalServer`, invisível ao Inno.
- Instalar a 1.0.1 com o app aberto = erro de arquivo em uso.
- **Correção**: `CreateMutex` via `ctypes` no startup (3 linhas) + `AppMutex=` no .iss.

### Performance / fluxo

**H8. Drop incremental pendente — confirmado onde e quanto custa**
- **Local**: `main_window.py:8558-8624` (`_add_file_to_production` síncrono) e `:9248-9256` (`open_external_files` → `generate(blocking=True)`, sem nem wait cursor).
- O caminho em thread só cobre drop com produção VAZIA. Soltar PDF grande numa produção montada, ou **receber arquivo da macro do Corel com o app aberto** (vitrine do produto), congela a UI pelos mesmos ~19s já corrigidos no outro caminho.
- **Correção p/ semana**: mínimo `_wait_cursor()` + toast "importando…"; ideal reutilizar o `ProductionWorker` com `paths=[path]` e fazer só a parte leve no `finished`.

**H9. "Páginas do PDF…" renderiza todas as miniaturas sincronamente, sem feedback**
- **Local**: `main_window.py:6982-6995` — `render_png` por página (pikepdf reparseia por página, `pdfium_knife.py:76-109`) antes de o diálogo aparecer.
- **Correção**: mostrar o diálogo com placeholders e preencher em lotes via `QTimer.singleShot(0, …)`; ou 1 linha de `_wait_cursor()`.

**H10. "Enviar p/ Corel": COM síncrono, sem timeout, sem feedback**
- **Local**: `app/infrastructure/corel_bridge.py:34-74` chamado na thread da UI (`cut_mode_dialog.py:1110-1123`).
- Corel ocupado/modal aberto → PrintNest inteiro parece travado; a percepção é "o PrintNest quebrou".
- **Correção**: mover para QThread (o SVG já está em disco; lembrar `pythoncom.CoInitialize()` no worker) com aviso "Enviando ao CorelDRAW…". Testar na máquina com Corel real.

**H11. Exportações inteiras na thread da UI (imagem em DPI alto é o pior caso)**
- **Local**: `main_window.py:9281-9285` (PDF), `:9328-9332` (imagem), `:9552-9612` (faca), `:9434+` (DXF); `pikepdf_print_exporter.py:97-143`.
- Wait cursor existe, mas exportar 5 chapas a 600 DPI = dezenas de segundos com "Não respondendo". Mesmo padrão em "Gerar Faca" por contorno (`main_window.py:6439-6481`).
- **Correção**: começar pela exportação de imagem: worker + progresso por chapa (o loop já é por página; exportadores não tocam widgets).

**H12. Renesting completo a cada clique/tecla no campo de quantidade, sem espera**
- **Local**: `main_window.py:6683` e `:4098` (`valueChanged` → `_relayout` síncrono, sem wait cursor). Digitar "150" roda o nesting em 1, 15 e 150.
- **Correção**: debounce (QTimer ~250ms) + `_wait_cursor()` no relayout de quantidade. Conferir testes que dependem do relayout imediato.

**H13. Busy-state incompleto + barra de progresso que nunca zera (×2)**
- **Local**: `main_window.py:4270-4281` (barra 4px), `:7458-7465` (`_on_progress`/`_on_finished` sem reset), `:7420-7422` (`_set_busy` só desabilita Gerar/Adicionar), `:1101-1113` (worker emite dois ciclos de progresso — a barra "enche duas vezes").
- Durante a geração, Exportar continua habilitado (exporta o resultado ANTIGO) e ajustes disparam `_relayout` sobre estado velho; ao terminar, a barra fica cheia para sempre.
- **Correção**: total único (import N + render M), `reset()`+esconder no finished/failed, e estender `_set_busy` a exportações/"Colocar na chapa"/diálogos de páginas (que também compõem com C2).

### UX / feedback

**H14. Desfazer/Refazer sempre parecem habilitados — clique mudo com pilha vazia**
- **Local**: `main_window.py:1870-1873`; zero uso de `canUndoChanged`/`createUndoAction`.
- **Correção**: conectar `canUndoChanged`/`canRedoChanged` → `setEnabled`; bônus: `undoTextChanged` no tooltip ("Desfazer: girar peça").

**H15. "Procurar atualizações" offline responde "Você já está na versão mais recente" (×2)**
- **Local**: `update_check.py:44-49, 94-102` — erro de rede e "em dia" caem no mesmo `None`.
- **Correção**: terceiro estado (sentinela de erro) → "Não consegui verificar agora — confira sua internet". Manter o check automático silencioso.

**H16. Exceções cruas em inglês nos caminhos de erro mais prováveis (×2)**
- **Local**: `main_window.py:1499, 2913, 2939, 7474, 7645`; `cut_mode_dialog.py:773, 788, 1163`.
- PDF corrompido (mensagem do pypdfium em inglês), `[WinError 5] Access is denied`, erro COM críptico do Corel — o operador lê e conclui "quebrou".
- **Correção**: interceptar 3-4 famílias antes do genérico (PermissionError/OSError → "feche o arquivo se estiver aberto e confira a pasta"; import de PDF → "o PDF parece danificado — reexporte do Corel"; COM → "abra o CorelDRAW e tente de novo") mantendo o detalhe técnico embaixo.

**H17. "Remover da biblioteca": destrutivo sem confirmação e com undo inconsistente**
- **Local**: `main_window.py:6757-6782` — remove o arquivo e todas as peças da chapa; Ctrl+Z restaura o arranjo mas NÃO a linha da biblioteca (estado dessincronizado); remover o último arquivo zera a produção fora do undo. Remoção 100% muda.
- **Correção**: confirmar apenas quando o arquivo tem peças na produção ("Remover NOME também tira N peça(s) da chapa?"); no mínimo, toast com o nome do removido.

**H18. Mensagens apontam para "Gerar Produção", que não existe como botão em lugar nenhum**
- **Local**: ação só no menu Ferramentas + F5 (`main_window.py:1860, 2074`); mas `:7455, 8938, 9223` mandam o usuário "Gerar a produção primeiro" — enquanto a ribbon e o guia do canvas ensinam "Colocar na chapa".
- **Correção**: trocar o texto das mensagens para o botão que o usuário VÊ: "Coloque os arquivos na chapa primeiro (botão 'Colocar na chapa' ou F5)".

**H19. Botões padrão do Qt em inglês — Yes/No num diálogo de descarte de trabalho (×2)**
- **Local**: nenhum `QTranslator` no projeto. Afeta: "Fechar aba … Fechar e descartar?" (`main_window.py:4188` → **Yes/No**), todos os `QInputDialog` (`:8701, 8765-8775, 9308, 9359` → **OK/Cancel**), `QDialogButtonBox` do recorte/páginas (`:6905, 7022`), diálogo Texto (`cut_mode_dialog.py:1302`), desativar licença (`licensing_dialog.py:245-251` → Yes/No), QColorDialog inteiro em inglês (`themes/settings_dialog.py:151,158`).
- **Correção**: carregar `qtbase_pt_BR.qm` no `__main__.py` (2 linhas + empacotar o .qm), e/ou botões custom como `_confirm_discard` já faz (`:2864-2866` — a referência correta está no próprio código).

### UI / acessibilidade

**H20. Foco de teclado invisível fora dos campos de texto**
- **Local**: único `:focus` do QSS em `theme.py:223` (spins/combos/lineedit); `theme.py:348` (`QTableWidget { outline: none; }`); nada para QPushButton/QToolButton/QCheckBox/QRadioButton.
- **Correção**: `:focus { border-color: {ACCENT}; }` para botões/checks/radios; remover `outline:none` da tabela ou estilizar `::item:focus`. Validar navegando por Tab no fluxo Adicionar → Gerar → Exportar.

**H21. Texto-guia do primeiro uso na cor mais fraca da paleta (2,54:1)**
- **Local**: token `TEXT_MUTED #9ca3af` (`theme.py:67`) usado no estado vazio do canvas (`main_window.py:300`), hints, títulos de grupo da ribbon (`theme.py:473, 491, 495`).
- **Correção cirúrgica**: estado vazio e hints informativos → `TEXT_SECONDARY` (4,83:1); MUTED só para decorativo/placeholder.

### Textos / pacote

**H22. ~30 strings visíveis sem acento** — lista completa por linha no relatório do auditor de textos; principais grupos: menu Exportar ("PDF de impressao", `main_window.py:1949-1950, 1328, 9266, 9287`), menu Organizar ("Girar 90 a esquerda", "anti-horario", `:1874-1877` — o menu de contexto `:8228` já está correto), tooltips de painel (`:5320-5335`), títulos "Ativacao" (`licensing_dialog.py:203, 239`). Passada única de substituições, sem risco de layout.

**H23. Tooltips prometem "(mm)" mas os campos exibem cm por padrão**
- **Local**: `main_window.py:5318-5335, 4645-4646` vs `units.py:20` (`_current = CM`).
- Leigo digita 300 achando que é mm num campo em cm.
- **Correção**: remover a unidade do tooltip ou atualizá-lo no `refresh_unit()`. (Nos `QInputDialog` fixos em mm, `:6848, 8772`, manter.)

**H24. Pacote do cliente com referências quebradas/desatualizadas (×2)**
- `docs/cliente/LEIA-ME.txt:5` "Obrigado por **testar**" (tom de beta num produto vendido); `:46` aponta `PRINTNEST-MENTOR-IA.md`, que **não entra no pacote** (`build.bat:26-51`) — o correto é o "Tutor IA - PrintNest.pdf".
- `corel/instalar_plugin_corel.bat` ensina a arrastar `PrintNest.EnviarParaPrintNest`; o guia ilustrado recomenda `PrintNest.PrintNestMenu`. Alinhar o .bat.
- `corel/GUIA-CLIENTE.md:12` + 7 tags de imagem referenciam pasta `imagens/` que não é distribuída (vira `.txt` com links quebrados).
- `PrintNest_Build/README.txt` lista registros "Nenhum / Bolinhas / Mimaki" — o combo real é outro (`main_window.py:5701-5707`).
- `VERSAO.txt` mistura "1.0.0 (primeira versao comercial)" com "Novidades da V1.3" e afirma "interface acentuada" num arquivo sem acentos.
- `PRINTNEST-MENTOR-IA.md:27-28` nega o recurso de atualização que existe (Ajuda → Procurar atualizações).
- **Correção**: revisão única do pacote; **validar** gerando `PrintNest_Build\` e conferindo cada nome citado contra os arquivos presentes.

**H25. Diálogo de Ativação: passos numerados 1-2-3-3 (×2)**
- **Local**: `licensing_dialog.py:81` e `:121` — o segundo "3." deveria ser "4.". A primeira tela que todo comprador vê. Troca de 1 caractere.

---

## 🟡 MÉDIO IMPACTO

**M1. Centro de Exportação: mínimo real (~560-600px) maior que o declarado (480)** — `main_window.py:1230` vs coluna direita sem rolagem (`:1292-1361`). Estoura por pouco em 1366×768 @125%. Correção: `QScrollArea` na coluna direita ou preview mínimo 160 + stretch.

**M2. Biblioteca: mínimo interno (260) > teto dinâmico (220) → scroll horizontal permanente em janela <~1240px** — `main_window.py:5459` vs `:2550`. Correção: alinhar os números (piso do teto = 260 ou mínimo = 218).

**M3. Logo da biblioteca e splash borradas em high-DPI** — `main_window.py:2597` (`scaledToWidth(200)` sem DPR) e `__main__.py:95-98`. Correção: escalar por `devicePixelRatioF()` + `setDevicePixelRatio`.

**M4. Fontes de 10-11px abaixo do piso de 12px do próprio design system (×2)** — `main_window.py:1695` (#stCap 10px), `:5570` (#heroCap 10px, com contraste 3,60:1 no escuro), `:6020` (sub-abas Produção/Acabamento/Registro 11px — navegação primária). Correção: subir para `FONT_CAPTION` (12); conferir reflow em 1366×768. Validação: `rg "font-size:1[01]px" app/` vazio.

**M5. Fechar aba não-ativa: pergunta mesmo vazia, sem opção "Salvar"** — `main_window.py:4176-4193`; o critério `is not None` é verdadeiro para aba recém-criada. Correção: perguntar só se `s["paths"] or s["result"]`; mesmos 3 botões do `_confirm_discard`.

**M6. Toast de ERRO some em 3,2s como o de sucesso (×2)** — `widgets/toast.py:23`; "Falha ao importar X" evapora antes de ser lida. Correção: ERROR com ~8s ou exigir clique; importação com falha poderia usar a faixa `Alert` persistente.

**M7. Drop de .cdr/.svg recusado sem explicação** — `main_window.py:245-256` (filtro no dragEnter). O público usa CorelDraw! Correção: aceitar o drop e responder ".cdr não é suportado — exporte como PDF no Corel (Ctrl+E)" / ".svg é usado no Modo Corte". Sem mudar o que é suportado.

**M8. Girar sem seleção gira o documento inteiro, sem aviso e contra o tooltip** — `main_window.py:8930-8979`; tooltip `:1874-1877` promete "arquivo selecionado". Correção: toast no ramo global + tooltip "Sem seleção, gira o documento inteiro".

**M9. Alinhar/Distribuir/Girar: no-ops silenciosos com seleção insuficiente** — `main_window.py:8359-8362, 8391-8394`; `cut_mode_dialog.py:963-971`. Correção: toast "Selecione 2+ peças para alinhar" etc.

**M10. "Repetir em grade": três QInputDialog encadeados, sem prévia** — `main_window.py:8761-8776` — enquanto a aba Transformar faz o mesmo COM prévia fantasma (`:4800`). Correção: diálogo único ou apontar para a aba Transformar.

**M11. Padrões trocados entre telas: sucesso é toast na janela principal e MODAL no Modo Corte** — `cut_mode_dialog.py:1117-1121, 1132-1136`; títulos de caixa variam ("PrintNest"/"Modo Corte"/"Ativacao"). Correção: usar a label `_status` do próprio diálogo para sucesso; título único "PrintNest".

**M12. Projeto recente que falha ao reabrir no startup: silêncio total** — `main_window.py:2963-2969` (`suppress(Exception)`). Correção: toast "Não foi possível reabrir X — use Arquivo › Abrir".

**M13. Aplicar recorte refaz a produção sem nenhum feedback** — `main_window.py:6930` (+ `_bake_cropped_pdf:7128-7164`). Correção: `_wait_cursor()` (uma linha).

**M14. Memória: pixmaps de página inteira + snapshot completo POR ABA** — `main_window.py:1733, 9094-9116, 4050-4064`; 60 pág. A3 ≈ 430 MB; 3 abas grandes > 1 GB. Correção barata: teto de ~2000px no lado maior do pixmap de EXIBIÇÃO em `_load_production` (exportação não usa esses pixmaps). Validar nitidez em zoom alto.

**M15. Terminologia com dois sentidos** — "corpo(s)" × "peça(s)" no Modo Corte (`cut_mode_dialog.py:846, 1234` vs `:429, 749, 816`); "encaixar" = snap E nesting (`main_window.py:1927, 5335, 6100` vs `:7533, 1875`); "chapa/folha/página" para a mesma superfície (`cut_mode_dialog.py:557-561, 1242`; `main_window.py:5610`). Correção: padronizar peça(s); reservar "encaixe" para nesting; tooltip explicando chapa×folha no Modo Corte.

**M16. Rótulos irmãos divergentes** — "Excluir selecionado" (menu `:1884`) × "Excluir da chapa" (`:5040, 8257`); "IECHO" × "AOKE/iECHO" (`faca_icons.py:187-191`).

**M17. Separador decimal: exibição sempre com ponto ("13.50 cm")** — `main_window.py:1160` (`QLocale.C`, deliberado) e `units.py:59`; o docstring de `fmt_len` promete vírgula e o código produz ponto; tooltips escritos à mão usam vírgula — o app mistura os dois na mesma tela. Decisão de produto: exibir vírgula (aceitando ambos na digitação) ou ao menos alinhar docstring/tooltips.

**M18. Radio marcado ignora o acento do tema (azul fixo)** — `assets/icons/radio-on.svg` (`fill="#2563eb"`) + `theme.py:318-321`. Correção: desenhar como o checkbox (`border {ACCENT}`); atenção ao comentário sobre borda espessa em algumas versões do Qt — validar no .exe.

**M19. QToolButton sem estado :disabled no QSS** — `theme.py:477-487` (o QPushButton tem, `:285`). A ribbon inteira usa QToolButton: desabilitado fica com texto em cor plena. Correção: `QToolButton:disabled { color: {TEXT_MUTED}; }`.

**M20. Emoji colorido misturado à iconografia Lucide** — `main_window.py:2818` (⚠ na biblioteca), `:3063` (📄), `:3164, 3539, 3542` (✂). ATENÇÃO: `:6737` faz `item.text().startswith("⚠")` — trocar por ícone exige mover a flag para `Qt.UserRole` (3 pontos: 2818, 6737, 7346).

**M21. Modo Corte, "Texto em curvas": exige caminho de .ttf/.otf na mão** — `cut_mode_dialog.py:1285-1294`. Correção mínima: `QFileDialog` abrindo em `C:\Windows\Fonts` + OK desabilitado sem texto+fonte.

**M22. Diálogo "Recortar" aperta em 1366×768 @150%** — `main_window.py:6839` + `CropPreview.setMinimumSize(380, 380)` (`:829`). Correção: mínimo 300×300 (redesenha proporcional).

**M23. Botão truncado no aviso de update** — `update_check.py:121` "Não avisar sobre esta" → "…sobre esta versão".

---

## 🟢 REFINAMENTOS

**R1. Splash mínima de 3s em toda abertura** — `__main__.py:34` (`_SPLASH_MIN_MS = 3000`). Intencional (marca), mas o operador abre o app várias vezes ao dia; 1500ms dá o mesmo efeito.

**R2. Tour de boas-vindas × aviso de update podem se sobrepor** — `main_window.py:2580-2583` (singleShot 800 vs 3000). Adiar o update se o tour está ativo. Só relevante quando C6 for resolvido.

**R3. build.bat não valida os extras do pacote** — `build.bat:34-48`: falha no Tutor PDF/cópias passa em silêncio e o atalho do menu Iniciar (`printnest.iss:57`) nasce quebrado. Checar `errorlevel` + presença dos arquivos-chave no fim.

**R4. Ativação sem saída alternativa ao e-mail** — `licensing_dialog.py:81-118`; a EULA promete WhatsApp (`EULA.txt:48`) que o diálogo não menciona. Uma linha resolve.

**R5. Sem associação `.printnest` no Windows** — `printnest.iss` (sem `[Registry]`) e `__main__.py:29` (`_FILE_EXTS` filtra a extensão até por linha de comando). Duplo clique no projeto salvo não abre o app. Se ficar para 1.0.1, não prometer duplo clique na doc.

**R6. Escolha de chapas por sintaxe de texto nos exports do menu** — `main_window.py:9354-9365`; entrada inválida aborta sem reabrir. O Centro de Exportação (Ctrl+E) já faz certo com miniaturas.

**R7. Barra de propriedades sempre reserva a altura da scrollbar (~12px)** — `main_window.py:3017-3018`. Cosmético; o comentário explica o porquê.

**R8. Ribbon sem tratamento próprio de overflow** — em ~1092px lógicos os últimos grupos somem no chevron nativo ">>"; "Exportar" pode sair do campo de visão em notebook @125%.

**R9. Alert × Toast com raio/fundo divergentes** — `widgets/alert.py:61-65` (raio 6, fundo tingido) vs `toast.py:30-34` (raio 8, fundo branco). Igualar o raio.

**R10. Ícone WARNING do Alert a 1,95:1 sobre o fundo creme** — `alert.py:66`. Par `*_STRONG` (ex. `#b45309`) para ícone/borda.

**R11. Raios de borda fora da escala de tokens** — 14px (`main_window.py:1693`), 15px (`:5565`), 7px (`:1696, 6018`) vs `RADIUS_SM=6/RADIUS=8/RADIUS_CARD=10`. Padronizar (o painel Resumo mistura 10, 14 e 15 na mesma coluna).

**R12. QSS órfão `#statusBadge`** — `theme.py:422-429`, nenhum usuário. Remover ou adotar na status bar.

**R13. `messages.py` define avisos nunca usados** — `messages.py:86-93` (`NO_SELECTION`, `EXPORT_NO_CUT`, `missing_file()`); o papel é feito por um QMessageBox duplicado (`main_window.py:9535`). Ligar ou remover.

**R14. Rótulos com dois espaços à esquerda como padding** — `main_window.py:3105, 3108, 4686, 4917, 5380`; `licensing_dialog.py:82, 127`. Leitores de tela leem o espaço; usar QSS/ícone.

**R15. "0 peças" × "N peça(s)"** — `panels/status_bar.py:20, 50`. Padronizar.

**R16. Flags High-DPI: NÃO mexer** — Qt6 já usa PassThrough (correto); `AA_EnableHighDpiScaling`/`QT_AUTO_SCREEN_SCALE_FACTOR` são legado Qt5. Documentar num comentário do entrypoint para ninguém "consertar" no futuro.

---

## PLANO DE ATAQUE SUGERIDO (semana de 03/08)

**Dia 1 — estabilidade e jurídico (bloqueadores):**
1. C2 (lock pdfium — 10 min, elimina a melhor pista do 0xc0000374)
2. C3 (cancelamento no fechar)
3. C1 (EULA) + C5 (nome Premium×Pro) + decisão C6 (URL de update)
4. H3 + H4 (licenciamento — H4 é decisão IRREVERSÍVEL após emitir chaves)
5. H5 (excepthook, ~15 linhas)

**Dia 2 — a tela na frente do cliente:**
6. C9 + C10 (tooltip dark + contraste CTA — poucas linhas no tema)
7. C4 + H2 (Modo Corte e Ativação em 1366×768 @125%)
8. H1 (ícones com DPR — o maior ganho visual da auditoria)
9. C7 + C8 (perda de trabalho: dirty por aba + confirmação do Modo Corte)

**Dia 3 — acabamento de alto retorno:**
10. H19 (qtbase_pt_BR) + H22 (acentos) + H25 (numeração 3-3) + H23 (tooltips mm/cm)
11. H24 (revisão do pacote: LEIA-ME, .bat do plugin, VERSAO.txt, README.txt)
12. H13-H18 (feedback: barra de progresso, undo enabled, update offline, exceções amigáveis, remover da biblioteca, "Gerar Produção" nas mensagens)
13. H8-H12 conforme couber (mínimo: wait cursors; ideal: workers)

🟡 e 🟢 são pós-lançamento seguro, exceto os que caírem de brinde nos itens acima.

**Validação final recomendada**: suíte completa (`--junit-xml`; lembrar que `tests/presentation` trava como pasta — rodar por arquivos), build completo, e o roteiro de PC novo já existente com `QT_SCALE_FACTOR=1.25` e `1.5` numa janela 1366×768.
