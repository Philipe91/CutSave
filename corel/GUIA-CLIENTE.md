# PrintNest no CorelDRAW — Instalação do plugin (Cliente)

Coloca um **botão do PrintNest** dentro do CorelDRAW: você desenha, clica e o
arquivo cai direto no PrintNest, pronto para gerar a faca.

> Instala uma vez. Depois é só clicar no botão no dia a dia.

---

## Instalação (2 minutos)

1. **Abra o PrintNest uma vez** (dois cliques no `PrintNest.exe`). Pode fechar
   em seguida — ele se registra sozinho para o Corel encontrá-lo.
2. Na pasta **Plugin CorelDRAW** (veio junto do programa), dê dois cliques em
   **`instalar_plugin_corel.bat`**. Ele acha o seu CorelDRAW e instala o
   plugin em todas as versões que você tiver.
3. Abra o CorelDRAW e crie o botão (só na primeira vez):
   - **Ferramentas → Opções → Personalização → Comandos**
     *(em algumas versões: Ferramentas → Personalização → Comandos)*;
   - No filtro (lista suspensa no alto), escolha **Macros**;
   - **Arraste** o item **PrintNest.EnviarParaPrintNest** para a barra de cima;
   - (Opcional, fica bonito) aba **Aparência** → **Importar** → escolha a
     imagem `printnest_symbol.png` da pasta do plugin.

Pronto! 🎉

---

## Como usar no dia a dia

1. Desenhe a arte no Corel. **A linha de corte, desenhe como vetor** (curva).
2. Clique no botão **PrintNest**:
   - com algo **selecionado**, envia só a seleção;
   - sem seleção, envia a página inteira.
3. No PrintNest: Tipo de faca **"Faca do cliente (vetor do PDF)"** → **Gerar
   Faca**. A faca sai seguindo exatamente o seu corte.

## Botões disponíveis (se quiser mais de um)

| Macro | O que faz |
|---|---|
| **EnviarParaPrintNest** | Inteligente: seleção (se houver) ou a página |
| **EnviarSelecaoParaPrintNest** | Só a seleção |
| **EnviarPaginaParaPrintNest** | A página inteira |
| **AbrirPrintNest** | Só abre/traz o PrintNest para frente |

---

## Problemas comuns

- **"PrintNest não encontrado"** → abra o PrintNest uma vez (passo 1) e tente
  de novo. Ele se registra sozinho a cada abertura.
- **O instalador não achou o CorelDRAW** → abra o CorelDRAW uma vez (para ele
  criar as pastas de usuário) e rode o instalador de novo.
- **Aviso de segurança de macro** → aceite/permita; é o plugin do PrintNest.
- **Instalador sem o arquivo PrintNest.gms** → dá para instalar manualmente em
  2 minutos: abra o Corel, **Alt+F11**, botão direito em **GlobalMacros** →
  **Import File...** → escolha o `PrintNest.bas` da pasta do plugin → **Ctrl+S**.
  Depois siga o passo 3 acima para criar o botão.
