# PrintNest Pro 1.1.0 — Notas da versão

**3 de agosto de 2026**

Esta versão traz uma novidade pedida por quem usa e **uma correção importante
na impressão**. Instale por cima da versão que você já tem — sua licença e suas
configurações são preservadas.

---

## ⚠ Correção importante: impressão saía virada

Se você imprimiu com a 1.0.0 ou a 1.0.1 e **girou alguma peça**, confira o
material antes de repetir o trabalho.

Havia duas falhas, agora corrigidas:

- **Peça girada em 90° ou 270° saía 180° virada no PDF de impressão.** O lugar
  e o tamanho estavam certos — só o sentido do giro discordava do que aparecia
  na tela. A faca nunca foi afetada, o que fazia o erro parecer problema das
  marcas de registro.
- **Alguns arquivos saíam com a arte espelhada.** Depende de como o PDF foi
  gravado na origem (certos programas escrevem a página de um jeito que o
  PrintNest interpretava ao contrário). Todo visualizador corrige isso sozinho,
  então o arquivo abria certo em qualquer lugar e ninguém desconfiava.
  A mesma causa fazia o **recorte de borda ser ignorado em silêncio**: a
  sangria que você mandava tirar continuava no material.

---

## Novidade: espelhar peças

Como no CorelDRAW. Selecione uma peça — ou várias — e espelhe.

**Três jeitos de chamar:**
- os dois botões na barra de cima, ao lado dos de girar
- o menu do **botão direito** sobre a peça
- **Ctrl+Shift+H** (horizontal) e **Ctrl+Shift+V** (vertical)

Clicar de novo no mesmo botão **desfaz**. `Ctrl+Z` também funciona normalmente.

### A faca espelha junto?

Se a faca já foi gerada, o PrintNest **pergunta**:

- **Espelhar arte e faca** — o normal. A linha de corte continua acompanhando o
  desenho.
- **Somente a impressão** — a faca fica como está. Útil para impressão no
  verso. **Atenção:** em peça assimétrica a faca deixa de bater com a arte, e
  isso só aparece depois de cortar.

Peça sem faca gerada espelha direto, sem pergunta.

### PDF com várias páginas

Se o arquivo tem outras peças na produção, o programa pergunta se o espelho
vale só para as selecionadas ou para todas do arquivo.

---

## Como atualizar

Execute o instalador **por cima** da versão atual. Não precisa desinstalar.

- **Licença preservada** — você não vai precisar ativar de novo
- **Configurações preservadas**
- Feche o PrintNest antes de instalar

**O aviso azul do Windows:** ao abrir o instalador, o Windows pode dizer que
"protegeu seu computador". Clique em **Mais informações** e depois em
**Executar assim mesmo**. Esse aviso aparece em todo programa novo.

---

## Um problema conhecido nesta versão

Em alguns casos, **apagar uma peça quando existem várias cópias do mesmo
arquivo pode remover mais peças do que a selecionada** na tela. O `Ctrl+Z`
desfaz. Estamos investigando; se acontecer com você, anote a sequência de
cliques e avise — é o que permite corrigir.
