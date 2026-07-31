# Prompt para abrir uma conversa nova

Cole o bloco abaixo numa conversa nova do Claude Code, dentro da pasta
`c:\projetos\Cutph`. Ele dá todo o contexto necessário e já define a próxima
tarefa: **testar o canal de atualização 1.0.0 → 1.0.1**.

---

```
Estou continuando o trabalho no PrintNest Pro. Leia estes três documentos antes
de responder qualquer coisa:

  docs/qa/RELATORIO-FINAL-RELEASE-1.0-2026-07-30.md   (o que foi validado)
  docs/qa/CHECKLIST-POS-LANCAMENTO-1.0.md             (o que falta fazer)
  docs/qa/PLANO-1.0.1.md                              (a fila da próxima versão)

CONTEXTO CURTO

O PrintNest Pro 1.0.0 foi lançado em 30/07/2026. É um software desktop Windows
(Python + PySide6, empacotado com PyInstaller, instalador Inno Setup) para
preparação de produção gráfica: encaixe de peças na chapa, faca de corte,
Modo Corte para laser/CNC, exportação PDF e DXF, plugin do CorelDRAW.

O produto está EM PRODUÇÃO e o congelamento de código está ATIVO.

COMO VOCÊ DEVE TRABALHAR

Atue como FableBoss (a skill está em ~/.claude/skills/fableboss). Você é o
executor; o arquiteto é um subagente com modelo "fable" que decide sobre
resumos, diffs curtos e evidências — nunca mande o projeto inteiro para ele.

Nenhuma solicitação vira código direto. Toda solicitação nova precisa ser
classificada ANTES de qualquer implementação, em:
  - Hotfix 1.0.1
  - Versão 1.1
  - Backlog
  - Rejeitar

Junto da classificação, apresente: justificativa, impacto esperado, riscos e
prioridade. Só implemente depois da minha aprovação explícita.

Antes de aprovar qualquer alteração, responda as cinco perguntas: resolve um
problema real? existe evidência? vale o risco? pode esperar outra versão? existe
chance de regressão?

FATOS QUE VOCÊ PRECISA SABER E QUE NÃO ESTÃO ÓBVIOS NO CÓDIGO

1. O canal de atualização lê um Gist público:
   https://gist.githubusercontent.com/Philipe91/00110a87efa02d4256ea0755ac621236/raw/manifesto.json
   Essa URL está gravada dentro do .exe de todo cliente da 1.0.0 e NÃO tem
   correção remota. Nunca apagar a conta, nunca apagar o Gist, nunca renomear o
   arquivo manifesto.json. O campo "url" do manifesto ainda está com um
   placeholder ("TROCAR-PELO-LINK-REAL-NA-1.0.1").

2. A suíte NÃO se auto-reporta: o processo morre no teardown com 0xC0000005 e o
   código de saída mente. O resultado válido é a soma dos XML do junit. E
   tests/presentation trava se rodada como pasta — tem que rodar arquivo a
   arquivo:

   New-Item -ItemType Directory -Force reports | Out-Null
   .venv\Scripts\python.exe -m pytest tests --ignore=tests\presentation -q --junit-xml=reports\core.xml
   foreach ($f in Get-ChildItem tests\presentation\test_*.py) {
     $xml = "reports\" + $f.BaseName + ".xml"
     .venv\Scripts\python.exe -m pytest $f.FullName -q --junit-xml=$xml
   }
   .venv\Scripts\python.exe reports\somar.py

   Atenção: monte a variável $xml ANTES. PowerShell não expande
   --junit-xml=(...) e o pytest recusa o argumento com exit 4.
   Estado atual: 939 testes, 0 falhas, 0 erros, 5 skips.

3. Teste de geometria de tela precisa aplicar theme.apply() ANTES de medir. Sem
   o QSS a medição erra de 28 a 117 px e esconde o defeito que deveria pegar.

4. O fingerprint da licença não usa mais o MAC no Windows (só o MachineGuid).
   Toda licença emitida antes de 30/07 parou de funcionar. Três clientes de
   teste receberam chave em 29/07 e precisam de reemissão.

5. Já classificado para a Versão 1.1 (não reabrir): no preview do Modo Corte as
   curvas aparecem facetadas. Foi investigado e MEDIDO — o DXF exportado sai
   como B-spline suave; o facetado existe só na tela, porque _rings_path() usa
   lineTo. A correção aprovada é usar cubicTo com os mesmos cubic_segments() do
   exportador, com pré-requisito de mapear quem mais consome aquele
   QPainterPath.

TAREFA DE AGORA: TESTE DO CANAL DE ATUALIZAÇÃO

Quero provar que um cliente com a 1.0.0 instalada recebe o aviso de que existe a
1.0.1. É o teste de fogo do canal — se ele falhar, todo hotfix futuro vira
reinstalação manual, cliente por cliente.

O que eu tenho hoje:
  - PrintNest 1.0.0 instalado em C:\Program Files\PrintNest
  - o instalador validado em dist_installer\PrintNest-Setup-1.0.0.exe
  - o Gist no ar, anunciando versao 1.0.0 (por isso o app está em silêncio)

O que eu quero que você faça:
  1. Me explique o plano antes de executar, incluindo como voltar atrás.
  2. Conduza o teste: editar o manifesto para anunciar uma 1.0.1, abrir o
     PrintNest instalado e confirmar que o aviso aparece, que o botão de
     download abre o link certo, e que "não avisar sobre esta versão" funciona.
  3. IMPORTANTÍSSIMO: ao terminar, devolver o Gist para versao 1.0.0. Se ficar
     anunciando 1.0.1, qualquer cliente real é mandado para um link que não
     existe.
  4. Me diga o que fazer diferente no dia do lançamento real da 1.0.1 —
     principalmente a ordem entre publicar o instalador e editar o manifesto.

DEPOIS DO TESTE: DEIXAR A OPERAÇÃO ORGANIZADA

Terminado o teste do canal, quero a parte operacional em ordem. Trate cada item
abaixo como tarefa, me mostrando o estado atual antes de mexer em qualquer
coisa:

1. ROBÔ DE ATIVAÇÃO
   - Conferir se está rodando (tools\iniciar_robo_licencas.bat abre uma janela
     de console que precisa ficar aberta).
   - O intervalo de checagem está em 15 segundos (poll_seconds no
     tools\robot_config.json, que é segredo e fica fora do Git). Era 60s e a
     resposta demorava ~1min30; com 15s deve ficar em 30-45s. O que sobra é
     propagação do Gmail e não depende de nós.
   - Me diga se vale a pena deixar o robô subindo sozinho com o Windows, e como
     eu saberia que ele caiu. Hoje, se a janela fechar, ninguém percebe — e
     cliente que acabou de pagar fica sem chave.
   - Existe a opção de IMAP IDLE (resposta em 2-3s em vez de 30-45s). Já foi
     avaliado e NÃO foi feito porque a conexão fica pendurada e precisa de
     tratamento próprio de reconexão; o laço atual se recupera sozinho de queda
     de internet. Se for reabrir isso, tem que vir com vigia de reconexão.

2. LICENÇAS
   - Três pessoas receberam chave em 29/07, ANTES de o fingerprint mudar. As
     chaves delas não funcionam mais na 1.0.0:
       maquinadomau530@gmail.com     PN-UZTK-DU69-A4P5-6MVT  PNC-3F9N-BAYS
       vendas@nucleografico.com.br   PN-J7GQ-WLWM-DHC5-7LBW  PNC-8FNB-8R6F
       ngd.vendas1@gmail.com         PN-E2KD-M94T-A4HC-YSZZ  PNC-ZQ8X-SAHX
     Me ajude a escrever o e-mail avisando e explicando o que elas precisam
     fazer (abrir o app, copiar o ID novo, mandar com o mesmo código de compra).
   - Existe uma licença de teste ativada nesta máquina durante a validação
     ("TESTE A4 - Philipe (validacao RC 1.0)"). Precisa ser desativada em
     Ajuda > Licença > Desativar.
   - Dois códigos de compra novos foram gerados para o teste em outro PC:
     PNC-P9TK-ZWXX e PNC-EB28-SK57.
   - A chave privada tools\license_private_key.pem só existe nesta máquina e
     está fora do Git. Se ela sumir, nunca mais dá para emitir licença nenhuma.
     Me lembre de guardar cópia offline e me diga o jeito mais seguro.

3. ARQUIVOS E ENTREGA
   - docs/build/ARQUIVOS-DA-ENTREGA.md diz o que vai para o cliente e o que
     nunca pode sair daqui. Confira se continua verdadeiro.
   - A pasta PARA-LEVAR-NO-PENDRIVE\ tem o kit do teste em outro PC (instalador,
     plugin do Corel, documentos do cliente, roteiro em txt). Não é versionada.
   - O instalador validado (dist_installer\PrintNest-Setup-1.0.0.exe, o programa
     dentro dele tem SHA-256 2A49367B...6DA2DE) precisa de cópia arquivada fora
     da pasta do projeto: rodar build.bat apaga e refaz dist\ e PrintNest_Build\.

4. O QUE MAIS ESTIVER PENDENTE
   - Percorra o docs/qa/CHECKLIST-POS-LANCAMENTO-1.0.md comigo e me diga, item a
     item, o que já está feito e o que falta. Não marque nada como feito sem
     verificar de verdade.

Não altere código do aplicativo. O congelamento continua ativo.
```

---

## Notas para o Philipe (não colar, é só para você)

**Por que o teste importa tanto.** O canal de atualização foi validado como
"consegue ler o manifesto e ficar quieto quando está em dia". O que ainda NÃO
foi provado é o caminho que interessa: o app anunciar de fato uma versão nova e
o cliente conseguir baixar. Enquanto isso não for testado, a 1.0.1 é uma
promessa.

**O que você vai precisar ter em mãos:** acesso ao Gist para editar (é só abrir
gist.github.com logado).

**Cuidado principal.** Enquanto o Gist estiver anunciando 1.0.1, qualquer
cliente que abrir o PrintNest recebe o aviso. Hoje isso é inofensivo porque
ninguém comprou ainda — mas depois da primeira venda esse teste só pode ser
feito com o instalador da versão nova já publicado.

**Depois deste teste**, os próximos itens do checklist são: definir a hospedagem
do instalador, publicar a instrução do SmartScreen na página e no e-mail, e
rodar o teste em máquina de terceiro com CorelDRAW instalado.
