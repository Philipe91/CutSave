# RELATÓRIO FINAL DE RELEASE — PrintNest Pro 1.0.0

**Encerramento do A4 (Rebuild + Smoke Test).** Complementa o
`RELATORIO-EXECUTIVO-RC-1.0-2026-07-30.md` (A3). Juntos, os dois formam o
registro oficial da Release 1.0.

| | |
|---|---|
| **Versão liberada** | 1.0.0 |
| **Data** | 30 de julho de 2026 |
| **Branch** | `v1.3-redesign` |
| **Commit final** | `0f72bc5` — *docs(qa): checklist executavel da validacao manual A3* |
| **Commit do último código** | `1717043` — *fix(1.0): lote final do release candidate* |
| **Congelamento de código** | **ATIVO e respeitado** — nenhuma linha alterada durante o A4 |

---

## 1. ARTEFATOS GERADOS

| Artefato | Caminho | Tamanho |
|---|---|---|
| Executável | `PrintNest_Build\PrintNest.exe` | 119.071 KB |
| Pasta de distribuição | `PrintNest_Build\` | 21 arquivos em 3 níveis |
| Instalador | `dist_installer\PrintNest-Setup-1.0.0.exe` | 18 arquivos empacotados |
| Manual do cliente | `Tutor IA - PrintNest.pdf` | 544 KB, 4 páginas |
| Guia do plugin | `Plugin CorelDRAW\PLUGIN-CORELDRAW.pdf` + **7 imagens** | 341 KB + 249 KB |

### Hash do build

```
SHA-256  2A49367B388BFF6AF056716718CC81548F6C884A1059C444DA00A0D5E76DA2DE
```

**Verificado nos dois pontos:** o hash do `PrintNest.exe` em `PrintNest_Build\` e o
do `C:\Program Files\PrintNest\PrintNest.exe` **após a instalação** são idênticos.
O binário que chega ao cliente é bit a bit o que saiu do build.

| Carimbo | Valor |
|---|---|
| Build gerada em | 30/07/2026 13:56:19 |
| Empacotador | PyInstaller 6.21.0 (onefile, Windows x64) |
| Compilador do instalador | Inno Setup 6.4.3 |
| Runtime | Python 3.10 embarcado |

---

## 2. SUÍTE E TESTES

| Campo | Valor |
|---|---|
| **Suíte utilizada** | pytest via `--junit-xml`, soma de 14 arquivos XML |
| **Total de testes** | **939** |
| **Aprovados** | **934** |
| **Falhas** | **0** |
| **Erros** | **0** |
| **Skips** | **5** |

> A suíte não se auto-reporta: o processo morre no teardown com `0xC0000005` e o
> código de saída mente. O resultado válido é a soma dos XML. `tests/presentation`
> trava se executada como pasta — roda arquivo a arquivo.

**Validação manual A3:** 8 validações, 8 aprovadas, 0 reprovadas, 0 bloqueadores.
Detalhe em `RELATORIO-EXECUTIVO-RC-1.0-2026-07-30.md`.

---

## 3. RESULTADO DO SMOKE TEST

### 3.1 Pipeline completo no binário — **✔ APROVADO**

Executado **duas vezes**: no build (`PrintNest_Build\PrintNest.exe`) e no
**artefato instalado** (`C:\Program Files\PrintNest\PrintNest.exe`).

```
SELFTEST OK
  pecas=3  pdf=...\IMPRESSAO.pdf  dxf=...\CORTE.dxf  projeto=True  config=True
exit=0
```

Cobre a cadeia inteira dentro do executável congelado: importação → nesting →
exportação de PDF de impressão → exportação DXF de corte → gravação de projeto
`.printnest` → gravação de configuração.

### 3.2 Abertura do artefato instalado — **✔ APROVADO**

```
 0,8s   splash nativa do PyInstaller
11,7s   splash Qt do produto
14,9s   "PrintNest Pro v1.0.0 — projeto rdq.printnest"  (maximizada)
        Responding=True · RAM 160 MB · mutex presente
```

Abre **licenciado** (sem tela de ativação), restaura o último projeto, responde a
eventos e **não exibe nenhum aviso de atualização**. Fechamento pelo fluxo normal
(`WM_CLOSE`): encerrou limpo e **liberou o mutex**.

### 3.3 Verificação do canal de atualização (A4b) — **✔ APROVADO**

A consulta roda **a cada abertura** (o gatilho é o primeiro `showEvent` da janela,
3 s após aparecer — não é exclusivo da primeira execução). Com rede ativa e o
manifesto anunciando 1.0.0 contra 1.0.0 instalado, o comportamento correto é o
silêncio, e foi o observado: **nenhum diálogo, nenhum congelamento**.

Complementa a validação A3/V7, que exercitou o caminho real de código: resposta em
0,10 s com rede; `None` em 5,0 s (timeout) sem rota; e os três cenários de versão
(em dia → `None`, desatualizado → `Novidade`, futuro → `None`).

### 3.4 Verificação do mutex (A4a) — **✔ APROVADO**

**Lado do aplicativo:** com o app rodando, ambos os mutexes existem no sistema
(`OpenExisting` bem-sucedido em `PrintNestAppMutex` e `Global\PrintNestAppMutex`).
Após o fechamento, **liberados**.

**Lado do instalador** — evidência textual do log do Inno (`inno-comapp.log`):

```
2026-07-30 14:22:47.425  Defaulting to Cancel for suppressed message box (OK/Cancel):
                         O instalador detectou que o PrintNest Pro está
                         atualmente em execução.

                         Por favor feche todas as instâncias dele agora, então
                         clique em OK pra continuar ou em Cancelar pra sair.
2026-07-30 14:22:47.425  Got EAbort exception.
2026-07-30 14:22:47.425  Deinitializing Setup.
```

O instalador detectou o app em execução, avisou **em português** e abortou sem
tocar em arquivo nenhum (exit code 1 — com `/SUPPRESSMSGBOXES` o padrão é Cancelar).

Era o risco **R2** do relatório do A3, classificado como **Alto** e o único que
ainda exigia execução. **Está fechado.**

---

## 4. RESULTADO DA INSTALAÇÃO — **✔ APROVADO**

Máquina sem instalação prévia (registro e `C:\Program Files\PrintNest` ausentes no
início).

| Verificação | Resultado |
|---|---|
| Instalação limpa | concluída (assistente completo, 14:17) |
| Instalação silenciosa com app fechado | exit code **0** |
| `RestartManager` | *"found no applications using one of our files"* |
| Nome exibido | **PrintNest Pro** |
| Versão exibida | 1.0.0 |
| Editor | **PrintNest — Philipe Fernandes** |
| Local | `C:\Program Files\PrintNest\` |
| Desinstalador | `unins000.exe` registrado |

**Atalhos criados:**
- `Menu Iniciar\PrintNest Pro\PrintNest Pro.lnk`
- `Menu Iniciar\PrintNest Pro\Tutor IA - PrintNest (PDF).lnk`
- `Menu Iniciar\PrintNest Pro\Desinstalar PrintNest Pro.lnk`
- `Área de Trabalho Pública\PrintNest Pro.lnk`

O atalho do Tutor IA aponta para um arquivo que **existe** — era o R3 do plano de
build (`build.bat` sem validação de extras), verificado na prática.

---

## 5. RESULTADO DA ATUALIZAÇÃO SOBRE INSTALAÇÃO EXISTENTE — **✔ APROVADO**

Instalador rodado **por cima** da instalação recém-feita:

```
exit code do upgrade: 0
RestartManager found no applications using one of our files.
Will append to existing uninstall log: C:\Program Files\PrintNest\unins000.dat
Dest file exists. → Installing the file. → Successfully installed the file.
```

Substituiu os arquivos, manteve um único registro de desinstalação (append no
`unins000.dat`, sem duplicar entrada no Painel de Controle) e terminou limpo.

**Licença preservada:** o `.iss` não remove `%APPDATA%\PrintNest` — o
`license.key` sobreviveu às três execuções do instalador.

---

## 6. VALIDAÇÃO DAS LICENÇAS — **✔ APROVADO**

| Verificação | Resultado |
|---|---|
| Fingerprint novo (H4) | `PN-AQHN-23SR-U847-QG34` |
| Licença antiga (03/07, com MAC) | **`UNLICENSED`** — invalidada, como previsto na decisão A1 |
| Reemissão para o ID novo | concluída, perpétua, edição `pro` |
| Ativação | `True` — *"Licença ativada para TESTE A4 - Philipe"* |
| Gravação em disco (H3) | `license.key` **282 bytes**, carimbo 30/07 14:13:36 |
| Chave malformada | recusada com *"Chave de licença inválida (formato não reconhecido)"* |
| Sem licença: fluxo bloqueante | diálogo **"Ativação do PrintNest"** abre e bloqueia |
| Fechar a ativação | encerra o programa (2 processos → 0) |

**Tela de ativação no binário real** (captura em `docs/qa/evidencias/`), fontes e
DPI reais:
- ID da máquina exibido: `PN-AQHN-23SR-U847-QG34`
- Numeração dos passos: **1 → 2 → 3 → 4** (H25 corrigido, confirmado no binário)
- CTA azul com texto branco legível (C10)
- Botão **"Sair"** no modo bloqueante
- Janela 536×568 px incluindo a barra de título

**Pendência operacional:** a licença ativada é de teste
(`TESTE A4 - Philipe (validacao RC 1.0)`). Deve ser descartada e reemitida em nome
real antes de qualquer venda — e este é o momento em que o fingerprint sem MAC
passa a ser o padrão definitivo de emissão.

---

## 7. VALIDAÇÃO DO PACOTE ENTREGUE AO CLIENTE — **✔ APROVADO**

Conferência item a item do que o `LEIA-ME.txt` promete contra o que existe na
pasta instalada:

| Prometido no LEIA-ME | Existe |
|---|---|
| `PrintNest.exe` | ✔ |
| `LEIA-ME.txt` | ✔ |
| `Tutor IA - PrintNest.pdf` | ✔ |
| `VERSAO.txt` | ✔ |
| `README.txt` | ✔ |
| `Plugin CorelDRAW\` | ✔ |
| `Plugin CorelDRAW\PLUGIN-CORELDRAW.pdf` | ✔ |

**As 7 imagens do guia do Corel chegaram** — era a única correção do lote (H24) que
só podia ser verificada depois do build:

```
imagens\01-abrir-personalizacao.png    imagens\05-modo-corte-organizando.png
imagens\02-filtro-macros.png           imagens\06-enviar-para-corel.png
imagens\03-arrastar-botao.png          imagens\07-popup-duas-opcoes.png
imagens\04-aparencia-logo.png
```

Antes desta correção, o `GUIA-CLIENTE.txt` chegava ao cliente com **7 referências
quebradas**.

**Demais itens do H24 verificados no pacote final:** `VERSAO.txt` diz
*"PrintNest Pro"* e carimba a data/hora real da build; `LEIA-ME.txt` não diz mais
*"obrigado por testar"* e aponta para o Tutor IA que de fato está na pasta;
`instalar_plugin_corel.bat` ensina `PrintNest.PrintNestMenu`, alinhado com o guia;
`README.txt` lista as **7** opções reais de registro e manda clicar em
*"Colocar na chapa"*, que é o botão que existe na tela.

---

## 8. RISCOS REMANESCENTES

R2 (mutex) saiu da lista — **fechado nesta rodada**. O que permanece:

| # | Risco | Classificação | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|---|
| R1 | Gist/conta do GitHub apagada ou renomeada — a URL está gravada no `.exe` e não há correção remota | **Alto** | Baixa | Crítico se ocorrer | Regra no fonte: nunca apagar a conta, nunca apagar o Gist, nunca renomear `manifesto.json`. Builds futuras migram para o domínio; o Gist segue servindo a 1.0.0 |
| R3 | **SmartScreen** — sem assinatura digital | **Alto** | **Alta** | Ticket "não abre / deu vírus" na primeira hora | **Obrigatório:** instrução "Mais informações → Executar assim mesmo" na página e no e-mail de entrega. Certificado EV depois |
| R4 | Placeholder no campo `url` do manifesto | **Alto** | Média | Cliente avisado de versão que não baixa | Lembrete dentro do próprio campo (`TROCAR-PELO-LINK-REAL-NA-1.0.1`); publicar o instalador **antes** de editar o manifesto |
| R5 | Excepthook com modal reentrante | **Médio** | Baixa | Comportamento imprevisível numa situação que já é de erro | Avisa uma vez por sessão, tudo sob `suppress` |
| R6 | Ativação a 150% em 1366×768 | **Médio** | Baixa | Cliente nessa configuração não ativa | Medida real: janela 568 px contra ~574 úteis a 125% (cabe, com ~6 px) e ~472 a 150% (não cabe). 1.0.1 |
| R7 | Ícones sem devicePixelRatio | **Médio** | **Alta** | Percepção "amadora" em 125–150% | 1.0.1. Sem perda funcional |
| R8 | Corel e exportações síncronos | **Médio** | Média | "Não respondendo" em operação pesada | Wait cursor já existe. 1.0.1/1.1 |
| R9 | Resposta offline igual a "em dia" | **Baixo** | Média | Informação imprecisa | 1.0.1 |
| R10 | Yes/No em inglês e ~30 strings sem acento | **Baixo** | Alta | Acabamento | 1.0.1, passada única de i18n |
| R11 | Sem autosave | **Baixo** | Baixa | Crash perde desde o último Ctrl+S | 1.1 |

**Nenhum risco Crítico aberto.** Dos três Altos, R3 é o único com alta
probabilidade — e a mitigação é textual, fora do código.

---

## 9. LIMITAÇÕES CONHECIDAS

Declaradas para que ninguém confunda escopo validado com escopo total:

1. **Uma única máquina.** Windows 10 Pro 19045, x64, monitores 1920×1080 e
   2560×1080 a 100%. Não houve teste em máquina limpa de terceiro, em Windows 11,
   nem em notebook 1366×768 real. As telas apertadas foram validadas por geometria
   forçada e emulação de escala, não em hardware.
2. **Sem CorelDRAW instalado nesta máquina.** O caminho "Enviar p/ Corel"
   (`corel_bridge`, COM) **não foi exercido** em nenhuma fase. O plugin foi
   validado apenas como conteúdo de pacote.
3. **Sem assinatura digital.** O SmartScreen vai aparecer no primeiro download de
   todo cliente.
4. **Ativação exercida pelo `LicenseManager`, não pelo diálogo.** O fluxo
   bloqueante foi validado (aparece, bloqueia, fechar encerra), mas a digitação da
   chave e o clique em "Ativar" na interface não foram automatizados.
5. **Impressão real não testada.** PDF e DXF foram gerados e validados como
   arquivos; nenhum foi enviado a um RIP, plotter ou mesa de corte.
6. **Nesting congelado.** O motor de encaixe não foi tocado desde 22/07 por
   decisão anterior; o benchmark não foi reexecutado nesta rodada.
7. **Interação com o instalador elevado** exigiu execução manual: o UIPI do Windows
   impede um processo não elevado de ler ou controlar janelas elevadas. Os
   resultados vieram de códigos de saída e dos logs do Inno, não de inspeção de
   tela.

---

## 10. PLANO DA VERSÃO 1.0.1

Ordem sugerida, do maior retorno ao menor. **É o primeiro uso real do canal C6** —
e a prova de que ele funciona.

**Bloco 1 — o que o cliente vê primeiro**
- **H1** — ícones com `devicePixelRatio`. Maior ganho visual por esforço de toda a
  auditoria; hoje o app fica levemente borrado a 125–150%, que é o padrão em
  notebook 14" FHD. 2 arquivos, call sites não mudam.
- **H2 a 150%** — Ativação com `QScrollArea` no miolo (R6).
- **H19 + H22** — `qtbase_pt_BR.qm` no `.spec` + passada de acentos, num único
  bloco de i18n. Atenção: o `.qm` precisa entrar no `PrintNest.spec` e o
  `test_build_packaging` precisa ser estendido.

**Bloco 2 — feedback e honestidade da interface**
- **H15** — terceiro estado no update: "não consegui verificar" ≠ "está em dia".
- **H13b** — barra de progresso com total único, que zera ao terminar.
- **H14** — Desfazer/Refazer nascem cinza (`canUndoChanged`).
- **H16** — exceções cruas em inglês nos caminhos mais prováveis.

**Bloco 3 — performance percebida**
- **H8** — drop incremental (soltar PDF grande em produção montada).
- **H9** — "Páginas do PDF…" com miniaturas em lote.
- **H10** — "Enviar p/ Corel" em `QThread`. **Requer máquina com Corel real.**
- **H11** — exportação de imagem em worker com progresso por chapa.

**Bloco 4 — infraestrutura**
- Publicar o manifesto no domínio próprio quando ele existir; o Gist continua
  servindo a base 1.0.0 (R1).
- Hospedagem definitiva do instalador e troca do placeholder do campo `url` (R4).
- Certificado de assinatura de código (R3).

**Adiado para 1.1:** N2 (autosave/recuperação), M14 (teto de pixmap), M17 (vírgula
decimal), R5 (associação `.printnest`).

**Primeira ação da 1.0.1, antes de qualquer código:** publicar o instalador, editar
o Gist com `versao: 1.0.1` e o link real, e confirmar que um cliente 1.0.0 recebe o
aviso. É o teste de fogo do canal.

---

## 11. DECISÃO FINAL DE LANÇAMENTO

# ⚠ GO COM RESSALVAS

**Justificativa técnica.**

O A4 encerrou com **todos os itens de escopo aprovados** e nenhuma reprovação. O
artefato entregue foi verificado por hash em dois pontos e é bit a bit idêntico ao
que saiu do build. O pipeline completo roda dentro do executável congelado, em duas
localizações independentes. A instalação limpa, a atualização por cima e a detecção
do aplicativo em execução foram todas comprovadas por código de saída e log do
próprio instalador, não por impressão. O canal de atualização respondeu, e o R2 —
o único risco Alto que ainda exigia execução no relatório do A3 — está fechado.

Sobre a base: 939 testes verdes, 0 falhas, e 8 de 8 validações manuais aprovadas
sobre as 18 correções do release candidate. As rotas de perda de dados e de perda
de trabalho identificadas nas duas auditorias estão fechadas e verificadas com o
aplicativo real. A causa provável do crash `0xc0000374` foi eliminada, e o
`excepthook` garante rastro para o que sobrar.

**As ressalvas — todas com mitigação definida e nenhuma dependente de código:**

1. **SmartScreen é certeza** (R3, probabilidade Alta). A instrução "Mais
   informações → Executar assim mesmo" **precisa** estar na página de venda e no
   e-mail de entrega, não só dentro do pacote — o cliente encontra o aviso azul
   antes de abrir o zip.
2. **O canal de atualização vive num Gist pessoal** (R1). Apagar a conta, apagar o
   Gist ou renomear o arquivo derruba o canal de todos os clientes 1.0.0, para
   sempre e sem correção remota.
3. **Placeholder no manifesto** (R4). Trocar pelo link real é obrigatório no dia da
   1.0.1, e o instalador precisa estar publicado **antes** da edição.
4. **Validado numa máquina só.** Nenhum teste em máquina limpa de terceiro nem em
   notebook 1366×768 real. O `TESTE-PC-NOVO.md` continua sendo o roteiro certo para
   isso e permanece pendente.
5. **O caminho do CorelDRAW nunca foi exercido** — nem no A3, nem no A4. É a
   vitrine do produto para o público que usa Corel e está sem cobertura de teste
   real.

**Recomendação.** Lançar. Antes de divulgar, executar duas ações fora do código:
publicar a instrução do SmartScreen na entrega, e rodar o `TESTE-PC-NOVO.md` numa
máquina de terceiro — de preferência uma que tenha CorelDRAW instalado, que fecha
as duas maiores lacunas de cobertura de uma vez.

---

## 12. PENDÊNCIAS OPERACIONAIS ANTES DA PRIMEIRA VENDA

Não são código. São condições para a entrega funcionar.

- [ ] Descartar a licença de teste `TESTE A4 - Philipe (validacao RC 1.0)` e passar
      a emitir com o fingerprint sem MAC como padrão definitivo
- [ ] Confirmar que o robô de licenças (`tools/license_robot.py`) reflete o
      fingerprint novo
- [ ] Publicar a instrução do SmartScreen na página de venda e no e-mail de entrega
- [ ] Definir a hospedagem do instalador e trocar o placeholder do manifesto
- [ ] Arquivar `PrintNest-Setup-1.0.0.exe` com o hash registrado neste documento
- [ ] Criar a tag git da versão 1.0.0
- [ ] Executar o `TESTE-PC-NOVO.md` numa máquina limpa de terceiro

---

**Encerramento.** Este documento fecha o A4. A Release Candidate 1.0 só é
oficialmente encerrada — e a versão considerada pronta para lançamento — mediante
aprovação explícita do dono do produto.
