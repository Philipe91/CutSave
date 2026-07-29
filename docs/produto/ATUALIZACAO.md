# Aviso de atualização

Como avisar o cliente que saiu uma versão nova do PrintNest.

## Como funciona

O app consulta um **manifesto** (um JSON que você publica). Se a versão de lá
for maior que a instalada, ele mostra um aviso com as novidades e um botão que
abre o link do download. **A instalação continua na mão do cliente.**

O app **não se atualiza sozinho**, e isso é decisão de projeto, não preguiça:
troca automática de executável só é aceitável verificando a assinatura do
arquivo baixado. Sem essa verificação, quem comprometesse o servidor rodaria
código na máquina de todo cliente. Se um dia quiser atualização automática,
reaproveite o par Ed25519 do licenciamento (`app/licensing/signing.py` já
verifica assinatura; a privada é a mesma de `tools/license_private_key.pem`) e
assine cada release.

## O que publicar

Um arquivo `versao.json` em qualquer endereço `https://`:

```json
{
  "versao": "1.1.0",
  "url": "https://seu-site/downloads/PrintNest.exe",
  "notas": "Faca do cliente mais rápida. Correção no DXF por chapa."
}
```

- **versao** — precisa ser MAIOR que a instalada, comparada por número
  (1.10 é maior que 1.9). Igual ou menor não avisa nada.
- **url** — só `http://` ou `https://`. Qualquer outro esquema é recusado pelo
  app de propósito, para um manifesto adulterado não conseguir disparar outra
  coisa na máquina do cliente.
- **notas** — opcional; aparece no aviso.

Lembre de subir `app/__init__.py` (`__version__`) e `docs/build/VERSAO.txt`
antes de gerar a build, senão o cliente atualiza e continua sendo avisado.

## Onde hospedar

Qualquer coisa que sirva um arquivo estático por HTTPS serve: a hospedagem do
site de vendas, GitHub Pages, ou um Release público no GitHub. Se usar o
repositório, ele precisa ser **público** — `raw.githubusercontent.com` de repo
privado exige token, e o app não manda credencial nenhuma.

## Como ligar (faça UMA vez, antes de buildar)

Preencha a constante em [`app/infrastructure/updates.py`](../../app/infrastructure/updates.py):

```python
URL_MANIFESTO_PADRAO = "https://seu-site/versao.json"
```

e rode o `build.bat`. **Todo cliente que instalar já sai sabendo onde
conferir** — o endereço vai dentro do `.exe`.

Vazio = recurso desligado, o app não faz requisição nenhuma.

> Não adianta deixar isso só para o `config.json`: ele vive em
> `%APPDATA%\PrintNest\` da máquina do cliente, que é exatamente onde você não
> alcança, e ninguém vai editar JSON para receber aviso de atualização.

### Exceção para um cliente específico

O `config.json` do cliente **sobrescreve** o endereço embutido, útil para
apontar um cliente para outro lugar sem gerar build nova:

```json
{
  "update_url": "https://outro-endereco/versao.json",
  "update_check_on_start": true
}
```

- `update_check_on_start: false` mantém só o check manual, em
  **Ajuda → Procurar atualizações...**

## Comportamento que você pode contar

- **Nunca trava a janela**: a consulta roda em thread separada.
- **Falha calada**: sem internet, servidor fora, 404 ou JSON quebrado, o app
  segue como se nada fosse. Aviso de atualização não pode atrapalhar quem só
  quer trabalhar.
- **Não insiste**: quem clica "Não avisar sobre esta" não é perturbado de novo
  por aquela versão. A próxima versão avisa normalmente.
- **O check manual sempre responde**, inclusive para dizer que está em dia —
  um botão que não dá retorno parece quebrado.
