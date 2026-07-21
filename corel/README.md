# Integração CorelDRAW → PrintNest

> **⚠️ TAREFA ÚNICA DO DONO (Philipe): gerar o `PrintNest.gms`.** O instalador
> do cliente (`instalar_plugin_corel.bat`) copia um arquivo `PrintNest.gms`
> para as pastas GMS do Corel — e o `.gms` só pode ser criado DENTRO do
> CorelDRAW (é um projeto VBA compilado). Fazer UMA vez, na sua máquina:
> 1. Abra o CorelDRAW → **Alt+F11**;
> 2. Menu **File → Import File...** com o projeto **GlobalMacros** selecionado
>    → escolha `corel/PrintNest.bas` → **Ctrl+S**;
> 3. Feche o Corel. O arquivo do projeto fica em
>    `%APPDATA%\Corel\CorelDRAW Graphics Suite <versão>\Draw\GMS\`
>    (o `.gms` das GlobalMacros — normalmente `GlobalMacros.gms`). Copie-o
>    para esta pasta `corel/` com o nome **`PrintNest.gms`**.
> 4. Rode o `build.bat`: o pacote "Plugin CorelDRAW" do build passa a incluir
>    o `.gms` e o instalador do cliente vira 2 cliques.
> Sem o `.gms`, o instalador cai no modo manual (importar o `.bas`), que
> também funciona — só é menos "2 cliques".
>
> **Novidade 09/07:** o cliente NÃO configura mais caminho nenhum — o
> PrintNest grava onde está (`%APPDATA%\PrintNest\printnest_path.txt`) a cada
> abertura e a macro lê de lá.

Botão no CorelDRAW que envia o desenho direto para o PrintNest (estilo RDWorks).
Você desenha no Corel, clica no botão e o arquivo cai no PrintNest já pronto. A
**linha de corte desenhada como vetor** vai no PDF e o PrintNest a usa como
**"Faca do cliente (vetor do PDF)"**.

## Como funciona
1. A macro exporta a página (ou a seleção) para um **PDF temporário**,
   preservando os vetores (inclusive a faca/corte).
2. Dispara o `PrintNest.exe` passando o caminho do PDF.
3. O PrintNest é **instância única**: se já estiver aberto, o arquivo entra na
   **sessão atual** (não abre outra janela). Se estiver fechado, abre com o
   arquivo já carregado.

## Instalação (uma vez)

1. Abra o CorelDRAW.
2. Pressione **Alt+F11** (Editor de VBA). Se não abrir, ative o VBA em
   *Opções → VBA* (em algumas versões é o "GMS"/Macros).
3. No editor: **Arquivo → Importar Arquivo...** e escolha `PrintNest.bas`
   (este arquivo está na pasta `corel/` do projeto).
4. Ainda no editor, abra o módulo **PrintNest** e ajuste a constante
   `PRINTNEST_EXE` com o caminho do seu `PrintNest.exe` (se não estiver no
   padrão `C:\Program Files\PrintNest\PrintNest.exe`).
   - **Para testar sem buildar o .exe** (durante o desenvolvimento): aponte
     `PRINTNEST_EXE` para `corel\run_printnest_dev.bat` (caminho completo). Ele
     roda o PrintNest direto do código.
5. Feche o editor (Alt+Q).

### Criar o botão na barra (com a logo do PrintNest)
1. CorelDRAW → **Ferramentas → Opções → Personalização → Comandos** (o caminho
   varia por versão; procure por *Macros* na lista de comandos).
2. Encontre **PrintNest.EnviarParaPrintNest** (é o **botão inteligente**: com
   algo selecionado envia a seleção; sem seleção envia a página).
3. **Arraste** o comando para uma barra de ferramentas.
4. Para colocar a **logo**: com o botão ainda selecionado na janela de
   Personalização, vá na aba **Aparência** (Appearance) → **Importar** e
   escolha:
   ```
   c:\projetos\Cutph\assets\printnest_symbol.png
   ```
   Em **Estilo**, escolha "Imagem" (ou "Imagem e texto"). Defina o nome para
   "Enviar p/ PrintNest".

> Atalho alternativo: dá para rodar por **Ferramentas → Macros → Executar
> Macro**, escolher `EnviarParaPrintNest` e clicar Executar.

## Macros disponíveis
- **PrintNestMenu** — **botão único com as duas opções** (novidade 21/07):
  pergunta se é **Importar (impressão/faca)** ou **Modo Corte**. O Modo Corte
  exporta a seleção (ou a página) **com o texto convertido em curvas** e abre
  a janela de nesting laser/CNC **por cima do Corel, já organizando**.
  Processo próprio: não mexe na sessão de impressão aberta.
- **ModoCorteNoPrintNest** — botão direto do **Modo Corte**, para quem quiser
  um ícone dedicado (tesoura) na barra.
- **ImportarDoPrintNest** — *não é botão*: é a função que o botão
  **"Enviar p/ Corel"** do Modo Corte chama por COM para jogar o arranjo
  organizado (curvas magenta) na página ativa. Precisa estar no GMS para o
  Enviar p/ Corel funcionar.
- **EnviarParaPrintNest** — **botão principal (inteligente)**: com objetos
  selecionados, envia **só a seleção** (recortado); sem seleção, envia a
  **página** inteira. Um clique faz o certo.
- **EnviarSelecaoParaPrintNest** — força o envio da **seleção**.
- **EnviarPaginaParaPrintNest** — força o envio da **página** inteira.
- **AbrirPrintNest** — só **abre o PrintNest** (ou traz a janela já aberta para
  a frente). Não envia arquivo. Bom para um botão "Abrir PrintNest" na barra.

## "Chegou como imagem?" (vetor vs. raster)
A **visualização** no PrintNest é sempre um *render* (imagem) da página — isso
vale para qualquer PDF e **não** quer dizer que o dado virou raster. O que
importa:
- Se você desenhou em **vetor** no Corel (curvas/linhas), o PDF mantém o vetor.
- A **linha de corte** desenhada como vetor é lida pelo PrintNest em
  **Faca de PDF → "Faca do cliente (vetor do PDF)"** → a faca sai como vetor
  real (DXF de corte).
- Arte com **imagem/foto** (JPG colado) continua raster — porque já era raster
  no Corel. Só o que era vetor permanece vetor.

## Dicas de produção
- Desenhe a **linha de corte como vetor** (uma curva/linha). No PrintNest,
  escolha **Faca de PDF → "Faca do cliente (vetor do PDF)"** para usar esse
  corte. A faca sai **verde** com o aviso de detecção.
- Trabalhe com **1 design por página** para o "Enviar página" ficar exato; ou
  selecione o que quer e use o "Enviar seleção".

## Solução de problemas
- **"PrintNest não encontrado"**: ajuste `PRINTNEST_EXE` no topo da macro
  (Alt+F11 → módulo PrintNest).
- **Aviso de segurança de macro**: o Corel pode pedir para habilitar macros;
  em produção, vale **assinar** a macro para não aparecer o aviso.
- **Abre outra janela em vez de cair na sessão aberta**: confirme que é a
  mesma versão/instalação do PrintNest (a instância única usa um canal local
  por usuário).
