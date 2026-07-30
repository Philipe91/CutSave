# A3 — VALIDAÇÃO MANUAL DA RELEASE CANDIDATE 1.0

**Data de execução:** ____/____/2026  **Executado por:** ______________________

Portão A3 exigido pelo Release Manager antes de liberar o A4 (rebuild + smoke).
Valida **manualmente, com o app rodando**, as 18 correções entregues em 30/07 nos
commits `2162ef5` (12 bloqueadores) e `1717043` (lote final).

**Este roteiro NÃO substitui** o `ROTEIRO-HOMOLOGACAO.md` (homologação funcional
ampla) nem o `TESTE-PC-NOVO.md` (jornada do cliente em máquina limpa). Ele é
cirúrgico: só olha o que mudou hoje, e só o que dá para provar **antes** de gerar
o executável.

> **Congelamento de código ativo.** Se algum item reprovar, **não corrija por
> conta própria**: registre no campo Observações e leve para classificação
> (Corrigir imediatamente / 1.0.1 / 1.1 / Rejeitar). Uma reprovação não invalida
> as outras — continue o roteiro até o fim para a decisão ser tomada com o
> quadro completo.

---

## PRÉ-REQUISITOS

Marque antes de começar. Sem isto o roteiro não é executável.

| | Pré-requisito | Como conferir |
|---|---|---|
| ☐ | Código na revisão certa | `git log --oneline -3` mostra `1717043` no topo |
| ☐ | Nada pendente na árvore | `git status --short` sem arquivos de `app/` modificados |
| ☐ | Suíte verde nesta revisão | 939 testes, 0 falhas (já executado — ver §Evidências) |
| ☐ | **PDF grande** (60+ páginas) | arte real de produção; é o único jeito de a geração durar tempo suficiente para o teste V1 |
| ☐ | PDF/PNG pequeno qualquer | serve `assets\exemplo\exemplo-printnest.pdf` |
| ☐ | Gerenciador de Tarefas aberto | para conferir processo zumbi no V1 |
| ☐ | Pasta de logs à mão | `%APPDATA%\PrintNest\logs` |

**Como rodar o app a partir do fonte** (é assim que todo o A3 é executado):

```powershell
cd c:\projetos\Cutph
.venv\Scripts\python.exe -m app.presentation
```

**Como emular um notebook 1366×768 @125% na sua máquina** (usado em V2):

O seu monitor principal é 1920×1080 com 1040px de área útil. Um notebook
1366×768 a 125% deixa **~545px lógicos** para as janelas. Para reproduzir o
mesmo aperto aqui, o fator é `1040 ÷ 545 ≈ 1.9`:

```powershell
cd c:\projetos\Cutph
$env:QT_SCALE_FACTOR="1.9"
.venv\Scripts\python.exe -m app.presentation
```

> Usar `1.25` na sua tela **não testa nada** — sobra espaço de qualquer jeito.
> Se você tiver um notebook 1366×768 de verdade à mão, use `1.25` **nele**.
> Ao terminar o V2, feche o app e limpe: `$env:QT_SCALE_FACTOR=""`

**O que NÃO dá para validar aqui** (depende do executável — vai para o A4):
a tela de Ativação **bloqueante** na primeira execução (só acontece com
`sys.frozen`), o AppMutex visto pelo instalador (A4a), e o canal de atualização
consultado de dentro do binário (A4b).

---

## V1 — Fechar a janela durante uma geração longa (C3)

**Objetivo.** Provar que fechar o PrintNest no meio de uma geração não congela a
janela por 10 segundos nem mata o processo à força. Antes desta correção o
`quit()` não interrompia o worker: a janela ficava "não respondendo" e, se o
worker não terminasse a tempo, o Qt abortava o processo — o cliente via "o
programa fechou sozinho".

**Pré-requisitos.** PDF de 60+ páginas. Gerenciador de Tarefas aberto na aba
Detalhes. Pasta de logs à mão.

**Passos.**
1. Abra o app pelo fonte.
2. `Ctrl+I` → adicione o PDF grande.
3. Pressione `F5` (Colocar na chapa / Gerar Produção).
4. **Enquanto a barra de progresso está correndo**, clique no X da janela.
5. Se aparecer a pergunta de descartar trabalho, confirme o fechamento.
6. Cronometre do clique até a janela sumir da tela.
7. No Gerenciador de Tarefas, procure por `python.exe` órfão da sessão.
8. Abra `%APPDATA%\PrintNest\logs\crash.log` e veja se ganhou entrada nova.
9. **Repita os passos 1–8 mais uma vez** (o defeito era intermitente).

**Resultado esperado.**
- A janela fecha em **menos de 3 segundos** nas duas repetições.
- A janela **não** exibe "Não Respondendo" em nenhum momento.
- **Nenhum** processo `python.exe` sobra no Gerenciador de Tarefas.
- **Nenhuma** entrada nova no `crash.log`.

| Registro | |
|---|---|
| Resultado | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Tempo medido (1ª / 2ª) | ______ s / ______ s |
| Processo órfão? | ☐ Não ☐ Sim |
| Entrada nova no crash.log? | ☐ Não ☐ Sim |
| Observações | |

---

## V2 — Modo Corte e Ativação em tela apertada (C4, H2, H25)

**Objetivo.** Provar que os dois diálogos que estouravam a tela agora cabem. O
Modo Corte é aberto **sozinho pela macro do CorelDRAW**, sem janela principal
por trás: com os botões fora da tela o operador fica sem saída. A Ativação é a
**primeira tela do produto comprado**: com "Ativar" abaixo da borda, o cliente
não entra no software que pagou. Medições feitas: Modo Corte 534px, Ativação
509px, contra ~545px disponíveis.

**Pré-requisitos.** App fechado. Rodar com `QT_SCALE_FACTOR=1.9` (ver
Pré-requisitos). Um PDF/SVG qualquer para o Modo Corte.

**Passos.**
1. Abra o app com o fator 1.9 aplicado.
2. Restaure a janela (sair do maximizado) para não esconder o problema.
3. Abra o **Modo Corte** (botão da tesoura na barra superior).
4. Confira se os **quatro** botões do rodapé estão visíveis **sem** rolar nem
   redimensionar: `Organizar`, `Enviar p/ Corel`, `Exportar DXF`, `Fechar`.
5. Role o painel de parâmetros da esquerda e confirme que ele rola por dentro
   em vez de empurrar os botões para fora.
6. Feche o Modo Corte.
7. Menu **Ajuda → Licença...**
8. Confira se os botões do rodapé (`Ativar`, `Desativar`, `Fechar`) estão
   visíveis sem rolar.
9. **Leia a numeração dos passos do diálogo, de cima para baixo.**

**Resultado esperado.**
- Modo Corte: os 4 botões do rodapé visíveis; o painel de parâmetros rola.
- Ativação: todos os botões visíveis; o campo da chave continua confortável
  para colar uma chave inteira.
- A numeração lê **1 → 2 → 3 → 4** (antes era 1‑2‑3‑**3**).

| Registro | |
|---|---|
| Modo Corte cabe | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Ativação cabe | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Numeração 1‑2‑3‑4 | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Observações | |

---

## V3 — Texto do botão de destaque nos presets de tema (C10)

**Objetivo.** Provar que o texto do CTA (o `GERAR FACA` e os cabeçalhos de card)
é legível em todos os presets. Sete presets reprovavam contraste WCAG AA com o
branco fixo — Verde media 2,28:1, Turquesa 2,49, Graphite 2,52, Laranja 2,80.
Agora a cor do texto é derivada por luminância, o que significa que **presets
claros passam a ter texto escuro no botão**. Isso é o comportamento correto, mas
é uma mudança visual perceptível: esta validação existe para você aprovar a
aparência, não só o número.

**Pré-requisitos.** App aberto (escala normal serve). Pelo menos um arquivo
carregado, para o botão de faca aparecer.

**Passos.**
1. **Opções → Personalizar Interface...**
2. Aplique o preset **Emerald/Verde**. Olhe o botão de destaque principal.
3. Aplique um preset **claro** (ex.: Graphite ou o tema Claro padrão).
4. Aplique o tema **Escuro**.
5. Em cada um: o texto do botão está legível a uma distância normal de uso?

**Resultado esperado.**
- O texto do botão de destaque é legível nos três casos.
- Nos presets claros o texto aparece **escuro** sobre o acento — esperado.
- Nenhum botão com texto "lavado" ou sumindo no fundo.

| Registro | |
|---|---|
| Resultado | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Preset claro com texto escuro incomoda? | ☐ Não ☐ Sim — decisão do dono |
| Observações | |

---

## V4 — Tooltip nos temas escuros (C9)

**Objetivo.** Provar que os 104 tooltips do app voltaram a ser legíveis no modo
escuro. O QSS pintava texto branco sobre fundo branco (contraste 1,0:1): no dark
mode — recurso vendido — todos os balões apareciam vazios.

**Pré-requisitos.** App aberto.

**Passos.**
1. **Opções → Personalizar Interface...** → tema **Escuro**.
2. Pare o mouse sobre um botão da barra superior e espere o balão.
3. Repita no tema **Midnight** e no **Carbon**.
4. Volte ao tema **Claro** e confirme que continua legível.

**Resultado esperado.** O texto do tooltip aparece e é legível nos quatro temas.

| Registro | |
|---|---|
| Escuro | ☐ ✔ ☐ ❌ | 
| Midnight | ☐ ✔ ☐ ❌ |
| Carbon | ☐ ✔ ☐ ❌ |
| Claro | ☐ ✔ ☐ ❌ |
| Observações | |

---

## V5 — Perda de trabalho: abas e Modo Corte (C7, C8)

**Objetivo.** Provar as duas rotas de perda silenciosa de trabalho. **C7:** o
`_dirty` era global — editar a aba A, trocar para a B, salvar a B e fechar o app
matava o trabalho da aba A sem perguntar nada. **C8:** um `Esc` acidental no
Modo Corte jogava fora minutos de nesting e retoques manuais, sem volta.

**Pré-requisitos.** App aberto. Dois arquivos quaisquer.

**Passos — C7 (dirty por aba):**
1. Na aba 1, adicione um arquivo e mude alguma coisa (quantidade, espaçamento).
2. Crie uma **aba nova** (aba 2) e adicione outro arquivo.
3. Com a aba 2 ativa, salve o projeto (`Ctrl+S`).
4. Feche o PrintNest pelo X.

**Passos — C8 (descarte do arranjo):**
5. Reabra o app. Abra o **Modo Corte** com um arquivo.
6. Clique em **Organizar** e espere o nesting terminar.
7. Pressione **Esc**.
8. Escolha **Continuar aqui**. Confirme que o diálogo permanece aberto e o
   arranjo continua na tela.
9. Agora clique em **Exportar DXF** e salve em qualquer lugar.
10. Pressione **Esc** de novo.

**Resultado esperado.**
- Passo 4: aparece a pergunta avisando que há trabalho não salvo **em outra
  aba** — o app **não** fecha calado.
- Passo 7: aparece a pergunta "Fechar o Modo Corte descarta o arranjo
  organizado", com botões em português.
- Passo 8: escolher "Continuar aqui" mantém o arranjo intacto.
- Passo 10: depois de exportar, o `Esc` fecha **sem** perguntar (o trabalho já
  foi aproveitado).

| Registro | |
|---|---|
| C7 — avisa sobre aba inativa suja | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| C8 — pergunta antes de descartar | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| C8 — não pergunta depois de exportar | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Observações | |

---

## V6 — Exportação bloqueada durante a geração (H13a)

**Objetivo.** Provar que não dá mais para exportar o resultado **antigo** no meio
de uma geração nova. Numa gráfica isso significa chapa errada impressa em
material caro, sem nenhum aviso de que aconteceu.

**Pré-requisitos.** PDF grande (o mesmo do V1). Uma produção **já gerada** antes,
para existir um "resultado antigo" exportável.

**Passos.**
1. Gere uma produção pequena e deixe pronta (`F5`).
2. Confirme que o menu **Exportar** está habilitado.
3. Adicione o PDF grande e dispare `F5` de novo.
4. **Durante** a barra de progresso, abra o menu Exportar.
5. Pare o mouse sobre um item desabilitado e leia o tooltip.
6. Espere terminar e abra o menu Exportar de novo.

**Resultado esperado.**
- Passo 4: **todos** os itens de exportação aparecem cinza (Centro de
  Exportação, PDF, DXF, imagem, faca, cartelas, Mimaki, iECHO).
- Passo 5: o tooltip diz **"Aguarde a geração terminar"** — e não o antigo
  "Gere a produção primeiro".
- Passo 6: tudo volta a ficar habilitado ao terminar.

| Registro | |
|---|---|
| Exportações ficam cinza durante | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Tooltip correto | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Voltam ao terminar | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Observações | |

---

## V7 — Canal de atualização respondendo (C6)

**Objetivo.** Provar, com o app rodando, que o endereço gravado no código
responde e que o cliente **em dia** recebe a resposta certa. Sem este canal
nenhum cliente da 1.0.0 ficaria sabendo de uma 1.0.1 — e a própria 1.0.1 é
entregue por ele. O manifesto publicado anuncia `1.0.0` e o app está em `1.0.0`,
então a resposta correta é "já está na versão mais recente".

**Pré-requisitos.** App aberto **com internet**.

**Passos.**
1. Menu **Ajuda → Procurar atualizações**.
2. Leia a mensagem.
3. Feche o app e reabra **com o Wi-Fi/cabo desligado**.
4. Menu **Ajuda → Procurar atualizações** de novo.

**Resultado esperado.**
- Com internet: mensagem dizendo que **já está na versão mais recente**. Não
  pode aparecer nenhum texto de desenvolvedor (ex.: "Defina 'update_url'…").
- A janela **não congela** durante a consulta.
- Sem internet: o app responde alguma coisa e **não trava** nem quebra.

> **Nota registrada:** offline o app hoje responde "você já está na versão mais
> recente" em vez de "não consegui verificar" — é o item **H15**, classificado
> para a **1.0.1**. Marcar como esperado, não como reprovação.

| Registro | |
|---|---|
| Com internet responde "versão mais recente" | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Não congela a janela | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Offline não trava | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Observações | |

---

## V8 — Integridade dos dados: salvar e configuração (N1, N3)

**Objetivo.** Provar as duas rotas de perda de dados que não estavam na auditoria
original. **N1:** salvar `.printnest` não era atômico — uma interrupção destruía
o arquivo novo **e** o anterior. **N3:** um `config.json` corrompido impedia o app
de abrir **para sempre**, sem nenhuma mensagem (com `console=False` o cliente via
o programa "abrir e fechar").

**Pré-requisitos.** App fechado no início. Bloco de Notas.

**Passos.**
1. Abra o app, monte um projeto qualquer e salve com `Ctrl+S`.
2. Feche o app.
3. Abra `%APPDATA%\PrintNest\config.json` no Bloco de Notas.
4. **Apague metade do conteúdo** (deixe o JSON quebrado) e salve.
5. Abra o app de novo.
6. Confira a pasta `%APPDATA%\PrintNest`: deve existir um `config.json.corrompido`.
7. Reabra o projeto salvo no passo 1 (`Ctrl+O`).

**Resultado esperado.**
- Passo 5: o app **abre normalmente**, com as configurações padrão.
- Passo 6: o arquivo quebrado foi preservado como `.corrompido` e um
  `config.json` novo foi criado.
- Passo 7: o projeto abre íntegro.

| Registro | |
|---|---|
| App abre com config corrompido | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Arquivo quebrado preservado | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Projeto reabre íntegro | ☐ ✔ Aprovado ☐ ❌ Reprovado |
| Observações | |

---

## CRITÉRIO OBJETIVO DE APROVAÇÃO DO A3

O A3 está **APROVADO** quando **todas** as três condições abaixo forem
verdadeiras:

1. **Zero ❌ em V1, V5, V6, V7 e V8.** São as validações de perda de trabalho
   (C3, C7, C8), saída errada (H13a), canal de entrega (C6) e integridade de
   dados (N1, N3). Qualquer reprovação aqui **interrompe** o lançamento e volta
   para classificação do Release Manager.

2. **Zero ❌ em V2.** As duas telas precisam caber. Um ❌ aqui é bloqueador
   comercial: o Modo Corte é o que a macro do Corel abre, e a Ativação é a
   primeira tela do produto pago.

3. **V3 e V4 sem ❌, ou com ❌ acompanhado de decisão registrada do dono.**
   São itens de percepção visual. Se a aparência do CTA em preset claro
   incomodar, é decisão comercial do Philipe, não defeito — registre a decisão
   no campo Observações em vez de reprovar.

**Não é critério de aprovação:** o H15 (resposta offline), o H1 (nitidez dos
ícones em alta escala), o H19 (Yes/No em inglês nos diálogos padrão do Qt) e o
H22 (acentos faltando) — todos classificados para a **1.0.1**. Se aparecerem
durante o roteiro, anote em Observações e siga.

---

## FECHAMENTO

| | |
|---|---|
| Validações aprovadas | ______ de 8 |
| Validações reprovadas | ______ |
| Bloqueadores encontrados | ______ |
| **Veredito do A3** | ☐ APROVADO — liberar o A4 ☐ REPROVADO — voltar para classificação |
| Assinatura / data | |

**Observações gerais da sessão:**

```
(espaço para anotações livres — o que chamou atenção, mesmo fora do roteiro)
```

---

## O QUE VAI PARA O A4 (não executar agora)

Registrado aqui só para não se perder. **Depende do executável compilado:**

- **A4a — prova do mutex (H7).** Com o `.exe` **aberto**, rodar o instalador
  recém-gerado por cima: o Inno Setup tem que detectar o app e pedir para
  fechar; fechando, a instalação prossegue. Sem este passo o H7 está entregue
  pela metade.
- **A4b — prova do C6 no binário.** Abrir o `.exe` compilado com rede: a
  inicialização não pode travar nem exibir aviso de atualização. O silêncio é o
  comportamento correto e precisa ser observado no binário real.
- **Ativação bloqueante.** Primeira execução sem licença: o diálogo bloqueia e
  fechar = sair. Só acontece com `sys.frozen`.
- **Conteúdo do pacote (H24).** Conferir que `PrintNest_Build\Plugin CorelDRAW\
  imagens\` chegou com os **7** PNGs — é a única mudança do lote que só aparece
  depois do build.
- **Pós-A4:** descartar e reemitir as licenças de teste presas ao fingerprint
  antigo (decisão A1 do dono).
