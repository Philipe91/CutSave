# PLANO DEFINITIVO DE IMPLEMENTAÇÃO E LANÇAMENTO — 30/07/2026

Revisão estratégica das ~70 correções do `AUDITORIA-PRE-LANCAMENTO-2026-07-30.md`,
feita ANTES de qualquer implementação, com duas verificações adicionais no código:
(1) integridade de dados/segurança em dimensões não cobertas pela auditoria original;
(2) mapeamento correção-a-correção contra a suíte real de ~850 testes (cobertura,
testes em risco, conflitos, ordem). Nada foi modificado.

---

## 1. RESUMO GERAL

- A auditoria original está **validada**: nenhum achado se mostrou incorreto; as
  duplicatas já estavam consolidadas; nenhuma correção proposta é desnecessária —
  mas **7 devem ser adiadas ou simplificadas** porque o risco de regressão supera o
  benefício na semana do lançamento (§6).
- A verificação de integridade encontrou **um tema novo que a auditoria original não
  cobriu e que muda o plano**: *nenhuma escrita do app é atômica e não existe
  recuperação* — salvar projeto pode destruir o arquivo anterior (N1) e um
  `config.json` corrompido impede o app de abrir para sempre (N3). Dois novos 🔴.
- O mapeamento de testes encontrou **5 armadilhas concretas** onde a correção "do
  jeito óbvio" quebra a suíte ou o produto (§4) — inclusive um falso-verde: preencher
  a URL de update (C6) sem atualizar `test_sem_url_configurada_nao_faz_requisicao`
  deixa o teste verde por engano e cria uma QThread órfã (flake).
- Total consolidado: **12 itens obrigatórios para 1.0** (§5), o resto distribuído em
  6 sprints ou adiado para 1.1.

## 2. NOVOS ACHADOS DE INTEGRIDADE (não estavam na auditoria original)

| # | Achado | Local | Prior. |
|---|--------|-------|--------|
| N1 | Salvar `.printnest` NÃO é atômico — `write_text` direto no destino; interrupção destrói o arquivo novo E o anterior; sem `.bak` | `app/application/project_io.py:169-178` | 🔴 |
| N2 | Zero autosave/recuperação — crash perde tudo desde o último Ctrl+S (é o seguro contra o 0xc0000374) | ausência confirmada em todo `app/` | 🟠 |
| N3 | `config.json` corrompido = app não abre NUNCA MAIS, sem mensagem — `load_or_create()` sem try antes do QApplication, com `console=False`; escrita também não-atômica | `app/shared/config/settings.py:86-94` + `app/presentation/__main__.py:124-126` | 🔴 |
| N4 | Falha ao gravar config aborta operações principais — em `export_image` a exceção estoura ANTES da exportação; em `save_project` depois do save (usuário vê erro achando que não salvou) | `main_window.py:2893, 2918, 2943, 9326-9327` | 🟡 |
| N5 | %TEMP% acumula para sempre: cache de recortes usa `hash()` randomizado por processo (nunca acerta entre sessões) e `printnest-faca-*` guarda cópias integrais dos PDFs dos clientes sem limpeza | `main_window.py:7159, 7192`; `pdfium_knife.py:131, 159` | 🟡 |
| N6 | Log da GUI não registra versão/sessão; crash.log em append eterno sem data/versão/limite | `app/presentation/__main__.py:40-50` (o `log.info` de versão só existe no stub CLI que o .exe não usa) | 🟡 |
| N7 | Exportações sobrescrevem o destino direto — falha no meio deixa PDF/DXF meio-escrito que um RIP pode consumir parcialmente (chapas faltando = material perdido) | `pikepdf_print_exporter.py:89, 128-137`; `dxf_exporter.py:107` | 🟡 |
| N8 | `license.key` presente mas inválido vira tela de ativação seca, sem explicar ("perdi minha licença?") | `app/licensing/manager.py:34-42` | 🟢 |
| N9 | `server.listen()` da instância única sem checagem — falha silenciosa habilita duas instâncias completas gravando os mesmos arquivos | `single_instance.py:46-48` | 🟢 |
| N10 | Quantidade aceita 100.000 com renesting síncrono — dedo a mais trava o app por minutos | `main_window.py:1212` | 🟢 |

**Um helper compartilhado de escrita atômica (~10 linhas: `.tmp` no mesmo dir +
`flush/fsync` + `os.replace`) resolve N1, N3-escrita, N4-parcial e N7 de uma vez.**

**Verificado e OK (não precisa de ação)**: formato do projeto é JSON versionado e
validado, NÃO pickle (sem risco ao abrir projeto de terceiros); `printnest.log` tem
rotação 2MB×5; Ed25519 só com chave pública no binário (privada fora do repo e do
pacote, confirmado); relógio atrasado nunca quebra licença; updates.py não baixa nem
executa nada (64KB, só http/https); nomes com acento/emoji OK (PIL, não cv2.imread);
PyInstaller 6.21 já embute `longPathAware` no manifest; handles pdfium/pikepdf
fechados com disciplina; ranges dos spins sensatos; PDF com senha/lixo tratado;
RLock do pdfium sem ciclo de deadlock possível.

## 3. RESPOSTAS ÀS 10 PERGUNTAS ESTRATÉGICAS

1. **Correções que podem quebrar outras partes?** Sim, 5 (detalhe no §4): C7 (pode
   PENDURAR a suíte inteira via conftest), C8/H17 (modais novos sem a guarda
   `PYTEST_CURRENT_TEST` quebram 5+ testes), C6 (falso-verde em teste de update),
   H15 (muda contrato de `checar()` — teste existente asserta o comportamento velho),
   C5 (renomear as chaves de QSettings `"PrintNestPremium"` resetaria tema/tour dos
   usuários — renomear SÓ strings visíveis).
2. **Duplicadas?** Já consolidadas no relatório (EULA ×2, nome ×3, Yes/No ×2, update
   offline ×2, toast erro ×2, fechar-com-thread ×2, numeração 3-3 ×2, fontes 10px ×2,
   exceções cruas ×2). Nenhuma ação duplicada no plano.
3. **Fazer juntas?** Sim — 6 blocos naturais: tema (C9+C10+H20+H21+M18+M19, mesmos
   2 arquivos), textos (C1+C5+H19+H22+H23+H25+H18+H16), `_close_tab` (C7+M5, mesma
   função), update (C6+H15, mesmos arquivos e testes), região worker/busy (C2→H13→C3),
   escrita atômica (N1+N3+N4+N7, mesmo helper).
4. **Dependências?** H4 ANTES de emitir qualquer chave (irreversível); C6 antes de
   R2; estender `test_themes` ANTES da passada de tema (test-first — os 2 testes
   novos devem falhar no código atual); ajuste do `conftest` JUNTO com C7.
5. **Ordem obrigatória?** C2 → H13 → C3 (mesma região; fazer C3 antes de H13 obriga
   a reescrever o teardown do busy duas vezes). Sprints na ordem do §7.
6. **Risco sem benefício proporcional?** H10 (COM em QThread — sem como validar sem
   Corel real, quebra teste síncrono), H11 (exports em worker — ~20 testes síncronos),
   H12-debounce (quebra testes que assertam resultado imediato), M14 (mexe no coração
   do preview na véspera), M17 (parsing de todos os spins), R5 (cadeia longa sem
   teste de instalador).
7. **Adiar para 1.1?** Os 6 acima + certificado de assinatura (H6 — versão 1.0 leva
   só o texto no e-mail/página de entrega) + N2-autosave se o prazo apertar (aceitável
   adiar SE C2/C3/N1 estiverem fechados) + M14/M17/R5/R6 e todos os 🟢 não citados.
8. **Simplificáveis?** C3 (flag no loop + wait, sem UI nova), C4 (mínimo 900×540 +
   `setMaximumHeight` na prévia, sem QScrollArea), H2 (chave 64px + SPACE_SM), H8/H9/
   M13 (wait cursor em vez de worker), H17 (toast em vez de confirmação), H6 (texto).
9. **Desnecessárias?** Nenhuma incorreta; 2 "não-ações" explícitas: R16 (NÃO adicionar
   flags de High-DPI — Qt6 já está certo) e a alternativa "esconder o menu de update
   sem URL" do C6 (quebraria 2 testes; preencher a URL é o caminho).
10. **Podem introduzir regressões?** As do §4; todas têm mitigação mapeada e teste
    obrigatório definido.

## 4. AS 5 ARMADILHAS DE REGRESSÃO (mapeadas contra a suíte real)

1. **C7 (dirty por aba)**: o `conftest.pytest_sessionfinish` seta `widget._dirty =
   False` e fecha janelas — se o `closeEvent` checar `any(sessão dirty)` fora da
   guarda, sessões sujas de abas inativas abrem modal SEM `PYTEST_CURRENT_TEST` e
   penduram a suíte. Fazer a checagem agregada DENTRO de `_confirm_discard` (depois
   da guarda) E atualizar o conftest para zerar o dirty das sessões. Manter `_dirty`
   como atributo simples (property sem setter quebra o teardown com AttributeError).
2. **C8/H17 (modais novos)**: obrigatória a guarda `os.environ.get("PYTEST_CURRENT_TEST")
   or not self.isVisible()` — senão `test_reject_durante_organizar_nao_fecha_e_avisa`
   (que chama `reject()` com `_layouts` populado) e os 4 testes de remoção da
   biblioteca quebram.
3. **C6 (URL de update)**: `test_sem_url_configurada_nao_faz_requisicao` foi escrito
   assumindo constante vazia — preencher sem atualizar o teste cria falso-verde
   (o `except` do `_Consulta.run` engole o AssertionError) + QThread órfã. Atualizar
   o teste com `monkeypatch URL_MANIFESTO_PADRAO=""` no mesmo commit.
4. **H15 (update offline)**: `test_erro_de_rede_devolve_none` asserta o contrato
   atual (`checar(...) is None` em erro). A correção MUDA esse contrato — atualizar o
   teste junto, mantendo `None` = "em dia" e sentinela própria para erro.
5. **H19 (pt-BR)**: resolver com `qtbase_pt_BR.qm` carregado em `main()` (testes
   nunca executam `main()` → zero impacto). NÃO trocar `QMessageBox.question` do
   `_deactivate` por botões custom (quebraria `test_desativar_no_exe_fecha_o_app`).
   O .qm TEM de entrar no `PrintNest.spec` — estender `test_build_packaging`.

## 5. OBRIGATÓRIO PARA A 1.0 (12 itens — bloqueadores)

C1 (EULA) · C2 (lock pdfium) · C3 (cancelamento no fechar) · C4 (Modo Corte @125%) ·
C5 (nome, só strings visíveis) · C6 (URL update, decisão + hosting) · C7 (dirty por
aba) · C8 (confirmação Modo Corte) · C9+C10 (tema: tooltip + CTA) · **N1 (salvar
atômico)** · **N3 (config corrompido não pode brickar)** · H3+H4 (licença: gravação
verificada + decisão do MAC ANTES da primeira chave vendida).

Fortemente recomendados se couber: H5 (excepthook), H1 (ícones DPR), H19+H22 (pt-BR
+ acentos), H24 (pacote), H2 (ativação @125%), N2 (autosave).

## 6. ADIADO PARA 1.1 (com justificativa)

| Item | Por quê | Mínimo que a 1.0 leva |
|------|---------|----------------------|
| H10 COM em QThread | apartment COM sem como validar sem Corel; quebra teste síncrono | wait cursor + status "Enviando ao CorelDRAW…" |
| H11 exports em worker | ~20 testes síncronos; assincronia na semana errada | wait cursor já existe |
| H12 debounce | quebra `test_quantidade_multiplica_pecas` e `test_relayout_em_tempo_real...` | wait cursor no relayout |
| M14 teto de pixmap | coração do preview; sem teste de qualidade visual | — (documentado) |
| M17 vírgula decimal | `QLocale.C` deliberado; toca parsing de todos os spins | alinhar docstring/tooltips |
| R5 associação .printnest | cadeia .iss+registry+roteamento sem teste | doc não promete duplo clique |
| H6 certificado | custo/prazo; EV é a solução real | instrução SmartScreen no e-mail/página de entrega |
| N2 autosave | desejável na 1.0; aceitável 1.1 SE C2/C3/N1 fechados | — |
| M/R restantes | polimento sem risco de recall | os que caírem de brinde nos sprints |

## 7. SPRINTS (ordem e porquê)

**Sprint 1 — Estabilidade e integridade (sem UI)** — C2 → H13 → C3 → H5 → N1 → N3 →
N4 → H7(mutex no app) → N6. *Por quê primeiro: elimina as causas de crash e de perda
de dados; é a fundação de todo o resto; não toca UI = menor risco de regressão; C2 é
a melhor pista do 0xc0000374 e custa 10 minutos.*

**Sprint 2 — Licenciamento e canal (decisões irreversíveis)** — H4 (MAC) → H3 →
N8 → C6+H15 (com os 2 testes atualizados juntos). *Por quê segundo: H4 é IRREVERSÍVEL
depois da primeira chave vendida; C6 é a apólice de seguro do lançamento (sem ela,
nenhum hotfix chega aos clientes).*

**Sprint 3 — Perda de trabalho (UX destrutiva)** — C7+M5 (com ajuste do conftest) →
C8 → H17 → N2 (autosave, se couber). *Por quê: são as correções com mais fios ligados
na suíte (armadilhas 1 e 2); precisam de calma e vêm antes do acabamento.*

**Sprint 4 — Tema e acessibilidade (test-first)** — estender `test_themes` (2 testes
novos, ver FALHAR) → C9+C10+H20+H21+M18+M19 numa passada em `theme.py`+`palettes.py`+
`radio-on.svg`. *Por quê: bloco 100% isolado em 2 arquivos, test-first garante o
resultado; cuidado: caractere não-ASCII em comentário de QSS derruba a regra seguinte.*

**Sprint 5 — Responsividade e nitidez** — H1 (DPR nos ícones) → C4 (+ teste no padrão
`test_layout_telas`) → H2+H25+R4 → M1/M22 se sobrar. *Por quê: maior ganho visual por
esforço; independentes entre si; validação visual concentrada numa tarde
(QT_SCALE_FACTOR 1.25/1.5).*

**Sprint 6 — Textos, pacote e acabamento** — H19(.qm no spec)+H22+H23+H18+H16 →
C1+C5 → H24 (+extensão do `test_build_packaging`) → H8/H9/M13 (wait cursors) → H14 →
M23 → N5/N10 se sobrar. *Por quê por último: quase tudo é string/texto com risco
próximo de zero; um único bloco de validação (rodar os arquivos de teste com asserts
de texto uma vez só).*

## 8. PLANO DE TESTES

**Após cada sprint** (rodadas dirigidas):
- S1/S3 → `tests\qa\test_qa_f2a_abas.py`, `tests\presentation\test_main_window.py`, `tests\qa\test_qa_f2b_estado.py`
- S2 → `tests\licensing`, `tests\infrastructure\test_updates.py`, `tests\presentation\test_update_check.py`
- S4 → `tests\presentation\test_themes.py` (+ abrir o app e conferir QSS vivo)
- S5 → `tests\presentation\test_layout_telas.py`, `test_cut_mode_dialog.py`, `test_cut_mode_manip.py`
- S6 → `tests\test_build_packaging.py` + arquivos com asserts de texto

**Testes novos obrigatórios** (nomes e asserts no relatório do QA): lock-espião no
`_pdf_page_count`; fechar-durante-geração termina <3s sem abort; Modo Corte cabe em
1366×545; dirty-é-por-aba + trocar-de-aba-não-suja; confirmação do Modo Corte (por
role); contraste `ICON_ON_ACCENT×ACCENT` em todos os presets; tooltip legível em
todos os temas; `machine_id` estável com MAC variando; ativar-sem-conseguir-gravar
avisa (monkeypatch em `write_text`, NÃO pasta read-only — atributo de pasta não
bloqueia escrita no Windows); pixmap respeita DPR; save atômico sobrevive a escrita
interrompida; config corrompido abre com defaults; .qm no spec; EULA sem placeholders.

**Suíte completa (a suíte NÃO se auto-reporta e `tests\presentation` trava como pasta):**
```powershell
New-Item -ItemType Directory -Force reports | Out-Null
.venv\Scripts\python.exe -m pytest tests --ignore=tests\presentation -q --junit-xml=reports\core.xml
Get-ChildItem tests\presentation\test_*.py | ForEach-Object {
  .venv\Scripts\python.exe -m pytest $_.FullName -q --junit-xml=("reports\" + $_.BaseName + ".xml")
}
# somar os XML (o terminal mente — o processo morre no teardown com 0xC0000005)
.venv\Scripts\python.exe -c "import glob,xml.etree.ElementTree as ET; ts=[ET.parse(f).getroot() for f in glob.glob('reports/*.xml')]; g=lambda k: sum(int(s.get(k,0)) for t in ts for s in t.iter('testsuite')); print(f'tests={g(\"tests\")} failures={g(\"failures\")} errors={g(\"errors\")} skipped={g(\"skipped\")}')"
```

**Validação manual final**: build completo → instalar numa máquina limpa (o roteiro
de PC novo já existente) → `QT_SCALE_FACTOR=1.25` e `1.5` em janela 1366×768 →
fluxo completo importar→gerar→Modo Corte→exportar→Corel → matar o processo com
projeto sujo e reabrir → truncar config.json e abrir → instalar 1.0.1-fake por cima
com o app aberto.

## 9. AUDITORIA DE EXPERIÊNCIA PREMIUM (percepção, não bugs)

Momentos que quebram a sensação de produto de R$ 1.000, em ordem de jornada:
1ª impressão: SmartScreen sem explicação no ponto de download → EULA com colchetes →
ativação com passos 1-2-3-3. Primeiro uso em notebook 150%: **todo o app levemente
borrado** (H1) — a percepção "amadora" mais difusa e constante. Uso: botão principal
lavado nos presets; tooltips invisíveis no escuro; barra de progresso que enche duas
vezes e nunca esvazia; Desfazer sempre aceso; Yes/No em inglês no pior diálogo;
"13.50 cm" com ponto ao lado de tooltips com vírgula; modais de OK no fluxo repetitivo
do Modo Corte; emoji colorido no meio da iconografia sóbria. O que já entrega
percepção premium: estados vazios que ensinam, tour, tooltips ricos, undo profundo,
tema com editor completo, nesting em thread com dicas rotativas.

## 10. AUDITORIA DE CUSTOMER SUCCESS (previsão de tickets, por frequência)

1. **SmartScreen** ("não abre / deu vírus") — alta; mitigação: texto na entrega (H6-mín).
2. **Ativação** — alta: e-mail como único canal (R4), ID×código (já mitigado no
   diálogo), licença que "some" (H3), MAC mudou (H4). As correções derrubam para média.
3. **"Comprei Pro, instalou Premium"** — média-alta; zera com C5.
4. **"Cliquei em Enviar p/ Corel e travou"** — média (H10-mín reduz percepção).
5. **"Deu um erro e sumiu" / erro em inglês** — média (M6+H16).
6. **"Não cabe na tela / botão cortado"** — média em notebook (C4/H2).
7. **"Perdi meu projeto"** — baixa frequência, gravidade máxima (reembolso):
   C7+N1+N2+C8 são a resposta.
8. **".cdr não entra"** — média (M7 responde no app).
9. **"Como atualizo?"** — média a partir da 1.0.1; depende 100% de C6.
10. **"O programa não abre mais"** — rara, fatal (N3); vira reembolso se não corrigida.

## 11. AUDITORIA DE LANÇAMENTO (se fosse amanhã)

- **Jurídico**: 🔴 EULA sem vendedor/foro/política de update — contrato deficiente
  exibido a cada instalação. Resolve com C1 (texto).
- **Comercial**: 🟠 nome do produto divergente entre venda e entrega (C5).
- **Técnico**: 🔴 crash de heap com causa provável conhecida e não corrigida (C2);
  perda de dados por escrita não-atômica (N1/N3); perda de trabalho silenciosa (C7/C8).
- **Operacional**: 🔴 sem canal de update (C6) — qualquer bug pós-venda vira
  reinstalação manual guiada por suporte; 🟠 suporte só por e-mail no fluxo de ativação.
- **Financeiro**: 🟠 reembolsos concentrados nos cenários N3 (app não abre) e
  perda de projeto.
- **Reputação**: 🟠 SmartScreen + app borrado em 150% nos primeiros vídeos/reviews.

## 12. CHECKLIST FINAL DE LANÇAMENTO 1.0

**Estabilidade/dados**: [ ] C2 lock pdfium [ ] C3 fechar durante geração sem abort
(10× seguidas) [ ] N1 save atômico + teste de interrupção [ ] N3 config corrompido
abre com defaults [ ] H5 excepthook logando + diálogo [ ] crash.log com versão/data
(N6) [ ] matar processo e reabrir sem corrupção
**Licenciamento/ativação**: [ ] decisão do MAC tomada e testada (H4) [ ] ativar com
disco travado avisa (H3) [ ] license.key truncado explica (N8) [ ] ativar→desativar→
reativar em máquina limpa [ ] robô de vouchers reflete a decisão do fingerprint
**Atualizações**: [ ] manifesto publicado e URL preenchida (C6) [ ] check manual:
versão nova / em dia / offline (H15) — 3 respostas distintas [ ] "Não avisar sobre
esta versão" (M23)
**Instalação**: [ ] EULA final sem placeholders (C1) [ ] nome único em título/Sobre/
instalador/VERSAO.txt (C5) [ ] AppMutex: instalar por cima com app aberto (H7)
[ ] instalar/desinstalar/reinstalar preservando licença [ ] instrução SmartScreen na
página/e-mail de entrega (H6-mín) [ ] pacote confere com o que o LEIA-ME promete (H24)
**Responsividade/DPI**: [ ] ícones nítidos em 150% (H1) [ ] Modo Corte e Ativação
cabem em 1366×768 @125% (C4/H2) [ ] varredura visual 100/125/150% nas 5 telas do
`test_layout_telas`
**UX/UI**: [ ] tooltip legível nos 4 temas (C9) [ ] CTA legível nos 10 presets (C10)
[ ] dirty por aba (C7) [ ] confirmação do Modo Corte (C8) [ ] barra de progresso
zera (H13) [ ] Desfazer nasce cinza (H14) [ ] foco visível por Tab (H20)
**Textos**: [ ] Yes/No→Sim/Não com .qm empacotado no spec (H19) [ ] passada de
acentos (H22) [ ] tooltips sem "(mm)" enganoso (H23) [ ] mensagens sem "Gerar
Produção" fantasma (H18) [ ] exceções com ação sugerida (H16)
**Exportação**: [ ] exportar por cima de PDF aberto no Acrobat: erro claro e arquivo
antigo preservado (N7, se entrar) [ ] fluxo completo até o Corel na máquina real
**Testes/QA**: [ ] suíte completa via junit-xml somada = 0 falhas [ ] testes novos
obrigatórios do §8 verdes [ ] benchmark do nesting inalterado (motor congelado)
**Release**: [ ] versão única 1.0.0 em app/iss/VERSAO.txt (H24) [ ] release notes =
VERSAO.txt reescrito [ ] build.bat validando extras (R3) [ ] tag git + zip do
instalador arquivado [ ] roteiro de PC novo executado do zero na máquina limpa

## 13. VEREDITO

- **Maturidade do software: 7,5/10** — arquitetura, formato de dados, licenciamento,
  onboarding e design system acima da média; derrubam a nota: integridade de escrita
  inexistente, os 2 crashes evitáveis, e o acabamento de DPI/textos.
- **Confiança para lançar AMANHÃ, como está: 4/10 — NÃO RECOMENDO LANÇAR** (EULA,
  crash com causa conhecida, perda de dados possível, canal de update morto).
- **Confiança após Sprints 1–3 + C1/C5/C6: 8,5/10 — LANÇAMENTO POSSÍVEL COM
  RESSALVAS** (ressalvas: sem assinatura digital, Corel síncrono, exports síncronos —
  todos com mitigação mínima incluída e plano 1.1).
- Sprints 4–6 antes do lançamento elevam para **PRONTO PARA LANÇAMENTO** na percepção
  do cliente; são ~2 dias adicionais de trabalho de baixo risco.
