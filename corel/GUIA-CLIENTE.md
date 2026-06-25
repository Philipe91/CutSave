# PrintNest no CorelDRAW — Guia de Instalação (Cliente)

Este guia coloca um **botão do PrintNest** dentro do CorelDRAW. Depois de
instalado, você desenha no Corel, clica no botão e o arquivo vai direto para o
PrintNest — pronto para gerar a faca e cortar.

> Faça uma vez. Depois é só clicar no botão no dia a dia.

---

## Passo 1 — Importar o botão (a macro)

1. Abra o **CorelDRAW**.
2. Pressione **Alt + F11** (abre o editor de macros).
   - *Se não abrir:* vá em **Ferramentas → Opções → CorelDRAW → VBA** e ative o
     VBA; feche e abra o Corel de novo.
3. No editor, do lado esquerdo, clique com o **botão direito** em
   **GlobalMacros** → **Import File...** (Importar Arquivo).
4. Selecione o arquivo **`PrintNest.bas`** (entregue junto com o programa) e
   clique **Abrir**.
5. Salve com **Ctrl + S** e feche o editor (**Alt + Q**).

---

## Passo 2 — Apontar para o PrintNest

1. **Alt + F11** de novo → na esquerda, abra **GlobalMacros → PrintNest** (duplo
   clique).
2. Lá no alto, ache a linha:
   ```
   Private Const PRINTNEST_EXE As String = "C:\Program Files\PrintNest\PrintNest.exe"
   ```
3. Se o seu PrintNest estiver instalado em outro lugar, troque **só o texto
   entre as aspas** pelo caminho do `PrintNest.exe`. Se estiver no padrão, não
   precisa mexer.
4. **Ctrl + S** → **Alt + Q**.

---

## Passo 3 — Criar o botão na barra (com a logo)

1. No CorelDRAW: **Ferramentas → Opções → Personalização → Comandos**.
   *(Em algumas versões: **Ferramentas → Personalização → Comandos**.)*
2. No alto do painel **Comandos**, troque o filtro (lista suspensa) para
   **Macros**.
3. Na lista, ache **PrintNest.EnviarParaPrintNest**.
4. **Arraste** esse item para uma barra de ferramentas do Corel (ex.: a barra
   de cima). Vai aparecer um botão.
5. **Colocar a logo:** com o item ainda selecionado, clique na aba
   **Aparência** (à direita) → **Importar** → escolha a imagem
   **`printnest_symbol.png`** (entregue junto). Em **Estilo**, escolha
   *Imagem* (ou *Imagem e texto*).
6. (Opcional) Na aba **Geral**, ajuste o nome para **"Enviar p/ PrintNest"**.
7. Clique **OK**.

Pronto — o botão do PrintNest está na barra. 🎉

> **Dica:** repita o Passo 3 para criar também o botão **AbrirPrintNest**
> ("Abrir PrintNest"), se quiser um botão só para abrir o programa.

---

## Como usar no dia a dia

1. Desenhe a arte no CorelDRAW. **Desenhe a linha de corte como vetor**
   (uma curva/linha).
2. Clique no botão **Enviar p/ PrintNest**.
   - Com algo **selecionado**, envia só a seleção.
   - Sem seleção, envia a página inteira.
3. No PrintNest, escolha **Faca de PDF → "Faca do cliente (vetor do PDF)"** e
   clique **Gerar Faca**. A faca sai **verde** seguindo o seu corte.
4. Organize, e exporte (**Ctrl + E**): PDF de impressão e DXF de corte.

---

## Botões disponíveis (para montar a barra)

| Botão (macro) | O que faz |
|---|---|
| **EnviarParaPrintNest** | Inteligente: envia a seleção (se houver) ou a página |
| **EnviarSelecaoParaPrintNest** | Envia só a seleção |
| **EnviarPaginaParaPrintNest** | Envia a página inteira |
| **AbrirPrintNest** | Só abre / traz o PrintNest para a frente |

---

## Problemas comuns

- **"PrintNest não encontrado"** → o caminho no Passo 2 está errado. Ajuste com
  o local real do `PrintNest.exe`.
- **Aviso de segurança ao rodar a macro** → o Corel pede para permitir macros;
  aceite. (Na versão final, a macro vem assinada e o aviso some.)
- **Não acho "Macros" no filtro de Comandos** → confirme que o VBA está ativo
  (Passo 1) e que a macro foi importada no **GlobalMacros**.
