# Prompt para abrir uma conversa nova — 03/08/2026

Cole o bloco abaixo numa conversa nova do Claude Code, dentro de
`c:\projetos\Cutph`.

---

```
Estou continuando o PrintNest Pro. Antes de responder qualquer coisa, leia:

  docs/produto/ESTADO-2026-07-31-FIM-DO-DIA.md   (o dia do lançamento da 1.0.1)
  docs/qa/CHECKLIST-POS-LANCAMENTO-1.0.md        (operação pendente)
  CHANGELOG.md                                    (o que já saiu)

CONTEXTO CURTO

PrintNest Pro: software desktop Windows (Python + PySide6, PyInstaller onefile,
instalador Inno Setup) para preparação de produção gráfica — encaixe de peças na
chapa, faca de corte, Modo Corte para laser/CNC, exportação PDF e DXF, plugin do
CorelDRAW. Produto EM PRODUÇÃO. Branch de trabalho: release/1.0.1.

COMO VOCÊ DEVE TRABALHAR

Atue como FableBoss (skill em ~/.claude/skills/fableboss): você é o executor; o
arquiteto é um subagente com modelo "fable" que decide sobre resumos e
evidências — nunca mande o projeto inteiro para ele. Ele caiu várias vezes com
erro 529 em 03/08; se cair, escreva o plano você mesmo e diga claramente que é
seu, não dele.

Toda solicitação nova é CLASSIFICADA antes de virar código: Hotfix / Versão
seguinte / Backlog / Rejeitar, com justificativa, impacto, riscos e prioridade.
Só implemente depois da minha aprovação explícita.

O que tem segurado a qualidade: escopo com LISTA FECHADA DE ARQUIVOS por etapa,
prova medida antes de mexer (sonda de pixel), e aprovação visual minha no app
rodando do código-fonte antes de qualquer build.

O QUE JÁ ESTÁ FEITO

- 1.0.1 LANÇADA e entregue pelo canal de atualização (primeira vez que uma
  versão chegou ao cliente sozinha). Ícones nítidos em 125-150% e botão Modo
  Corte destacado.
- 1.0.2 CORRIGIDA MAS NÃO EMPACOTADA: impressão saía girada/espelhada. Duas
  causas independentes, as duas provadas com sonda de pixel. Já validei no app.
- ESPELHAR (1.1) implementado e aprovado por mim no app: botões na barra, menu
  do botão direito, Ctrl+Shift+H / Ctrl+Shift+V, pergunta de escopo para PDF
  multipágina, e pergunta se a faca espelha junto com a arte.
- Suíte: 1024 testes, 0 falhas, 5 skips.

TAREFA DE AGORA: BATERIA DE TESTES

A última bateria completa foi na release 1.0. Depois dela entraram: ícones com
DPI, botão Modo Corte, duas correções de exportação e o espelho inteiro.

E eu vi DOIS BUGS que quero investigados primeiro:
  1. algo errado ao apertar DELETE
  2. algo errado no CTRL+Z

Atenção: pode ser regressão do trabalho de 03/08. O snapshot de desfazer ganhou
dois campos novos (_piece_mirrors e _piece_faca_mirrors) e o _delete_selected
nunca limpou os estados por peça. Também existe um defeito JÁ DIAGNOSTICADO e
não corrigido: excluir uma peça da chapa e rearrastar o mesmo arquivo da
biblioteca traz de volta a faca e o giro antigos — o estado por caminho de
arquivo (_file_overrides, _faca_manual, _piece_rotations) não é limpo. Decisão
pendente entre (A) limpar quando a última peça do arquivo sai, com Ctrl+Z
devolvendo, e (B) um botão "Recomeçar este arquivo". Eu prefiro a A.

Quero a bateria cobrindo pelo menos: excluir peça, excluir a última peça,
excluir e rearrastar, Ctrl+Z/Ctrl+Y em sequência e intercalados com girar e
espelhar, salvar/abrir projeto com espelho, e exportação PDF+DXF conferindo que
a faca cai sobre a arte.

FATOS QUE NÃO ESTÃO ÓBVIOS NO CÓDIGO

1. A SUÍTE NÃO SE AUTO-REPORTA. O processo morre no teardown e o código de
   saída mente. Vale a soma dos XML do junit, e tests/presentation trava se
   rodada como pasta — tem que ser arquivo a arquivo:

   New-Item -ItemType Directory -Force reports | Out-Null
   .venv\Scripts\python.exe -m pytest tests --ignore=tests\presentation -q --junit-xml=reports\core.xml
   foreach ($f in Get-ChildItem tests\presentation\test_*.py) {
     $xml = "reports\" + $f.BaseName + ".xml"
     .venv\Scripts\python.exe -m pytest $f.FullName -q --junit-xml=$xml
   }
   .venv\Scripts\python.exe reports\somar.py

   Monte a variável $xml ANTES: o PowerShell não expande --junit-xml=(...).

2. A GUI abre com `.venv\Scripts\python.exe -m app.presentation` (o `-m app` é
   só bootstrap e sai sem janela). O app tem TRAVA DE INSTÂNCIA ÚNICA: se já
   houver uma janela aberta, a nova é recusada em silêncio e você acha que
   abriu quando não abriu. Confira que a janela subiu antes de pedir teste.

3. ORDEM CANÔNICA DO ESPELHO: espelhar primeiro, girar depois. Implementada só
   em `crop_and_rotate_contour` e travada por teste com um caso onde as duas
   ordens divergem. Cinco consumidores dependem dela: faca, arte na impressão,
   preview do canvas, estado por peça e o DXF (que herda o contorno pronto).
   Se dois divergirem, a faca sai fora da arte.

4. O botão "espelhar horizontal" espelha horizontalmente NA TELA (como no
   Corel). Numa peça a 90/270 o eixo interno aparece trocado, e o handler
   converte H<->V antes de gravar (`_eixo_na_tela`).

5. Escala negativa na matriz de encaixe da impressão só pode nascer de um
   pedido EXPLÍCITO de espelho, nunca de uma caixa de página mal ordenada —
   quem garante isso é `bbox_normalizada`. Há teste nos dois sentidos.

6. Teste de geometria de tela precisa aplicar `theme.apply()` ANTES de medir;
   sem o QSS a medição erra de 28 a 117 px.

7. O app reabre o último projeto ao iniciar (campo `last_project` do
   %APPDATA%\PrintNest\config.json). Isso é local: máquina de cliente abre
   vazia, e o pacote da build não leva nenhum projeto.

DECISÕES PENDENTES, MINHAS

- Construir a 1.0.2 a partir do commit 51c8ff4 (só as correções) ou publicar
  tudo junto como 1.1? A branch hoje diz "1.0.2" no código mas já carrega o
  espelho, que é 1.1.
- O defeito do rearrastar: opção A ou B (acima).

PENDÊNCIAS QUE NÃO SÃO CÓDIGO E ESTÃO ABERTAS

1. INCIDENTE DE SEGURANÇA de 31/07. O repositório Philipe91/CutSave é PÚBLICO e
   um commit de logs de conversa expôs uma chave de API do 21st.dev, códigos de
   compra e e-mails de clientes. A chave privada de licenciamento NUNCA foi
   versionada (essa está a salvo). Já feito: docs/conversas saiu do
   versionamento, entrou no .gitignore e o hook passou a gravar em
   ~/PrintNest-conversas. FALTA, e é meu: deixar o repositório privado, revogar
   a chave do 21st.dev, remover do GitHub a branch que carrega o commit dos
   logs, e gerar códigos de compra novos.
2. Guardar tools\license_private_key.pem FORA desta máquina. Perder = nunca
   mais emitir licença, nem para quem já pagou.
3. Reemitir 3 licenças que quebraram com a mudança do fingerprint em 30/07.
4. Desativar a licença de teste desta máquina (Ajuda > Licença > Desativar).
5. Rodar o TESTE-PC-NOVO.md numa máquina de terceiro, de preferência com
   CorelDRAW — o caminho "Enviar p/ Corel" nunca foi exercido.

Não empacote nada sem eu aprovar. Comece investigando os bugs do Delete e do
Ctrl+Z.
```

---

## Notas para o Philipe (não colar)

**Por que a bateria agora.** Os dois bugs que você viu são no Delete e no
Ctrl+Z — a área exata que mudou hoje. O snapshot de desfazer ganhou dois campos
e o Delete nunca limpou estado por peça. Se for regressão de hoje, é barato
consertar agora; se for antigo, entra na fila com o defeito do rearrastar.

**O que eu faria primeiro se fosse você:** deixar o repositório privado e
revogar a chave. São dois cliques e resolvem o único problema desta semana que
piora sozinho com o tempo.
