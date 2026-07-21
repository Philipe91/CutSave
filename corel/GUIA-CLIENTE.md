# PrintNest no CorelDRAW — Instalação do plugin (Cliente)

Coloca um **botão do PrintNest** dentro do CorelDRAW com dois caminhos:

- **Importar** → o desenho cai no PrintNest para impressão e faca;
- **Modo Corte** → abre a janela de nesting (laser/CNC) **já organizando** o
  que você selecionou, e devolve o arranjo pronto **na página do Corel** ou
  em **DXF** para a máquina.

> Instala uma vez. Depois é só clicar no botão no dia a dia.

As imagens deste guia ficam na pasta `imagens/` ao lado deste arquivo.

---

## Instalação (2 minutos)

1. **Abra o PrintNest uma vez** (dois cliques no `PrintNest.exe`). Pode fechar
   em seguida — ele se registra sozinho para o Corel encontrá-lo.
2. Na pasta **Plugin CorelDRAW** (veio junto do programa), dê dois cliques em
   **`instalar_plugin_corel.bat`**. Ele acha o seu CorelDRAW e instala o
   plugin em todas as versões que você tiver.
3. Abra o CorelDRAW e crie o botão (só na primeira vez):
   - **Ferramentas → Opções → Personalização → Comandos**
     *(em algumas versões: Ferramentas → Personalização → Comandos)*
     ![Menu Ferramentas](imagens/01-abrir-personalizacao.png)
   - Na lista suspensa no alto (onde diz "Ajuda"), escolha **Macros**;

     ![Escolher Macros](imagens/02-filtro-macros.png)

   - Ache **PrintNest.PrintNestMenu** na lista e **arraste** para a barra
     de ferramentas de cima;

     ![Arrastar o botão](imagens/03-arrastar-botao.png)

   - (Opcional, fica bonito) com o item ainda selecionado, na aba **Geral**
     ao lado, clique em **Ícone → Procurar...** e escolha a imagem
     `printnest_symbol.png` da pasta do plugin.

     ![Colocar a logo](imagens/04-aparencia-logo.png)

Pronto! 🎉

---

## Como usar no dia a dia

### Impressão + faca (como sempre)
1. Desenhe a arte. **A linha de corte, desenhe como vetor** (curva).
2. Selecione (ou deixe sem seleção para mandar a página inteira) e clique no
   botão **PrintNest** → **[Sim] Importar**.
3. No PrintNest: Tipo de faca **"Faca do cliente (vetor do PDF)"** → **Gerar
   Faca**.

### Modo Corte (laser/CNC)
1. Selecione as peças ou o texto no Corel (texto **não** precisa converter em
   curvas — o plugin converte sozinho).
2. Botão **PrintNest** → aparece a pergunta → **[Não] Modo Corte**.

   ![As duas opções](imagens/07-popup-duas-opcoes.png)

   A janela abre **já organizando** as peças pelo contorno real.

   ![Modo Corte organizado](imagens/05-modo-corte-organizando.png)
3. Ajuste se quiser: **Giro das peças** (mais fino = encaixe mais denso, um
   pouco mais demorado) e **Tempo de otimização** (mais tempo = melhor
   aproveitamento). Clique **Organizar** de novo.

   **Preencher furos (peça dentro de peça)** aproveita o vão interno das
   peças — o miolo do "O", o buraco do "8" — para encaixar as peças menores.
   Vem ligado e pode ficar assim: o programa testa **com e sem** o vão e fica
   com o que render mais, então ligar não estraga um encaixe que já estava
   bom. O ganho grande aparece quando há peças pequenas junto de peças com
   vão largo. Como a conta fica mais pesada, em lote grande vale subir o
   **Tempo de otimização** para 30–60s.

   No DXF o corte sai **de dentro para fora**: primeiro a peça que ficou
   dentro do vão, depois os furos, e o contorno externo por último. Se a
   máquina fechasse o contorno de fora primeiro, a peça se soltaria da chapa
   e o que faltava cortar sairia desalinhado.
4. Escolha a saída:
   - **Enviar p/ Corel** → o arranjo volta para a página do Corel como
     **curvas magenta editáveis** — ajuste fino, duplicação, o que quiser;
     ![Enviar para o Corel](imagens/06-enviar-para-corel.png)
   - **Exportar DXF** → arquivo em milímetros, layer CUT, direto na máquina.

## Botões disponíveis (se quiser mais de um)

| Macro | O que faz |
|---|---|
| **PrintNestMenu** | **Recomendado**: pergunta Importar ou Modo Corte |
| **ModoCorteNoPrintNest** | Vai direto ao Modo Corte, sem perguntar |
| **EnviarParaPrintNest** | Importa: seleção (se houver) ou a página |
| **EnviarSelecaoParaPrintNest** | Importa só a seleção |
| **EnviarPaginaParaPrintNest** | Importa a página inteira |
| **AbrirPrintNest** | Só abre/traz o PrintNest para frente |

---

## Problemas comuns

- **"PrintNest não encontrado"** → abra o PrintNest uma vez (passo 1) e tente
  de novo. Ele se registra sozinho a cada abertura.
- **O instalador não achou o CorelDRAW** → abra o CorelDRAW uma vez (para ele
  criar as pastas de usuário) e rode o instalador de novo.
- **Aviso de segurança de macro** → aceite/permita; é o plugin do PrintNest.
- **Cliquei no botão e nada aconteceu** → o botão perdeu o vínculo (acontece
  quando o plugin é reinstalado). Remova o botão (Personalização aberta →
  arraste-o para fora da barra) e crie de novo (passo 3 da instalação).
- **"Enviar p/ Corel" reclama da macro** → rode o `instalar_plugin_corel.bat`
  de novo (a função de importação faz parte do plugin).
- **Instalador sem o arquivo PrintNest.gms** → dá para instalar manualmente em
  2 minutos: abra o Corel, **Alt+F11**, botão direito em **GlobalMacros** →
  **Import File...** → escolha o `PrintNest.bas` da pasta do plugin → **Ctrl+S**.
  Depois siga o passo 3 acima para criar o botão.
