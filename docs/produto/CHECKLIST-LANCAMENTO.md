# CHECKLIST FINAL DE LANÇAMENTO — PrintNest (L1)

Imprimível. Ordem sugerida. Itens ☐ são do Philipe; os [C] o Claude faz
quando as decisões saírem.

## Antes de vender QUALQUER licença
- ☑ **BACKUP DA CHAVE PRIVADA** `tools/license_private_key.pem` — FEITO
  pelo Philipe em 27/07.
- ☐ Robô de ativação RODANDO no PC que recebe os e-mails
  (`iniciar_robo_licencas.bat`; ver docs ROBO-ATIVACAO).
- ☐ Teste de compra ponta a ponta com código PNC de uso único
  (já passou 1× em 24/07 — repetir com o INSTALADOR novo).

## Decisões comerciais (destravam o jurídico)
- ☐ 1. Figura jurídica: MEI/ME + emissão de nota (contador) —
  **falta: razão social/nome, CNPJ/CPF e cidade/UF** pros docs.
- ☑ 2. Gateway: **Mercado Pago** (decidido 27/07; já preenchido nos docs).
- ◐ 3. Suporte: **e-mail + WhatsApp** (decidido 27/07) —
  **falta: o endereço de e-mail e o número**.
- ☑ 4. Code signing: **lançar sem** (decidido 27/07); aviso azul do
  SmartScreen documentado no README do cliente. Comprar na v1.0.x.
- ☑ 5. Versão de venda: **1.0.0** (decidido 27/07; aplicada em
  app/__init__.py, VERSAO.txt e installer/printnest.iss).
- [C] Quando saírem razão social/CNPJ/cidade + contatos de suporte:
  preencher EULA/Privacidade/Termos + installer/EULA.txt (lacunas
  [RAZÃO SOCIAL], [NÚMERO], [CIDADE/UF], [SUPORTE], [DEFINIR:
  atualizações]).

## Pacote
- [C] build.bat → PrintNest_Build\ (exe + Tutor IA + plugin Corel).
- [C] ISCC installer\printnest.iss → dist_installer\PrintNest-Setup-*.exe.
- ☐ Smoke test do instalador: docs/build/SMOKE-TEST.md (10 itens).

## Release (depois do smoke test OK)
- [C] CHANGELOG com a data de lançamento.
- [C] Merge v1.3-redesign → main + tag da versão (com aprovação).
- ☐ Página de venda no ar (site/ — landing React, R$ 397).
- ☐ E-mail de suporte criado e chegando no robô/caixa certa.

## Pós-lançamento (v1.0.x — NÃO segurar o lançamento por isso)
- Auto-update + crash reporting.
- A10 (O(n²) merge), A4 (K puro), A2/A3 (marcas personalizáveis — doc de
  pesquisa do Philipe pendente).
