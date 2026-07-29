# Teste em PC novo (simulando um cliente)

Roteiro para rodar numa máquina limpa, **sem Python, sem o projeto, sem nada
instalado**. É o único jeito de descobrir o que quebra só na mão do cliente.

Leve este arquivo junto (ou imprima). Marque o que passou.

---

## Antes de sair da sua máquina

- [ ] `build.bat` rodado **depois** da última alteração de código
- [ ] `PrintNest_Build\VERSAO.txt` mostra a data/hora de hoje
- [ ] Pasta `PrintNest_Build` inteira zipada
- [ ] **Robô de licenças rodando** na sua máquina (`tools\iniciar_robo_licencas.bat`),
      senão a ativação não responde e o teste trava no meio
- [ ] Um **código de compra** válido em mãos (`PNC-XXXX-XXXX`)
- [ ] Um PDF de arte real seu, para testar com arquivo de gráfica de verdade

---

## 1. Instalação

- [ ] Copiar o zip para o PC novo e extrair
- [ ] Dois cliques em `PrintNest.exe`

**O que provavelmente vai acontecer:** o Windows mostra
*"O Windows protegeu o computador"* (SmartScreen). É esperado em executável sem
certificado de assinatura de código. Clique em **Mais informações → Executar
assim mesmo**.

- [ ] Anote quanto tempo levou da primeira execução até a janela abrir
      (o `.exe` é único e se descompacta na primeira vez; costuma ser o momento
      mais lento e o cliente acha que travou)
- [ ] A tela de abertura (splash) apareceu?
- [ ] A janela abriu sem erro?

> **Decisão pendente:** todo cliente vai ver esse aviso do SmartScreen. Ou você
> compra um certificado de assinatura (não dá tempo em 2 dias e meio), ou avisa
> no e-mail de venda e no guia. Veja "Riscos conhecidos" no fim.

---

## 2. Licença (o caminho do cliente que acabou de comprar)

- [ ] O app pediu ativação ao abrir?
- [ ] Copiar o **ID da Máquina** (`PN-XXXX-XXXX-XXXX-XXXX`)
- [ ] Enviar o e-mail de ativação com o ID + o código de compra
- [ ] O robô respondeu? Em quanto tempo?
- [ ] Colar a chave recebida e ativar
- [ ] Fechar e reabrir: **continua ativado** (não pode pedir de novo)

---

## 3. Primeiro contato (é o que decide se o cliente entende sozinho)

- [ ] O tour de boas-vindas apareceu sozinho na primeira abertura
- [ ] **Tutoriais → Tutorial guiado**: o arquivo de exemplo carregou na biblioteca?
- [ ] Os passos mão na massa deixam clicar no controle certo e só avançam quando
      você faz?
- [ ] **Tutoriais → Modo Corte** e **Marcas de registro**: mostram onde clicar?

---

## 4. Trabalho de verdade (com o SEU arquivo, não o de exemplo)

- [ ] Arrastar um PDF de gráfica para a janela
- [ ] Soltar na chapa: o gesto responde na hora?
- [ ] Um PDF de **muitas páginas**: a janela continua respondendo enquanto gera?
- [ ] Gerar faca: sai acompanhando a arte?
- [ ] Um arquivo com **faca do cliente** (linha magenta): é reconhecida? A linha
      magenta some do preview?
- [ ] Marcas de registro: aparecem na chapa?
- [ ] **Exportar PDF de impressão** — abrir o arquivo e conferir
- [ ] **Exportar DXF** — abrir e conferir se o corte casa com a impressão
- [ ] Salvar um `.printnest`, fechar o app, reabrir e carregar: voltou igual?

---

## 5. Aviso de atualização (só se você já publicou o versao.json)

- [ ] **Ajuda → Procurar atualizações...** responde alguma coisa
- [ ] Publicando um `versao.json` com versão MAIOR, o aviso aparece
- [ ] "Abrir download" abre o navegador no link certo
- [ ] "Não avisar sobre esta": fecha e reabre, não aparece de novo

---

## 6. Coisas que só quebram em máquina limpa

- [ ] Máquina **sem Microsoft Office / sem CorelDRAW**: o app abre igual?
- [ ] Tela pequena (notebook 1366x768): a janela cabe? Os painéis ficam usáveis?
- [ ] Escala do Windows em **125% ou 150%**: o texto corta? Os botões somem?
- [ ] Windows em outro idioma, se tiver como testar
- [ ] Sem internet: o app abre normal e não trava esperando nada

---

## Se algo der errado

Pegue o log e mande para você mesmo:

```
%APPDATA%\PrintNest\logs\printnest.log
```

Anote também: o que você fez, o que esperava, o que aconteceu, e a versão em
`Ajuda → Sobre`.

---

## Riscos conhecidos que este teste NÃO cobre

- **SmartScreen / antivírus**: sem certificado de assinatura, o aviso aparece
  para todo cliente na primeira execução. Precisa estar escrito no e-mail de
  venda e no guia, senão vira chamado de suporte (ou desistência de compra).
- **Arrastar arquivo grande para produção já montada** ainda congela a janela
  (~15s com 60 páginas). O primeiro drop já foi resolvido; esse não.
- **Modo escuro** ainda tem partes claras fora do painel Documento.
- **Crash `0xc0000374`** já visto uma vez e nunca reproduzido. Se acontecer no
  teste, anote **exatamente** o que você fez antes — é a melhor chance de pegar.
