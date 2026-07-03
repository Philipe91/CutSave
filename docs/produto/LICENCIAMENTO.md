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

## Arquivos

| Arquivo | O que é |
|---|---|
| `tools/license_private_key.pem` | **SEU SEGREDO** — chave privada. Fora do Git. Faça backup em lugar seguro. Se vazar, qualquer um forja licença. |
| `app/licensing/signing.py` → `PUBLIC_KEY_HEX` | chave pública embutida no app (par da privada). |
| `tools/gen_license.py` | emite uma licença para um cliente. |
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
