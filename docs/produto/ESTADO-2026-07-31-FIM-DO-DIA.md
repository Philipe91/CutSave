# Estado ao fim de 31/07/2026 — para retomar de casa

Branch de trabalho: **`release/1.0.1`** · último commit: **`a1c8f9c`**
Tudo o que está descrito aqui já está no GitHub. Comece com `git pull`.

---

## O que foi entregue hoje

**1.0.1 lançada e entregue pelo canal de atualização.** É a primeira vez que
uma versão chega ao cliente sozinha: o app na 1.0.0 avisou, baixou e instalou
por cima preservando licença e configurações. O canal deixou de ser promessa.

- Ícones nítidos em escala de 125–150% (H1)
- Botão **Modo Corte** destacado, em azul escuro com ícone de alvo
- Instalador hospedado em `github.com/Philipe91/printnest-releases`
  (release `v1.0.1`) — **release publicada nunca pode ser apagada**
- Tags `v1.0.0` e `v1.0.1` criadas e enviadas

---

## Correções de produção feitas depois (ainda NÃO empacotadas)

Estão no código, com 990 testes verdes, mas **não existem em nenhum `.exe`**.
Quem tem a 1.0.1 instalada ainda tem os defeitos abaixo.

### Impressão saía girada / espelhada — duas causas independentes

**a) Sentido do giro.** O canvas gira horário; a exportação girava anti-horário.
Peça com 90° ou 270° era impressa **180° virada** em relação à tela, no lugar e
no tamanho certos. A faca saía correta porque não passa por essa matriz.
O defeito é **anterior à migração PyMuPDF→pikepdf**: o teste de paridade
copiava fielmente o sentido do motor antigo, que já discordava da própria tela.

**b) Caixa de página invertida.** MediaBox escrita como `[0 297 210 0]` é legal
em PDF e todo visualizador normaliza sozinho — a nossa matriz não. Largura
negativa → escala negativa → arte **espelhada**. Só em alguns arquivos.
De brinde, a mesma causa fazia o **recorte de borda ser ignorado em silêncio**.

> **Falta o teste do dono com o arquivo real** (o Homem-Aranha do servidor).
> Rodar o app do código-fonte — `.venv\Scripts\python.exe -m app.presentation` —
> e conferir a exportação no Corel. A 1.0.1 instalada **ainda tem o defeito**.

---

## Fila aberta

1. **Confirmar as correções acima com arquivo real** e, se passarem, empacotar
   uma **1.0.2** (é o segundo uso do canal, agora sem estreia).
2. **Arquivo rearrastado volta com a faca e o giro antigos.** Diagnosticado: o
   estado por caminho de arquivo (`_file_overrides`, `_faca_manual`,
   `_piece_rotations`) não é limpo ao excluir a peça da chapa.
   **Decisão pendente do dono** entre:
   - **A)** limpar quando a última peça do arquivo sai, com o Ctrl+Z devolvendo
     os ajustes (recomendada)
   - **B)** um botão explícito "Recomeçar este arquivo"
3. **Excluir a faca gerada para gerar outra** — classificado como **1.1**
   (é funcionalidade nova, não correção).

---

## Incidente de segurança de 31/07 — PENDENTE, é o mais urgente

O repositório **`Philipe91/CutSave` é público** e um commit de logs de conversa
expôs: uma **chave de API do 21st.dev**, **códigos de compra**, **e-mails de
clientes** e o e-mail do robô de ativação.
A chave privada de licenciamento **nunca foi versionada** — essa está a salvo.

Já feito: `docs/conversas/` saiu do versionamento, entrou no `.gitignore`, e o
hook passou a gravar em `~/PrintNest-conversas/`, fora do repositório. Isso
impede vazamentos novos e **não desfaz o que já está publicado**.

Falta, na mão do dono:

1. **Deixar o repositório privado** — Settings → General → Change visibility.
   É o que resolve de imediato, inclusive contra o que já foi copiado por bots.
2. **Revogar a chave do 21st.dev** e gerar outra.
3. Remover do GitHub a branch que carrega o commit dos logs:
   ```
   git push origin --delete release/1.0.1
   git rebase --onto 4ac2ccb 95328ac release/1.0.1
   git push -u origin release/1.0.1
   ```
   (o Claude Code bloqueia esses dois primeiros por serem irreversíveis no
   remoto — tem de ser você, ou liberar a permissão)
4. **Gerar códigos de compra novos** para quem ainda não ativou.

---

## Outras pendências que o dia não anulou

- **Guardar `tools/license_private_key.pem` fora desta máquina.** Continua
  existindo num disco só. Perder = nunca mais emitir licença.
- **Reemitir as 3 licenças** que quebraram com a mudança do fingerprint (30/07).
- **Desativar a licença de teste** desta máquina (Ajuda → Licença → Desativar).
- Cópia do instalador 1.0.0 fora do projeto — arquivado em
  `%USERPROFILE%\PrintNest-releases\1.0.0\`, mas ainda no mesmo disco.

---

## Como rodar a suíte (ela não se auto-reporta)

```powershell
New-Item -ItemType Directory -Force reports | Out-Null
.venv\Scripts\python.exe -m pytest tests --ignore=tests\presentation -q --junit-xml=reports\core.xml
foreach ($f in Get-ChildItem tests\presentation\test_*.py) {
  $xml = "reports\" + $f.BaseName + ".xml"
  .venv\Scripts\python.exe -m pytest $f.FullName -q --junit-xml=$xml
}
.venv\Scripts\python.exe reports\somar.py
```

Estado atual: **990 testes, 0 falhas, 5 skips**. O processo morre no teardown e
o código de saída mente — vale a soma dos XML.

---

## Aviso sobre sessões simultâneas

Havia **outra sessão do Claude** trabalhando na landing (`site/app/...`) neste
mesmo diretório hoje. Foi ela que criou o commit dos logs de conversa que meu
push publicou. Antes de mexer em git, feche as outras sessões.
