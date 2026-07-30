# Plano inicial da versão 1.0.1

Aberto em 30/07/2026, logo após o encerramento da Release 1.0.

**Origem:** itens classificados como "1.0.1" durante o release candidate, todos
já auditados e com localização no código. Nada aqui é ideia nova — é a fila que
o Release Manager adiou conscientemente para proteger a estabilidade da 1.0.

> **Regra de entrada.** Esta versão é de **acabamento e correção**. Nenhuma
> funcionalidade nova, nenhuma refatoração de arquitetura. Solicitação que não
> se encaixe vai para 1.1 ou backlog.

---

## O que a 1.0.1 prova, antes de corrigir qualquer coisa

A 1.0.1 é a **primeira entrega pelo canal de atualização**. Isso importa mais
que o conteúdo dela: se o canal falhar, todo cliente da 1.0.0 vira reinstalação
manual guiada por suporte, um a um.

**Antes de escrever a primeira linha de código**, execute o teste de fogo:

1. Publique um instalador de teste (pode ser a própria 1.0.0 renomeada)
2. Edite o Gist: `versao: 1.0.1`, `url` com o link real, `notas` com o texto
3. Numa máquina com a 1.0.0 instalada, abra o programa
4. **O aviso tem que aparecer.** Se não aparecer, o resto do plano espera

Depois do teste, devolva o Gist para `versao: 1.0.0` até a 1.0.1 estar pronta —
senão os clientes são avisados de uma versão que ainda não existe.

---

## Bloco 1 — Nitidez e idioma (o que o cliente percebe primeiro)

### H1 — Ícones com `devicePixelRatio`
**Prioridade máxima.** É o maior ganho visual por esforço de toda a auditoria.
Hoje o app inteiro sai levemente borrado em 125–150%, que é o padrão de fábrica
em notebook 14" Full HD. Foi apontado como a causa provável do "desconforto"
relatado nos testes em outros PCs.

- **Onde:** `icons.py:28-39` (`_pixmap` com DPR fixo em 1); `faca_icons.py:91,
  219, 439-459, 577, 669`; `widgets/collapse_strip.py:62`;
  `panels/status_bar.py:30,40`; `widgets/toast.py:39`
- **Como:** obter o `devicePixelRatio()`, criar o pixmap em `size*dpr`, pintar
  com `painter.scale(dpr, dpr)`, `setDevicePixelRatio(dpr)` e **incluir o dpr na
  chave do cache**. Os call sites não mudam.
- **Também:** logo da biblioteca (`main_window.py:2597`) e splash
  (`__main__.py:95-98`) — M3.
- **Validar:** `QT_SCALE_FACTOR=1.5`, comparação visual lado a lado.

### H19 + H22 — Português completo
Bloco único de i18n.

- **H19:** carregar `qtbase_pt_BR.qm` no `main()` (2 linhas). O `.qm` **tem** de
  entrar no `PrintNest.spec` — estender o `test_build_packaging`. Testes nunca
  executam `main()`, então o impacto na suíte é zero.
  **Não** trocar o `QMessageBox.question` do `_deactivate` por botões custom:
  quebraria `test_desativar_no_exe_fecha_o_app`.
- **H22:** ~30 strings sem acento. Grupos: menu Exportar
  (`main_window.py:1949-1950, 1328, 9266, 9287`), menu Organizar (`:1874-1877`),
  tooltips de painel (`:5320-5335`), títulos "Ativacao"
  (`licensing_dialog.py:203, 239`).
- **Cuidado registrado:** caractere não-ASCII em comentário de QSS derruba a
  regra seguinte.

### H2 (150%) — Ativação em tela muito apertada
Medição do A4: a janela abre com **568 px** de altura incluindo a barra de
título. Cabe em 1366×768 @125% (~574 px úteis, folga de 6 px) e **não cabe** a
150% (~472 px). `QScrollArea` no miolo resolve os dois casos com folga.

---

## Bloco 2 — Feedback honesto da interface

### H15 — Offline ≠ em dia
`update_check.py:44-49, 94-102`: erro de rede e "está atualizado" caem no mesmo
`None`. Criar um terceiro estado com sentinela própria → *"Não consegui
verificar agora — confira sua internet"*.
**Atualizar `test_erro_de_rede_devolve_none` no mesmo commit** — ele asserta o
contrato atual.

### H13b — Barra de progresso
`main_window.py:7458-7465` e `:1101-1113`: o worker emite dois ciclos de
progresso (a barra "enche duas vezes") e nunca zera ao terminar. Total único
(import N + render M) + `reset()` e esconder no `finished`/`failed`.

### H14 — Desfazer/Refazer nascem cinza
`main_window.py:1870-1873`: conectar `canUndoChanged`/`canRedoChanged` →
`setEnabled`. Bônus barato: `undoTextChanged` no tooltip ("Desfazer: girar
peça").

### H16 — Exceções em português
`main_window.py:1499, 2913, 2939, 7474, 7645`; `cut_mode_dialog.py:773, 788,
1163`. Interceptar 3–4 famílias antes do genérico:
- `PermissionError`/`OSError` → "feche o arquivo se estiver aberto e confira a
  pasta"
- importação de PDF → "o PDF parece danificado — reexporte do Corel"
- erro COM → "abra o CorelDRAW e tente de novo"

Manter o detalhe técnico embaixo, para o suporte.

### H18 — Mensagens apontam para um botão que existe
`main_window.py:7455, 8938, 9223` mandam "Gerar a produção primeiro", mas a
ribbon e o guia do canvas ensinam **"Colocar na chapa"**. Trocar o texto.

### H17 — "Remover da biblioteca"
Remoção 100% muda e com undo inconsistente: `Ctrl+Z` restaura o arranjo mas não
a linha da biblioteca. Confirmar apenas quando o arquivo tem peças na produção;
no mínimo, toast com o nome do removido.

### M6 — Toast de erro dura mais
`widgets/toast.py:23`: erro some em 3,2 s como o de sucesso. "Falha ao importar
X" evapora antes de ser lido. ERROR com ~8 s ou exigir clique.

### M7 — `.cdr` e `.svg` respondem em vez de ignorar
`main_window.py:245-256`. O público **usa CorelDRAW**: aceitar o drop e
responder *".cdr não é suportado — exporte como PDF no Corel (Ctrl+E)"*. Sem
mudar o que é suportado.

---

## Bloco 3 — Performance percebida

Ordem por retorno. Cada item aqui troca "parece travado" por "está trabalhando".

### H12 — Debounce na quantidade
`main_window.py:6683` e `:4098`: digitar "150" roda o nesting em 1, 15 e 150.
`QTimer` de ~250 ms + wait cursor.
**Quebra `test_quantidade_multiplica_pecas` e `test_relayout_em_tempo_real...`**
— ajustar os dois no mesmo commit.

### H8 — Drop incremental
`main_window.py:8558-8624` e `:9248-9256`: soltar PDF grande numa produção já
montada, ou **receber arquivo da macro do Corel com o app aberto** (a vitrine do
produto), congela a UI pelos mesmos ~19 s já corrigidos no outro caminho.
Reutilizar o `ProductionWorker` com `paths=[path]`.

### H9 — "Páginas do PDF…" com miniaturas em lote
`main_window.py:6982-6995`: renderiza todas as páginas antes de o diálogo
aparecer. Mostrar com placeholders e preencher via `QTimer.singleShot(0, …)`.

### H11 — Exportação de imagem em worker
`main_window.py:9328-9332`: 5 chapas a 600 DPI = dezenas de segundos com "Não
respondendo". Começar pela imagem, que é o pior caso; o loop já é por página e
os exportadores não tocam widgets. **~20 testes síncronos** — avaliar o custo
antes de começar.

### H10 — "Enviar p/ Corel" em `QThread`
`corel_bridge.py:34-74` roda COM síncrono na thread da UI, sem timeout.
**Exige máquina com CorelDRAW real para validar** — lembrar do
`pythoncom.CoInitialize()` no worker. Se não houver máquina disponível, adiar
sem culpa: o mínimo (wait cursor + status) já está entregue.

---

## Bloco 4 — Infraestrutura (fora do código)

- **Domínio próprio** → publicar o manifesto nele; as builds 1.0.2+ apontam para
  lá e o Gist continua servindo a base 1.0.0 (risco R1)
- **Hospedagem definitiva do instalador** → trocar o placeholder do campo `url`
  (risco R4)
- **Certificado de assinatura de código** → mata o SmartScreen (risco R3), que é
  o ticket de suporte de maior frequência prevista
- **Associação `.printnest`** (R5) → avaliar; se não entrar, a documentação
  continua não prometendo duplo clique

---

## Fora da 1.0.1

**Versão 1.1:** N2 (autosave e recuperação — é feature com decisões de design),
M14 (teto de pixmap no preview), M17 (vírgula decimal — toca o parsing de todos
os campos), E2 (true-shape na impressão, pausado por decisão do dono).

**Backlog:** A10 (merge de facas O(n²) em chapas de 1000+ peças), A4 (marcas de
registro saem RGB(0,0,0) em vez de K puro — validar leitura no plotter real),
demais 🟡 e 🟢 da auditoria de 30/07.

**Congelado por decisão:** o motor de nesting não reabre exceto por bug real
(decisão de 22/07).

---

## Plano de testes da 1.0.1

Mesmo procedimento da 1.0 — a suíte não se auto-reporta:

```powershell
New-Item -ItemType Directory -Force reports | Out-Null
.venv\Scripts\python.exe -m pytest tests --ignore=tests\presentation -q --junit-xml=reports\core.xml
foreach ($f in Get-ChildItem tests\presentation\test_*.py) {
  $xml = "reports\" + $f.BaseName + ".xml"
  .venv\Scripts\python.exe -m pytest $f.FullName -q --junit-xml=$xml
}
.venv\Scripts\python.exe reports\somar.py
```

> `--junit-xml=$xml` com a variável montada **antes**: PowerShell não expande
> `--junit-xml=(...)` e o pytest recusa o argumento com exit 4.

**Testes obrigatórios da 1.0.1:** pixmap respeita o DPR (H1); `.qm` presente no
spec (H19); update offline devolve a sentinela e não `None` (H15); barra de
progresso zera no `finished` (H13b); Desfazer nasce desabilitado (H14).

**Lembrete de método, aprendido no A3:** teste de geometria precisa aplicar
`theme.apply()` **antes** de medir. Sem o QSS, a medição erra por 28 a 117 px e
esconde exatamente o defeito que deveria pegar.

---

## Ordem sugerida

1. Teste de fogo do canal de atualização (antes de tudo)
2. Bloco 1 — H1 primeiro, sozinho, com validação visual dedicada
3. Bloco 2 — vários itens pequenos, um único bloco de validação
4. Bloco 3 — na ordem H12 → H8 → H9 → H11 → H10, parando onde o prazo mandar
5. Bloco 4 — em paralelo, não depende de código
