# PrintNest Pro 1.1.2 — Notas da versão

**4 de agosto de 2026**

Versão de manutenção. **Nenhuma função mudou** e nada no seu jeito de trabalhar
é diferente — é uma correção interna de desempenho. Instale por cima da versão
que você já tem: sua licença e suas configurações são preservadas.

---

## O que foi corrigido

**O Modo Corte não acumula mais memória a cada abertura.**

Toda vez que você abria o Modo Corte, a janela dele continuava ocupando memória
depois de fechada — junto com as peças que você tinha importado e toda a
geometria do encaixe. Só era liberada quando você fechava o PrintNest.

Na prática: quem abre e fecha o Modo Corte várias vezes no mesmo expediente
sentia o programa ficando mais pesado ao longo do dia, sem motivo aparente.
Fechar e abrir o PrintNest resolvia — e é exatamente por isso que era difícil
de perceber como defeito.

Agora a janela é liberada assim que você a fecha.

---

## Sobre o fechamento inesperado

Precisa ficar claro, para você não contar com o que ainda não está resolvido:
**esta versão não é a correção do problema de fechamento inesperado.**

Esse defeito continua **em aberto**. Ele é raro, não conseguimos reproduzi-lo em
bancada, e a investigação segue. O que a 1.1.2 corrige é um consumo de memória
que **piora** as condições em que ele costuma aparecer — mas não foi
demonstrado que seja a causa.

Se acontecer com você, o mais útil que você pode fazer é anotar **o que estava
fazendo no momento**. O programa grava sozinho um registro técnico em
`%APPDATA%\PrintNest\logs\crash.log`; envie esse arquivo junto.

**Salve com frequência** (`Ctrl+S`). Não existe salvamento automático.

---

## Como atualizar

Execute o instalador **por cima** da versão atual. Não precisa desinstalar.

- **Licença preservada** — você não vai precisar ativar de novo
- **Configurações preservadas**
- Feche o PrintNest antes de instalar

**O aviso azul do Windows:** ao abrir o instalador, o Windows pode dizer que
"protegeu seu computador". Clique em **Mais informações** e depois em
**Executar assim mesmo**. Esse aviso aparece em todo programa novo.

**Se der erro na primeira abertura:** logo depois de instalar, o antivírus do
Windows varre o programa recém-gravado. Abrir nesse exato momento pode gerar
uma mensagem falando em "Python DLL". Espere alguns segundos e abra de novo
pelo atalho — funciona normalmente.

---

## Problemas conhecidos mantidos nesta versão

Nenhum deles é novo; todos vêm da 1.1.0 ou anterior.

- **Fechamento inesperado**, descrito acima. Em aberto.
- **Apagar uma peça quando existem várias cópias do mesmo arquivo** pode remover
  mais peças do que a selecionada na tela. O `Ctrl+Z` desfaz. Ainda não
  reproduzido em bancada — se acontecer com você, anote a sequência de cliques.
- **Rearrastar um arquivo que você excluiu** traz de volta a faca e o giro
  antigos, em vez de começar do zero.
- **O Modo Corte não tem zoom.**
