# PrintNest Pro — dossiê para montar a bateria de testes

Documento de entrada para quem vai escrever o plano de testes. Descreve **o que
o software faz**, **como ele é feito**, **onde ele costuma quebrar** e **como o
usuário real percorre o produto**.

Estado em 04/08/2026 · versão 1.1.1 · branch `release/1.0.1`
Suíte atual: 1030 testes automatizados, 0 falhas.

---

## 1. O que é o produto

Software desktop Windows para **preparação de produção gráfica**. O cliente é
uma gráfica ou produtora de comunicação visual. O trabalho dele é:

1. receber artes prontas (PDF ou imagem);
2. encaixar várias peças numa chapa de material, aproveitando o máximo;
3. gerar a **faca** (linha de corte que a máquina vai seguir);
4. exportar um **PDF para impressão** e um **DXF para a mesa de corte**.

O produto substitui um trabalho que hoje é feito na mão dentro do CorelDRAW, e
o público-alvo é justamente quem usa CorelDRAW.

**O que está em jogo:** o material é caro. Um erro de encaixe desperdiça chapa;
um erro entre a arte impressa e a linha de corte estraga o lote inteiro — e só
é descoberto **depois de cortar**. Nenhum aviso na tela substitui isso.

---

## 2. Como é feito (arquitetura)

- **Python 3.10 + PySide6 (Qt 6)**, 131 arquivos, ~24.400 linhas em `app/`.
- Empacotado com **PyInstaller onefile** (um `.exe` de 116 MB que descompacta o
  Python numa pasta temporária a cada abertura), instalador **Inno Setup**.
- Arquitetura em camadas, com dependências apontando só para dentro:

| Camada | Pasta | Responsabilidade |
|---|---|---|
| Domínio | `app/domain/` | geometria, faca (`cut/`), encaixe (`nesting/`), modelos. Zero Qt. |
| Aplicação | `app/application/` | casos de uso, DTOs e *ports* (interfaces) |
| Infraestrutura | `app/infrastructure/` | importadores, exportadores, renderização |
| Apresentação | `app/presentation/` | Qt: janela, diálogos, canvas, temas |
| Licenciamento | `app/licensing/` | ativação por chave assinada, presa à máquina |

**Bibliotecas externas que importam para o teste:**
- `pypdfium2` — lê e rasteriza PDF. **Não é thread-safe**: o projeto usa um lock
  global (`PDFIUM_LOCK`).
- `pikepdf` — escreve PDF preservando vetores.
- `shapely` / GEOS — geometria **da faca** (offset, união, simplificação).
  Biblioteca em C. Vive em `app/domain/cut/`.
- `pyclipper` (Clipper) — geometria **do encaixe true-shape** (NFP, diferença
  de polígonos). Biblioteca em C++, independente da anterior. Vive em
  `app/domain/nesting/`. **Solta o GIL** durante o cálculo (medido em
  04/08/2026: 2 threads em 0,62× do tempo sequencial), ou seja, roda de fato em
  paralelo com o coletor de lixo do Python.
- `opencv` — recorte automático de imagens.
- `ezdxf` — exportação DXF.

**Concorrência:** operações pesadas rodam em `QThread` (importação, nesting do
Modo Corte, verificação de atualização). É a maior fonte de defeitos raros.

---

## 3. Inventário de funções

### 3.1 Biblioteca e importação
- Adicionar arquivos por botão, arrastar-e-soltar, ou pelo plugin do CorelDRAW
- Formatos aceitos: **PDF, PNG, JPG/JPEG, WEBP** (e **DXF/SVG** no Modo Corte)
- `.cdr` e `.svg` **não** entram na produção de impressão
- Quantidade por arquivo (coluna Qtd)
- Escolha da caixa do PDF: **Mídia** (com sangria) ou **Apara** (corte)
- Recorte de páginas/imagem; escolher quais páginas de um PDF entram
- Substituir arquivo; remover da biblioteca

### 3.2 Encaixe (nesting)
- Encaixe automático em grade, com divisão em várias chapas
- Largura e altura da chapa; espaçamento horizontal e vertical; margem de
  segurança; sangria
- Repetir em grade; duplicar; resetar arranjo
- Mover e girar peças no canvas, com encaixe recalculado
- Percentual de aproveitamento exibido

### 3.3 Faca de corte
Seis modos: **Automático**, **Retângulo**, **Contorno justo**, **Contorno
suave**, **Contorno simplificado** e **Faca do cliente** (vetor magenta 100%
desenhado pelo próprio cliente no arquivo).
- Sangria da faca (positiva = para fora, negativa = recuo/vinco)
- Sensibilidade do recorte automático de imagens
- Cantos: arredondar, chanfrar, manter vivo; raio configurável
- Densidade de nós (fino / médio / leve)
- Faca por peça ou compartilhada (estilo guilhotina)
- Edição manual dos nós (tecla F10, "Pontos")
- Solda automática de facas que se invadem

### 3.4 Marcas de registro
IECHO (círculos), Mimaki (marcas em L), quadrados (Summa/OPOS), cruzes
(AOKE/iECHO), Ls de canto (Graphtec/Roland), ou as duas juntas. Afastamento,
diâmetro e espessura configuráveis.

### 3.5 Modo Corte (laser/CNC)
Fluxo **separado**, em diálogo próprio, que não mexe no arranjo de impressão.
- Entrada por arquivo (PDF/DXF/SVG), por texto digitado, ou vindo do CorelDRAW
- Encaixe **true-shape** (peças se encaixam pelo contorno real, não pela caixa)
- Giro das peças em passos configuráveis (15°, 45°, 90°…)
- Tempo de otimização configurável
- Mover e girar peça no preview
- Exportar DXF; **Enviar p/ Corel**

### 3.6 Exportação
- **PDF de impressão** (vetores preservados)
- **DXF** único ou por chapa
- **Faca em PDF**; faca IECHO; faca Mimaki
- **Imagem** PNG/JPEG no DPI escolhido
- Centro de Exportação (Ctrl+E)
- Produção em cartelas (recurso desligado nesta versão)

### 3.7 Projeto e sessão
- `.printnest`: Novo, Abrir, Salvar, Salvar Como. **Gravação atômica**
- Abas de trabalho (multi-projeto, estilo CorelDRAW)
- Reabre o último projeto ao iniciar
- Desfazer/Refazer
- Configurações persistidas em `%APPDATA%\PrintNest\config.json`

### 3.8 Interface
- Barra estilo ribbon, painel de documento, biblioteca lateral, canvas com
  réguas e guias
- Modos de visualização: impressão, corte, dividido (2 orientações)
- Zoom (+, −, na página, na seleção, ajustar à tela); modo compacto
- Temas (claro e variações), tour de boas-vindas, tutoriais guiados
- Atalhos padrão CorelDRAW

### 3.9 Licenciamento e atualização
- Ativação por chave assinada, presa ao ID da máquina (**sem MAC**, só
  `MachineGuid`), licença perpétua
- Robô que emite licenças automaticamente por e-mail
- Canal de atualização: o app lê um manifesto JSON público e avisa quando há
  versão nova; o download é manual (o app **não** se atualiza sozinho, de
  propósito — sem verificar assinatura seria um vetor de ataque)

### 3.10 Plugin do CorelDRAW
Macro (`PrintNest.bas`/`.gms`) que instala um botão no Corel e manda a seleção
para o PrintNest. Comunicação por **COM**, síncrona.

---

## 4. Onde ele quebra — mapa de risco

Ordenado por **prejuízo**, não por frequência.

### 4.1 Crítico: arte e faca discordarem
Se a linha de corte não acompanha a arte impressa, a mesa corta fora e a chapa
inteira é perdida — descoberto só depois de cortar.

**Já aconteceu duas vezes** (corrigido em 31/07 e 03/08):
- o sentido do giro na exportação era o inverso do canvas, então peça a 90°/270°
  saía 180° virada na impressão enquanto a faca saía certa;
- PDFs com a caixa de página invertida (legal no formato, e todo visualizador
  corrige sozinho) saíam com a arte espelhada, e o recorte de borda era ignorado
  **em silêncio**.

**Regra que sustenta a correção:** a ordem canônica é *espelhar primeiro, girar
depois*, implementada num lugar só (`crop_and_rotate_contour`) e obedecida por
**cinco consumidores**: faca, arte na impressão, preview do canvas, estado por
peça e DXF. Se dois divergirem, o defeito volta.

**Teste tem que cobrir:** toda combinação de espelho × rotação, medindo se a
faca cai sobre a arte no arquivo exportado — não na tela.

### 4.2 Crítico: fechamento inesperado (crash 0xc0000374)
Aberto desde o lançamento. Em 04/08 apareceu um `crash.log` com a pilha:

```
worker            → true_shape.py: _subtract (pyclipper)
thread principal  → Garbage-collecting, dentro de _open_cut_mode
```

O Modo Corte roda o encaixe numa thread enquanto o coletor de lixo do Python
libera objetos na thread principal. `0xc0000374` é corrupção de heap. Como o
pyclipper solta o GIL, as duas coisas acontecem **de verdade ao mesmo tempo**.

**Correção de rumo (04/08/2026):** este item já foi descrito aqui como defeito
do GEOS. Está errado — `true_shape.py` importa `pyclipper` e **não usa shapely**.
GEOS só aparece na faca (`app/domain/cut/`), que não está nesta pilha.

**Estado da investigação:** sem reprodutor. Um esforço dirigido em 04/08 tentou
separar as três causas candidatas — encerramento, concorrência e
compartilhamento de geometria — e **não reproduziu** a corrupção com
worker no pyclipper + coleta de lixo agressiva na thread principal (4 modos,
25 s cada). Portanto a explicação "duas threads na mesma memória" segue como
**hipótese, não como causa provada**.

Candidato mais forte hoje: `main_window.py` abre o Modo Corte com
`CutModeDialog(self, ...).exec()` **sem guardar a referência**. O diálogo tem
pai, então o objeto C++ sobrevive à destruição do wrapper Python e **cada
abertura deixa um diálogo inteiro vivo** (cena, peças, geometria) — provado: 4
aberturas, 4 diálogos vivos. Isso empilha memória e alonga as pausas de coleta
exatamente onde o `crash.log` flagrou a thread principal.

**Não confundir com o BUG-QA-1** (`0xC0000005` na suíte de testes), que tinha
outra causa — eventos `DeferredDelete` nunca drenados — e está **fechado**.
Corrigir um não corrige o outro.

**Sem salvamento automático**, um crash custa tudo desde o último Ctrl+S.

### 4.3 Alto: entrega e primeira abertura
- **SmartScreen** aparece para todo cliente (sem assinatura digital)
- O onefile descompacta 116 MB no `%TEMP%` a cada abertura. Se o antivírus está
  varrendo o arquivo recém-instalado, a abertura falha com *"Failed to load
  Python DLL"*. **Instala e não abre** — o pior chamado possível. Mitigado na
  1.1.1 (o instalador não abre mais o programa sozinho), não eliminado.

### 4.4 Alto: estado por peça que não é limpo
Existe estado guardado **por arquivo** (faca personalizada, faca editada à mão)
e **por peça** (giro, espelho da arte, espelho da faca). Excluir a peça da chapa
**não limpa** esse estado: rearrastar o mesmo arquivo traz de volta a faca e o
giro antigos, quando o esperado é começar do zero. **Diagnosticado, não
corrigido.**

Relacionado, **relatado e ainda não reproduzido**: com várias cópias do mesmo
arquivo, apagar uma peça remove mais do que a selecionada na tela; um clique
seguinte traz as outras de volta.

### 4.5 Médio: concorrência com bibliotecas C
`pypdfium2` não é thread-safe (protegido por lock global). O `pyclipper` roda em
thread sem proteção equivalente **e solta o GIL** — é o item 4.2. Qualquer
operação nova em thread precisa ser avaliada sob essa ótica.

### 4.6 Médio: caminho do CorelDRAW
Ponte COM **síncrona, sem timeout**: se o Corel estiver ocupado ou com um
diálogo aberto, o PrintNest parece travado. Em 04/08 apareceu *"A macro do
PrintNest não respondeu no CorelDRAW"* ao usar Enviar p/ Corel, com o plugin
instalado. **Este caminho nunca teve cobertura de teste automatizado nem
validação sistemática** — e é a vitrine do produto para o público que usa Corel.

### 4.7 Médio: giro do Modo Corte intermitente
Relatado em 04/08: as letras não giravam no encaixe; repetindo a operação,
giraram. Comportamento que muda entre execuções idênticas costuma ser
concorrência ou estado residual — a mesma família do 4.2.

### 4.8 Interface em telas pequenas e escaladas
Histórico de defeitos reais: painéis engolindo a área de trabalho, barra pedindo
mais largura que a tela, tela de ativação sem caber a 150%. Telas de referência:
1920×1080, 1536×864, **1366×768**, 1280×720, 1092×614.

**Armadilha de método:** teste de geometria precisa aplicar `theme.apply()`
antes de medir; sem o QSS a medição erra de 28 a 117 px e esconde o defeito.

### 4.9 Acabamento pendente
~30 textos sem acento; caixas "Yes/No" em inglês; "Procurar atualizações" sem
internet responde como se estivesse em dia; exportação de imagem trava a janela;
digitar quantidade grande recalcula a cada dígito; `.cdr`/`.svg` arrastados são
ignorados sem mensagem; falta zoom no Modo Corte.

---

## 5. Jornada do usuário

### Jornada A — primeira vez (o momento mais frágil)
1. Recebe o link, baixa 118 MB
2. **SmartScreen** bloqueia → precisa clicar em "Mais informações"
3. Instala (EULA, atalho, instalar)
4. **Abre** — se o antivírus ainda estiver varrendo, falha com erro de DLL
5. **Tela de ativação bloqueante**: copia o ID da máquina, manda por e-mail com
   o código de compra, recebe a chave do robô, cola, ativa
6. Tour de boas-vindas
7. Fecha e reabre: **não pode pedir ativação de novo**

**Onde dói:** três oportunidades de desistir antes de ver o produto.

### Jornada B — trabalho do dia (o fluxo principal)
1. Abre o PrintNest (reabre o último projeto)
2. Arrasta 5 PDFs para a biblioteca
3. Define quantidade de cada um
4. Ajusta a chapa (ex.: 1250 × 1992 mm) e o espaçamento
5. **Colocar na chapa** → encaixe automático, vê o aproveitamento
6. Ajusta na mão: move, gira, espelha, duplica, apaga
7. **Gerar Faca** → escolhe o modo, ajusta sangria e cantos
8. Liga as marcas de registro conforme a máquina
9. **Exporta** PDF de impressão + DXF de corte
10. Manda o PDF para o RIP e o DXF para a mesa
11. Salva o projeto

**Onde dói:** os passos 6 e 7 são os que acumulam estado (giro, espelho, faca
por arquivo) — e é onde estão os defeitos de 4.4. O passo 9 é onde erram os
defeitos de 4.1, e o erro só aparece no material.

### Jornada C — Modo Corte (laser/CNC)
1. No CorelDRAW, seleciona as letras e clica no botão do plugin
2. O PrintNest abre o **Modo Corte** com as peças
3. Ajusta chapa, folga, margem, giro permitido e tempo de otimização
4. **Organizar** → encaixe true-shape (pode levar minutos)
5. Ajusta peças no preview
6. **Exportar DXF** ou **Enviar p/ Corel**

**Onde dói:** o passo 4 é onde o crash de 4.2 apareceu. O passo 1 e o 6
dependem da ponte COM (4.6). Não há zoom no preview.

### Jornada D — atualização
1. Abre o programa; ~3 s depois aparece o aviso de versão nova
2. "Abrir download" → navegador baixa do GitHub
3. Fecha o PrintNest, instala por cima
4. Reabre: licença e configurações preservadas

**Onde dói:** se o link do manifesto estiver errado, o cliente vai para um lugar
que não existe e não há correção remota — a URL está gravada dentro do `.exe`.

### Jornada E — recuperação de erro
- Programa fechou sozinho → perde tudo desde o último Ctrl+S (não há autosave);
  `crash.log` em `%APPDATA%\PrintNest\logs`
- Chave de licença não funciona → conferir se o ID da máquina mudou
- Não abre → conferir se já existe instância rodando (uma por vez)

---

## 6. Notas para quem for escrever os testes

**A suíte não se auto-reporta.** O processo morre no teardown do Qt e o código
de saída mente. O resultado válido é a soma dos XML do junit, e
`tests/presentation` trava se executada como pasta — tem que ser arquivo a
arquivo.

**Um defeito que passa em teste unitário e quebra no uso** é o padrão aqui. Os
três defeitos reais de 31/07 a 04/08 tinham 100% dos testes verdes:
- o giro invertido tinha teste — que travava paridade com o motor **antigo**,
  que já discordava da própria tela;
- o Delete/Ctrl+Z só quebra em **sequência** de cliques, não em operação isolada;
- o crash depende do coletor de lixo disparar no instante certo.

**O que a suíte atual não cobre:**
- comparação entre **o que a tela mostra** e **o que o arquivo exportado tem**
- sequências longas de interação (arranjar → girar → espelhar → apagar →
  desfazer → refazer, intercalados)
- concorrência: operação em thread com a interface sendo usada ao mesmo tempo
- o caminho do CorelDRAW (**nenhuma execução real desde que o produto existe**)
- instalação e primeira abertura em máquina limpa de terceiro
- arquivo gerado indo para RIP ou mesa de corte **reais**

**Princípio que vale mais que qualquer caso de teste:** o software é
intermediário entre um arquivo e uma máquina que corta material caro. Todo teste
deve terminar perguntando *"o que sai do outro lado bate com o que foi
mostrado?"* — e a resposta tem que vir de medir o arquivo, não de olhar a tela.
