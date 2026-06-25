# Integração CorelDRAW → PrintNest

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

### Criar o botão na barra
1. CorelDRAW → **Ferramentas → Opções → Personalização → Comandos** (o caminho
   varia por versão; procure por *Macros* na lista de comandos).
2. Encontre **PrintNest.EnviarParaPrintNest** (e/ou
   **PrintNest.EnviarSelecaoParaPrintNest**).
3. **Arraste** o comando para uma barra de ferramentas. Pode trocar o
   ícone/nome (ex.: "Enviar p/ PrintNest").

> Atalho alternativo: dá para rodar por **Ferramentas → Macros → Executar
> Macro**, escolher `EnviarParaPrintNest` e clicar Executar.

## Macros disponíveis
- **EnviarParaPrintNest** — envia a **página** atual.
- **EnviarSelecaoParaPrintNest** — envia **apenas a seleção** (se nada estiver
  selecionado, envia a página).

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
