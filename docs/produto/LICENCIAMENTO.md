# Licenciamento do PrintNest — guia do dono do produto

Modelo: **venda completa + chave de ativação (node-locked, sem trial) + 7 dias
de garantia**. O cliente compra, ativa com uma chave presa ao PC dele e usa
tudo; se não gostar, devolução em 7 dias (política comercial, não vive no
código). Sem chave válida, o **executável não abre** (dev/fonte não trava).

## Como funciona por dentro (offline, sem servidor)

- **Assinatura Ed25519.** Você tem a chave **privada** (segredo); o app tem só a
  **pública** — verifica a licença, mas ninguém consegue forjar uma.
- **Preso ao PC.** A licença carrega o "ID da Máquina" do cliente; o app só
  aceita se o ID bater. Passar o `.exe` para outro PC não funciona.
- **100% offline.** Nada de servidor nem mensalidade. Validação local.

> ✅ **Validado de ponta a ponta em 06/07/2026** num 2º PC real: exe bloqueou,
> ID enviado, chave emitida, ativou e persistiu após reiniciar.

## Arquivos

| Arquivo | O que é |
|---|---|
| `tools/license_private_key.pem` | **SEU SEGREDO** — chave privada. Fora do Git. Faça backup em lugar seguro. Se vazar, qualquer um forja licença. |
| `app/licensing/signing.py` → `PUBLIC_KEY_HEX` | chave pública embutida no app (par da privada). |
| `tools/license_studio.py` | **License Studio (GUI)** — emissão manual: cola o ID do cliente → Gerar → Copiar (~30 s por venda). |
| `tools/license_robot.py` | **Robô de ativação** — emissão AUTOMÁTICA por e-mail (ver seção abaixo). |
| `tools/gen_vouchers.py` | gera **códigos de compra** (`PNC-XXXX-XXXX`) em lote — um por venda, é o que o robô valida. |
| `tools/gen_license.py` | emite uma licença pela linha de comando (mesmo resultado do Studio). |
| `tools/issuer.py` | lógica de emissão compartilhada (Studio, CLI e robô usam; base para futuro backend na nuvem). |
| `tools/gen_keypair.py` | gera um novo par (só se quiser trocar o segredo — invalida licenças já emitidas). |

## Fluxo de venda (passo a passo)

1. Cliente compra (site/Hotmart/PIX) e instala o PrintNest.
2. Ele abre o app → aparece a tela de **Ativação** → copia o **ID da Máquina**
   (algo como `PN-XXXX-XXXX-XXXX-XXXX`) e te envia (WhatsApp/e-mail).
3. Você emite a licença:

   ```
   python tools/gen_license.py --machine-id PN-XXXX-XXXX-XXXX-XXXX \
       --customer "Grafica Fulano <email>"
   ```

   (para licença com validade, ex. assinatura anual, adicione
   `--expires 2027-12-31`.)
4. Copie a chave impressa (`PNEST1. ...`) e envie ao cliente.
5. Ele cola em **Ativar** → app liberado naquele PC, para sempre (ou até a
   validade).

## Ativação AUTOMÁTICA — o robô no seu PC (sem ficar na frente do computador)

> **Guia completo e detalhado do robô** (configurar do zero, rotina, problemas
> comuns, backup): **`ROBO-ATIVACAO.md`** nesta mesma pasta.

O robô troca **código de compra** por **licença** sozinho, por e-mail. A chave
privada continua só no seu PC (o robô roda aqui). Enquanto seu PC estiver
ligado com o robô aberto, o cliente é atendido em ~1 minuto, a qualquer hora.

### Configurar uma vez
1. Crie uma conta de e-mail dedicada (ex.: `ativacao.printnest@gmail.com`).
   No Gmail: ative a verificação em 2 etapas e crie uma **senha de app**
   (myaccount.google.com/apppasswords).
   > O endereço também vai **dentro do app** (`app/licensing/__init__.py`,
   > constante `ACTIVATION_EMAIL`) — se usar outro, troque lá e refaça o build.
2. Copie `tools/robot_config.example.json` → `tools/robot_config.json`
   (fica fora do Git) e preencha e-mail + senha de app.
3. Gere um lote de códigos de compra:
   `.venv\Scripts\python.exe tools/gen_vouchers.py -n 20 --note "lote 1"`
4. Inicie o robô: **`tools/iniciar_robo_licencas.bat`** (deixe a janela aberta).

### Fluxo de venda com o robô
1. Cliente paga → você envia **um código de compra** (`PNC-XXXX-XXXX`) — dá
   para fazer do celular, de qualquer lugar.
2. Cliente instala, abre o PrintNest → tela de Ativação → botão
   **"Pedir minha chave por e-mail"** → abre um e-mail já preenchido com o ID
   da máquina; ele cola o código de compra e envia.
3. O robô valida o código (uso único), assina a licença e **responde com a
   chave** + instruções. Cliente cola em Ativar. Fim.

Regras do robô: código é de **uso único** e fica preso ao 1º PC que ativar; o
**mesmo PC** pedindo de novo recebe a **mesma** chave (perdeu o e-mail); outro
PC com código usado é recusado com orientação de suporte. Registro de tudo em
`tools/licenses_emitidas/` (vouchers.json + robo-log.jsonl) — **entra no mesmo
backup da chave privada**.

Limite desta versão: se o seu PC estiver desligado, o pedido espera na caixa de
entrada e é atendido quando o robô voltar. O passo seguinte (planejado) é levar
essa mesma lógica para a nuvem (`issuer.py` já é a peça central).

## Transferir de PC / trocar de máquina

No PC antigo: **Ajuda → Licença → Desativar**. No PC novo: pega o novo ID e
você emite uma nova chave (ou reusa o mesmo processo). Se o PC quebrou e não deu
para desativar, é só você emitir uma nova chave para o ID novo (controle manual;
para automatizar "assentos", seria o modelo com servidor — ver
PLANO-COMERCIALIZACAO.md).

## Garantia de 7 dias (devolução)

É **comercial**: informe na página de venda e no EULA que há reembolso em até 7
dias. Tecnicamente não há como "revogar" uma licença offline já ativada — para o
volume inicial, o reembolso é confiança + baixo risco. Se virar problema,
migra-se para ativação online (revogável) conforme o plano.

## Segurança — a verdade honesta

Nenhuma proteção desktop é inquebrável (o código roda na máquina do cliente).
Este esquema (assinatura + node-lock + exe gate) impede **cópia casual** (passar
o programa para o amigo) e forjar licença sem a privada é inviável. Investir em
anti-tamper pesado tem retorno decrescente — o objetivo é tornar pirataria mais
trabalhosa que comprar.
