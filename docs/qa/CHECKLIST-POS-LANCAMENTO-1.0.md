# Checklist operacional pós-lançamento — PrintNest Pro 1.0.0

Da aprovação da release até o produto estar de pé na mão do primeiro cliente
pagante. **Nada aqui é código** — são as condições para a entrega funcionar.

Release aprovada em 30/07/2026 · commit `0f72bc5` · build
`SHA-256 2A49367B…6DA2DE`

---

## BLOCO A — Antes de vender a primeira licença

Ordem obrigatória. O A1 é o mais importante: a régua de emissão mudou.

- [ ] **A1. Descartar a licença de teste.** A licença ativada durante o A4
      (`TESTE A4 - Philipe (validacao RC 1.0)`, máquina
      `PN-AQHN-23SR-U847-QG34`) é de validação. Desativar em
      **Ajuda → Licença → Desativar**.
- [ ] **A2. Confirmar o fingerprint no robô.** Rodar
      `tools\iniciar_robo_licencas.bat` e conferir que ele emite para o
      `machine_id` **sem MAC**. Toda licença de teste emitida antes de 30/07
      está inválida — reemitir para quem tiver.
- [ ] **A3. Emitir uma licença real de ponta a ponta**, para você mesmo, numa
      máquina limpa: ID → e-mail → chave → ativar → abrir → fechar → reabrir sem
      pedir de novo. É o ensaio geral do fluxo que todo cliente vai viver.
- [ ] **A4. Testar o código de compra já usado em outro PC**: tem que recusar
      com orientação, não com erro cru.
- [ ] **A5. Guardar a chave privada.** `tools\license_private_key.pem` só existe
      na sua máquina e está fora do Git. **Perder esse arquivo significa não
      conseguir emitir mais nenhuma licença, nunca.** Cópia em pendrive ou cofre
      offline — **nunca** em nuvem sincronizada com a pasta do projeto.

---

## BLOCO B — Publicação

- [ ] **B1. Definir onde o instalador fica hospedado** e testar o download num
      navegador anônimo, de outra rede.
- [ ] **B2. Instrução do SmartScreen na página de venda e no e-mail de entrega.**
      **Obrigatório, não opcional.** O aviso azul aparece *antes* de o cliente
      abrir o pacote, então a explicação que está dentro do zip chega tarde.
      Texto sugerido:
      > Ao abrir o instalador, o Windows pode mostrar um aviso azul dizendo que
      > "protegeu seu computador". Clique em **Mais informações** e depois em
      > **Executar assim mesmo**. Esse aviso aparece em todo programa novo — o
      > PrintNest é seguro.
- [ ] **B3. Arquivar o instalador** `PrintNest-Setup-1.0.0.exe` com o hash
      registrado, em local que não seja apagado.
- [ ] **B4. Criar a tag git da versão:**
      ```
      git tag -a v1.0.0 -m "PrintNest Pro 1.0.0 - primeira versao comercial"
      git push origin v1.0.0
      ```
- [ ] **B5. Entregar as notas ao cliente.** `RELEASE-NOTES-1.0.0.md` e
      `PROBLEMAS-CONHECIDOS-1.0.0.md` (em `docs/cliente/`) devem chegar junto do
      produto — no zip, no e-mail ou na página. Cliente que sabe o que esperar
      abre menos chamado.
- [ ] **B6. Conferir o site de vendas** contra a realidade da 1.0.0: preço,
      nome "PrintNest Pro", o que o produto faz, requisitos, forma de entrega.
      Nada do que a landing promete pode faltar no produto.

---

## BLOCO C — O canal de atualização (a apólice de seguro)

O canal está no ar e respondendo. Estas regras existem para ele continuar assim.

- [ ] **C1. Registrar as regras permanentes do Gist** onde você as encontre
      daqui a um ano:
      - **nunca** apagar a conta `Philipe91` do GitHub
      - **nunca** apagar o Gist `00110a87efa02d4256ea0755ac621236`
      - **nunca** renomear o arquivo `manifesto.json`
      - o nome do arquivo faz parte da URL, e a URL está gravada dentro do
        `.exe` de **todo cliente da 1.0.0**, sem correção remota possível
- [ ] **C2. Confirmar que o manifesto está em `versao: 1.0.0`** e continua assim
      até a 1.0.1 estar publicada. Anunciar antes = mandar o cliente para um
      link morto.
- [ ] **C3. Lembrete do placeholder.** O campo `url` está com
      `TROCAR-PELO-LINK-REAL-NA-1.0.1`. Só é inofensivo enquanto a versão do
      manifesto for igual à instalada.
- [ ] **C4. Ordem obrigatória na 1.0.1:** publicar o instalador **primeiro**,
      baixar você mesmo para confirmar, e **só então** editar o manifesto.

---

## BLOCO D — Cobertura que ficou faltando

As duas maiores lacunas da validação. Fecham juntas, num único teste.

- [ ] **D1. Executar o `TESTE-PC-NOVO.md` numa máquina de terceiro**, sem
      Python, sem o projeto. Toda a validação da 1.0 foi feita numa máquina só.
- [ ] **D2. Que essa máquina tenha CorelDRAW instalado.** O caminho
      "Enviar p/ Corel" (ponte COM) **nunca foi exercido** — nem no A3, nem no
      A4. É a vitrine do produto para o público que usa Corel e está sem
      cobertura real.
- [ ] **D3. Fechar o ciclo com material de verdade:** mandar um PDF de impressão
      para o RIP e um DXF para a mesa de corte. Nenhum arquivo gerado foi
      impresso ou cortado — foram validados como arquivos, não como produção.
- [ ] **D4. Conferir as marcas de registro no equipamento real.** Está
      registrado como pendência que elas saem em RGB(0,0,0) e não em K puro:
      confirmar se o leitor da máquina enxerga.

---

## BLOCO E — Primeiros dias

- [ ] **E1. Preparar as respostas dos 3 chamados mais prováveis**, na ordem de
      frequência prevista:
      1. **SmartScreen** ("não abre / deu vírus") — resposta pronta do B2
      2. **Ativação** — ID × código de compra, licença que "some", MAC mudou
      3. **"Está borrado"** em notebook a 150% — explicar e informar que a 1.0.1
         corrige
- [ ] **E2. Pedir o `crash.log` em todo relato de fechamento inesperado.**
      Fica em `%APPDATA%\PrintNest\logs`. A correção do C2 mirou a causa
      **provável** do crash `0xc0000374`, não a confirmada: se voltar, esse
      arquivo é a única pista.
- [ ] **E3. Anotar todo chamado**, mesmo o resolvido em um minuto. A frequência
      real vai reordenar o plano da 1.0.1 melhor que qualquer previsão.
- [ ] **E4. Manter o congelamento.** Toda solicitação nova entra classificada:
      **Hotfix 1.0.1** · **Versão 1.1** · **Backlog**. Nada entra direto.

---

## BLOCO F — Gatilhos de hotfix imediato

Situações em que a 1.0.1 deixa de ser planejada e vira emergência.

| Gatilho | Ação |
|---|---|
| Cliente relata perda de projeto | **Parar tudo.** Pedir o `.printnest`, o `crash.log` e o passo a passo. É o cenário de reembolso |
| Dois ou mais relatos de fechamento sozinho | O C2 não pegou a causa. Investigar com os `crash.log` antes de qualquer outra coisa |
| Cliente não consegue ativar após 2 tentativas com suporte | Pode ser o fingerprint. Coletar `machine_id` antes e depois |
| Programa não abre em máquina limpa | Cenário raro e fatal (era o N3). Pedir `%APPDATA%\PrintNest\config.json` e verificar se existe `.corrompido` ao lado |
| Canal de atualização fora do ar | Verificar o Gist imediatamente. Sem ele, nenhum hotfix chega |

---

## Encerramento

Quando os blocos A, B e C estiverem completos, a 1.0.0 está **operacionalmente
lançada**. D e E correm em paralelo com as primeiras vendas.

O status desta lista deve ser revisto na abertura da 1.0.1 — o que sobrar aqui
entra no escopo dela.
