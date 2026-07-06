# Robô de Ativação — guia completo (para quando eu esquecer)

> **Resumo de 10 segundos:** o robô é um programa que roda **no meu PC**, lê a
> caixa de entrada de `ativacao.printnest@gmail.com` e responde sozinho com a
> chave de licença para quem mandar um **código de compra** válido. Eu só
> preciso: deixar o robô aberto e entregar um código por venda (dá do celular).
>
> Ligar o robô: **dois cliques em `tools/iniciar_robo_licencas.bat`**.

## Como funciona (o desenho todo)

```
EU (na venda)                 CLIENTE                          MEU PC (robô)
─────────────                 ───────                          ─────────────
1. Recebo o pagamento
2. Envio 1 código de compra ─▶ 3. Instala o PrintNest
   (PNC-XXXX-XXXX)               Abre → tela de Ativação
   * dá pra fazer do celular     Clica "Pedir minha chave
                                 por e-mail" (o app já põe
                                 o ID da máquina no e-mail)
                                 Cola o código e envia ──────▶ 4. Robô lê o e-mail
                                                                  Valida o código
                                                                  Assina a licença
                              6. Recebe a chave por  ◀───────── 5. Responde na hora
                                 e-mail, cola em Ativar
                                 → PrintNest liberado
```

- A **chave privada** (`tools/license_private_key.pem`) **nunca sai do meu PC** —
  por isso o robô roda aqui e não na nuvem (por enquanto).
- Se o meu PC estiver **desligado**, nada se perde: o pedido fica na caixa de
  entrada e é atendido quando o robô voltar a rodar.

## As peças

| Arquivo | O que é |
|---|---|
| `tools/license_robot.py` | o robô em si (lê IMAP, valida, assina, responde SMTP) |
| `tools/iniciar_robo_licencas.bat` | atalho para ligar o robô (deixar a janela aberta) |
| `tools/robot_config.json` | e-mail + **senha de app** do Gmail (SEGREDO, fora do Git) |
| `tools/gen_vouchers.py` | gera códigos de compra em lote |
| `tools/licenses_emitidas/vouchers.json` | os códigos e quem usou cada um (fora do Git) |
| `tools/licenses_emitidas/robo-log.jsonl` | registro de tudo que o robô fez |
| `app/licensing/__init__.py` → `ACTIVATION_EMAIL` | o endereço que vai DENTRO do app (botão "Pedir minha chave por e-mail") |

## Rotina do dia a dia

1. **Ligar o robô** (uma vez, ao ligar o PC): `tools/iniciar_robo_licencas.bat`.
   A janela mostra cada pedido tratado; Ctrl+C encerra.
2. **Ter códigos na mão** (quando acabarem):

   ```
   .venv\Scripts\python.exe tools/gen_vouchers.py -n 20 --note "lote agosto"
   ```

   Ele imprime os códigos novos — guardo a lista no celular para vender de
   qualquer lugar.
3. **Na venda:** cliente pagou → mando UM código (WhatsApp/e-mail). Só isso.

## Regras que o robô aplica sozinho

- Código é de **uso único** e fica preso ao **primeiro PC** que ativar.
- O **mesmo PC** pedindo de novo (cliente perdeu o e-mail) recebe a **mesma**
  chave de volta — sem gastar outro código.
- **Outro PC** com código já usado é **recusado** com orientação de suporte
  (troca de PC = Ajuda → Licença → Desativar no PC antigo + falar comigo).
- E-mail sem ID de máquina ou sem código recebe resposta explicando o que
  faltou. E-mails de robôs/bounces (no-reply, mailer-daemon) são ignorados.

## Configuração do zero (se eu trocar de PC ou de conta)

1. **Conta de e-mail dedicada**: `ativacao.printnest@gmail.com`
   (senha da conta no meu gerenciador de senhas).
2. **Verificação em duas etapas** na conta — sem ela o passo 3 não existe:
   `https://myaccount.google.com/signinoptions/twosv` → Ativar (celular + SMS).
3. **Senha de app** (16 letras, é o que o robô usa para logar):
   `https://myaccount.google.com/apppasswords` → nome "Robo PrintNest" → Criar.
   > O Google **esconde** essa página dos menus — ir direto pela URL acima.
4. Copiar `tools/robot_config.example.json` → `tools/robot_config.json` e
   preencher `email` e `app_password` (as 16 letras, com ou sem espaços).
5. Conferir que a **chave privada** está em `tools/license_private_key.pem`
   (restaurar do backup se for PC novo).
6. Ligar o robô e fazer um pedido de teste (mandar e-mail de outra conta com um
   ID `PN-...` e um código de teste).

Se um dia **trocar o endereço de e-mail**: mudar também a constante
`ACTIVATION_EMAIL` em `app/licensing/__init__.py` e **refazer o build** — o
endereço vai dentro do exe do cliente.

## Problemas comuns

| Sintoma | Causa provável / solução |
|---|---|
| Robô não loga ("authentication failed") | Senha de app errada ou revogada → gerar outra em `myaccount.google.com/apppasswords` e atualizar o `robot_config.json`. |
| Cliente diz que não chegou resposta | Robô está rodando? Janela aberta? Olhar `robo-log.jsonl`. Pedir para conferir o **spam**. |
| Cliente clicou no botão e "nada abriu" | Ele não tem programa de e-mail configurado → usar o botão **"Copiar pedido"** e colar no webmail/WhatsApp — mas o pedido precisa ir por E-MAIL para `ativacao.printnest@gmail.com` (o robô só lê e-mail). |
| "Código não reconhecido" | Digitou errado, ou o `vouchers.json` deste PC não tem o código (gerado em outro PC?) — o arquivo de vouchers vive junto do robô. |
| Preciso ativar na mão (robô parado) | Sempre dá: `tools/license_studio.py` (GUI) ou `tools/gen_license.py` (CLI) — e marcar o código como usado depois, pra não valer duas vezes. |

## Backup (IMPORTANTE — mesma pasta segura, pen drive/nuvem privada)

1. `tools/license_private_key.pem` — **o mais crítico**; sem ele não emito mais.
2. `tools/licenses_emitidas/` — vouchers e histórico do que foi emitido.
3. `tools/robot_config.json` — ou só lembrar que a senha de app se regenera
   no link do passo 3 acima.

## Segurança

- A **senha de app** dá acesso à conta de e-mail — se vazar, revogar na hora em
  `myaccount.google.com/apppasswords` (e gerar outra). Ela NÃO dá acesso à
  chave privada nem permite forjar licenças.
- O `robot_config.json` e a pasta `licenses_emitidas/` estão no `.gitignore` —
  **nunca** aparecem no GitHub. Se algum dia aparecerem: trocar a senha de app
  imediatamente.

## Futuro (quando for para a nuvem)

A conversa com o chefe é sobre mover ESTA mesma lógica para um servidor
(atende 24h sem depender do meu PC ligado). A peça central já está pronta e
compartilhada: `tools/issuer.py` (o robô, o Studio e o CLI usam a mesma
emissão). O plano da versão nuvem está em `PLANO-COMERCIALIZACAO.md` (seção 1)
e no `LICENCIAMENTO.md`.
