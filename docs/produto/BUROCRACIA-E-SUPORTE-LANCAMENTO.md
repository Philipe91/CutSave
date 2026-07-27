# Burocracia & Suporte — Lançamento do PrintNest

> ⚠️ **Isto é um guia prático de organização, NÃO um parecer jurídico ou
> contábil.** Os itens fiscais/legais precisam ser confirmados com um
> **contador** e, idealmente, um **advogado**. Leis e valores mudam.
> Documento vivo — atualizar conforme as decisões saem.
> Complementa: [CHECKLIST-LANCAMENTO.md](CHECKLIST-LANCAMENTO.md) e
> `docs/produto/juridico/` (EULA, Privacidade, Termos).

Decisões já fechadas (27/07/2026): versão **1.0.0**, gateway **Mercado Pago**,
**lançar sem code signing** (comprar depois), suporte **e-mail + WhatsApp**,
**backup da chave privada feito**.

---

# PARTE A — BUROCRACIA (o que falta para poder vender legalmente)

## A1. Figura jurídica (CNPJ) — ⚠️ atenção ao MEI × software
- **Pegadinha:** o **MEI historicamente NÃO permite atividade de
  desenvolvimento/licenciamento de software.** Muito provavelmente o caminho é
  **ME no Simples Nacional** (ou você como autônomo/PJ conforme o contador).
  **➡️ Primeira pergunta ao contador: "consigo vender licença de software no
  MEI ou preciso de ME?"**
- Definir: **razão social / nome**, **CNPJ**, **cidade/UF**, **CNAE**
  (ex.: 6203-1/00 – desenvolvimento e licenciamento de software customizável /
  6202-3/00 – customizável; o contador escolhe o correto).
- Custo/prazo de abertura: confirmar com o contador (abertura + honorário
  mensal). 
- **Depende disto:** emissão de nota, preencher os contratos, comprar o
  certificado de code signing (é emitido para o CNPJ).

## A2. Nota fiscal
- Licença de software normalmente é **NFS-e (nota de serviço)** emitida pelo
  portal da **prefeitura** da sua cidade (ISS). O contador confirma se é
  serviço (licenciamento) ou outro enquadramento e configura o portal.
- Definir alíquota (ISS), regime (Simples), e se o Mercado Pago/Hotmart emite
  algo no seu lugar (Mercado Pago **não** emite NF por você — você emite).
- **Fluxo:** venda no Mercado Pago → você (ou automação) emite a NFS-e para o
  cliente → guarda para a contabilidade.

## A3. Contratos jurídicos (já redigidos — faltam dados)
Status em `docs/produto/juridico/`:
- **EULA.md**, **POLITICA-DE-PRIVACIDADE.md**, **TERMOS-DE-VENDA-E-GARANTIA.md**
  — redigidos, com **lacunas** a preencher:
  `[RAZÃO SOCIAL]`, `[NÚMERO do CNPJ]`, `[CIDADE/UF]`, `[SUPORTE]`
  (e-mail/WhatsApp), `[DEFINIR: atualizações incluídas por X tempo]`.
- `[GATEWAY]` já preenchido = **Mercado Pago**.
- **➡️ Assim que sair CNPJ + contatos, o Claude preenche em 5 min.** O mesmo
  EULA (versão .txt) já está na tela de aceite do instalador
  (`installer/EULA.txt`).
- **Recomendado:** um advogado dar uma lida final antes de publicar (barato
  e evita dor de cabeça no primeiro cliente-problema).

## A4. LGPD (proteção de dados)
- Dados coletados pelo software/venda: **nome, e-mail, ID da máquina**
  (node-lock) e dados de pagamento (esses ficam **no Mercado Pago**, você não
  guarda cartão).
- A **Política de Privacidade** já cobre isso; confirmar base legal (execução
  de contrato) e o contato para requisições de titular (= o e-mail de suporte).
- Boa prática: não pedir mais dado do que precisa; guardar o mínimo.

## A5. Direito do consumidor (CDC)
- Venda pela internet dá **direito de arrependimento em 7 dias** (art. 49 CDC)
  com reembolso integral. Já está nos **Termos**.
- Processo de reembolso: ver **B6** (revoga a licença + estorno no Mercado Pago).

## A6. Gateway de pagamento — Mercado Pago
- Criar conta **Mercado Pago** (PJ, com o CNPJ) → criar o **produto/checkout**
  (link de pagamento ou Checkout Pro) → habilitar **Pix, cartão, boleto**.
- Definir preço: **R$ 397** (licença perpétua, 1 PC).
- **Entrega:** o Mercado Pago **não entrega o código sozinho** — você precisa
  de um passo que, após o pagamento aprovado, mande ao cliente o **código de
  compra PNC** (manual no início; automatizável depois via webhook).
- Conferir **taxas** (Pix < cartão) e prazo de repasse.

## A7. Code signing (assinatura do executável)
- **Decisão:** lançar **sem** certificado. Consequência: o Windows
  **SmartScreen** mostra "aplicativo não reconhecido" → o cliente clica em
  "Mais informações → Executar assim mesmo". **Já documentado no README do
  cliente.**
- Comprar depois (v1.0.x): certificado **EV/OV code signing** (emitido para o
  CNPJ, custo anual, alguns dias para emitir). Some com o aviso azul.

## A8. Propriedade intelectual / marca
- **Motor livre:** já resolvido (migração AGPL→pypdfium2+pikepdf; ver memória
  do motor). Sem pendência de licença de terceiros no app.
- **Marca "PrintNest":** registro no **INPI** é **opcional** para lançar, mas
  recomendado a médio prazo para proteger o nome (custo/prazo próprios).
  Não bloqueia o lançamento.

## A9. Segurança do negócio (não é "papel", mas é crítico)
- ✅ **Backup da chave privada** `tools/license_private_key.pem` (feito 27/07).
  Sem ela, nenhuma licença vendida é emitida/revalidada.
- **Robô de ativação** precisa rodar no PC que recebe os e-mails
  (`iniciar_robo_licencas.bat`). Ver Parte B.

### Checklist burocracia
- [ ] Contador: MEI × ME (pode vender software?) + CNAE + custo
- [ ] Abrir/confirmar CNPJ (razão social, número, cidade/UF)
- [ ] Portal de NFS-e da prefeitura configurado
- [ ] Preencher lacunas dos 3 contratos + revisão de advogado (opcional)
- [ ] Conta Mercado Pago PJ + checkout R$ 397 + Pix/cartão/boleto
- [ ] Fluxo de entrega do código PNC definido (manual no início)
- [ ] (Depois) certificado de code signing
- [ ] (Depois) registro da marca no INPI

---

# PARTE B — ESQUEMA DE SUPORTE

Objetivo: cliente de gráfica consegue **comprar → instalar → ativar → produzir**
sem travar, e quando trava tem para quem recorrer rápido.

## B1. Canais (decidido: e-mail + WhatsApp)
- **E-mail** (formal, jurídico, LGPD, comprovantes): `[DEFINIR e-mail]`
  (ex.: suporte@printnest.com.br).
- **WhatsApp** (dia a dia, rápido, gráfica não gosta de e-mail): `[DEFINIR
  número]` — usar **WhatsApp Business** (respostas rápidas, catálogo, horário).
- Um mesmo endereço/número entra nos contratos e na tela de ativação.

## B2. Horário e expectativa de resposta (SLA)
- **Dias úteis, horário comercial**, sem garantia contratual de tempo (já nos
  Termos) — mas **meta interna**: responder em **até 1 dia útil**.
- Deixar claro na assinatura/mensagem automática: "recebido, respondemos em
  até X".

## B3. Ferramenta de atendimento (começar simples)
- **Fase 1 (lançamento):** caixa de e-mail + WhatsApp Business. Barato, zero
  setup.
- **Fase 2 (quando escalar):** um helpdesk simples (ex.: assunto/ticket) para
  não perder mensagem. Não precisa agora.

## B4. Fluxo de licença/ativação (o coração do suporte)
- **Compra → código PNC → ativação:** cliente paga (Mercado Pago), recebe o
  **código de compra PNC-XXXX-XXXX**, abre o PrintNest, cola no campo **"Código
  de compra"** da tela de ativação (o campo novo que criamos evita colar o ID
  errado), pede a chave por e-mail (mailto pronto) → o **robô** responde com a
  chave → cliente cola e ativa.
- **Robô rodando:** `iniciar_robo_licencas.bat` no PC que recebe os e-mails.
  ⚠️ Se o robô estiver **desligado**, o cliente paga e **não recebe a chave** →
  reclamação. **Manter o robô sempre no ar** (ou checar todo dia).
- **Troca de PC:** cliente usa **"Desativar"** no PC antigo e ativa no novo.
  Perda/defeito do PC antigo: suporte transfere manualmente após verificação.
- **Backup da chave privada:** sem ela nada disso funciona (ver A9).

## B5. Base de conhecimento / FAQ (reduz 80% dos tickets)
Escrever respostas prontas (e mandar junto no e-mail de entrega):
1. **"Windows diz que não reconhece o app"** → SmartScreen: Mais informações →
   Executar assim mesmo (sem code signing; é normal).
2. **"Onde coloco o código?"** → tela de ativação, campo "Código de compra"
   (não é o ID da Máquina).
3. **"Paguei e não recebi a chave"** → verificar spam; robô responde em
   minutos; se não, acionar suporte.
4. **"Como troco de computador?"** → Desativar no antigo → ativar no novo.
5. **"O corte saiu torto / DXF"** → validar o DXF na mesa (iBrightCut/Mimaki)
   antes de larga escala; conferir medidas/sangria.
6. **"Como coloco o arquivo na chapa?"** → botão **Colocar na chapa** ou
   duplo clique na biblioteca (ou arrastar).
- Material de apoio que já existe: **Tutor IA (PDF)** que vai no instalador, o
  **README do cliente** e o **guia do plugin CorelDRAW**.

## B6. Reembolso (7 dias)
- Cliente pede em até 7 dias → **estornar no Mercado Pago** → **revogar/
  desativar a licença** (para não ficar licença paga sem pagamento) → confirmar
  por e-mail. Registrar o caso.

## B7. Escalonamento
- **Dúvida de uso** → FAQ / suporte responde.
- **Bug do software** → registrar (arquivo que causou + print) → repasse ao
  desenvolvimento (Claude/Philipe) → corrigir em atualização.
- **Jurídico/reembolso/LGPD** → seguir Termos/Política; casos difíceis →
  advogado.

## B8. Templates de resposta (criar antes de vender)
- **Entrega da compra** (código PNC + passo a passo de ativação + FAQ + links).
- **Chave de licença** (a que o robô manda; já existe).
- **Reembolso** (confirmação + prazo do estorno).
- **"Robô fora do ar" / atraso** (pedido de desculpas + prazo).

## B9. Métricas simples (acompanhar do 1º dia)
- Nº de vendas, nº de tickets, **motivos mais comuns** (alimenta o FAQ e as
  próximas melhorias do app), tempo médio de resposta, reembolsos.

### Checklist suporte
- [ ] Criar e-mail de suporte + assinatura com expectativa de resposta
- [ ] WhatsApp Business configurado (horário, respostas rápidas)
- [ ] Robô de ativação rodando e monitorado (não pode cair)
- [ ] Escrever os 6 itens do FAQ + os 4 templates
- [ ] Teste de compra ponta a ponta (pagar → receber PNC → ativar) com o
      instalador 1.0.0 novo
- [ ] Definir quem responde (você? sócio?) e em qual horário

---

## O que trava o lançamento AGORA (resumo)
1. **CNPJ + razão social + cidade** (contador) → destrava contratos e nota.
2. **E-mail + WhatsApp de suporte** definidos → entram nos contratos e no app.
3. **Mercado Pago** com checkout no ar + **fluxo de entrega do PNC**.
4. **Robô de ativação** rodando + **teste de compra ponta a ponta**.
5. **Página de venda** no ar (site/) — onde o cliente compra.

O software (produto) já está pronto e validado; o que falta acima é
**operacional/comercial**, não é mais código do app.
