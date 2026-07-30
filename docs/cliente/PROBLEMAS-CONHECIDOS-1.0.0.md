# PrintNest Pro 1.0.0 — Problemas conhecidos

Lista honesta do que ainda não está redondo nesta versão, com a solução de cada
caso. Tudo aqui já está na fila de correção. Preferimos que você saiba de
antemão a descobrir sozinho no meio de um trabalho.

**Nenhum item desta lista causa perda de trabalho.**

---

## Na instalação

### O Windows diz que "protegeu seu computador"

**O que acontece:** ao executar o instalador, aparece uma tela azul do
SmartScreen dizendo que o aplicativo não é reconhecido.

**Por quê:** o instalador ainda não tem certificado de assinatura digital. O
Windows mostra esse aviso para todo programa novo, até ele acumular downloads
suficientes.

**O que fazer:** clique em **Mais informações** → **Executar assim mesmo**.

**Quando resolve:** quando o certificado de assinatura de código for adquirido.

---

### Atualizar com o PrintNest aberto

**O que acontece:** o instalador avisa que o PrintNest está em execução e pede
para fechá-lo.

**O que fazer:** feche o programa e clique em OK. É o comportamento correto —
instalar por cima de um programa aberto corromperia a instalação.

---

## Na tela

### O programa parece levemente desfocado

**O que acontece:** em telas configuradas a 125% ou 150% no Windows — o padrão
em notebooks de 14 polegadas Full HD — os ícones e algumas ilustrações saem
menos nítidos que o resto da interface.

**Por quê:** os ícones são desenhados no tamanho de uma tela 100% e ampliados
pelo Windows.

**O que fazer:** nada impede o uso. Se incomodar, configurar a tela em 100%
(Configurações → Sistema → Vídeo → Escala) deixa tudo nítido.

**Quando resolve:** é a **primeira** correção da versão 1.0.1.

---

### Tela de ativação não cabe em notebook pequeno com fonte grande

**O que acontece:** em notebooks 1366×768 configurados a **150%**, o botão
"Ativar" pode ficar abaixo da borda da tela.

**O que fazer:** mudar temporariamente a escala para 125% ou 100%
(Configurações → Sistema → Vídeo → Escala), ativar, e depois voltar. A 125% a
tela cabe normalmente.

**Quando resolve:** versão 1.0.1.

---

## No uso

### Algumas telas usam "Yes / No" e "OK / Cancel" em inglês

**O que acontece:** certas caixas de confirmação do Windows aparecem com botões
em inglês, no meio de um programa todo em português.

**Por quê:** são caixas padrão do sistema gráfico, ainda sem o pacote de
tradução embutido.

**O que fazer:** "Yes" é Sim, "No" é Não, "OK" confirma e "Cancel" cancela. As
caixas mais importantes — as que perguntam antes de descartar trabalho — **já
estão em português**.

**Quando resolve:** versão 1.0.1.

---

### Algumas palavras aparecem sem acento

**O que acontece:** cerca de trinta textos da interface estão sem acentuação
("PDF de impressao", "Girar 90 a esquerda").

**O que fazer:** nada, é só aparência.

**Quando resolve:** versão 1.0.1.

---

### "Procurar atualizações" sem internet responde como se estivesse tudo em dia

**O que acontece:** sem conexão, o programa responde *"Você já está na versão
mais recente"* em vez de avisar que não conseguiu verificar.

**O que fazer:** confira sua conexão antes de confiar na resposta.

**Quando resolve:** versão 1.0.1.

---

### Exportar arquivos grandes deixa a janela "parada"

**O que acontece:** ao exportar várias chapas em alta resolução, a janela pode
ficar sem responder por alguns segundos, e o Windows pode escrever "Não
respondendo" na barra de título.

**O que fazer:** **aguarde**. O trabalho está sendo feito e vai terminar
normalmente. Não force o fechamento.

**Quando resolve:** versão 1.0.1.

---

### "Enviar p/ Corel" com o CorelDRAW ocupado

**O que acontece:** se o CorelDRAW estiver com uma caixa de diálogo aberta ou
processando outra coisa, o PrintNest parece travado enquanto espera.

**O que fazer:** deixe o CorelDRAW sem nenhuma janela aberta esperando resposta
antes de usar o botão.

**Quando resolve:** versão 1.0.1.

---

### Digitar uma quantidade grande recalcula a cada dígito

**O que acontece:** ao digitar "150" no campo de quantidade, o encaixe é
recalculado em 1, depois 15, depois 150 — e pode demorar.

**O que fazer:** use as setinhas do campo, ou selecione o número inteiro antes
de digitar o novo.

**Quando resolve:** versão 1.0.1.

---

### Arquivos `.cdr` e `.svg` não entram por arrastar

**O que acontece:** arrastar um `.cdr` para a janela não faz nada.

**O que fazer:** no CorelDRAW, exporte como **PDF** (Ctrl+E) e arraste o PDF.
Arquivos `.svg` são usados no **Modo Corte**, não na produção de impressão.

**Quando resolve:** versão 1.0.1 dá uma mensagem explicando em vez de ignorar.

---

### Duplo clique num projeto `.printnest` não abre o programa

**O que acontece:** o Windows não sabe que os arquivos `.printnest` pertencem ao
PrintNest.

**O que fazer:** abra o PrintNest primeiro e use **Ctrl+O**, ou arraste o
arquivo para a janela aberta.

**Quando resolve:** em avaliação para a 1.0.1.

---

## Recuperação

### O programa fechou sozinho — e agora?

Seu último **Ctrl+S** está preservado: a gravação de projeto desta versão é
atômica, ou seja, um arquivo salvo nunca fica pela metade, mesmo que a máquina
desligue no meio.

Ainda **não existe salvamento automático** — o que foi feito depois do último
salvamento se perde. Salve com frequência. O salvamento automático está previsto
para a versão 1.1.

Se o programa fechar sozinho, o arquivo `crash.log` em
`%APPDATA%\PrintNest\logs` registra o que aconteceu. Mande esse arquivo para o
suporte: é o que permite corrigir o problema de verdade.

### O programa não abre de jeito nenhum

Confira no Gerenciador de Tarefas (Ctrl+Shift+Esc) se já existe um
**PrintNest.exe** em execução — pode ser uma janela minimizada ou num monitor
desconectado. O PrintNest permite uma instância por vez: abrir de novo apenas
traz a janela existente para a frente.

---

## Suporte

**philipe.fernandes0101@gmail.com**

Se encontrar algo que não está nesta lista, avise. Problema relatado é problema
que entra na fila; problema silencioso continua lá.
