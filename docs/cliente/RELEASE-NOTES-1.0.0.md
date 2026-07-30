# PrintNest Pro 1.0.0 — Notas da versão

**Primeira versão comercial** · 30 de julho de 2026

---

## O que é o PrintNest Pro

Software para preparar produção gráfica: você joga seus PDFs e imagens, ele
encaixa tudo na chapa aproveitando o material, gera a faca de corte e exporta o
PDF de impressão e o DXF para a máquina.

---

## O que vem nesta versão

### Encaixe automático na chapa

Adicione seus arquivos, diga quantas cópias de cada um e aperte **F5**. O
PrintNest distribui as peças na chapa, divide em quantas folhas forem
necessárias e mostra o aproveitamento. Você pode ajustar espaçamento, margem e
sangria e ver o resultado na hora.

### Faca de corte

Seis modos, para o material chegar no formato certo:

- **Automático** — decide sozinho pelo tipo de arquivo
- **Retângulo** — o contorno mais simples
- **Contorno justo, suave ou simplificado** — acompanha o desenho
- **Faca do cliente** — se o seu PDF já vem do Corel com a linha de corte
  desenhada (traço magenta 100%, sem preenchimento), o PrintNest usa ela

### Modo Corte (laser, CNC, plotter)

Para trabalho só de corte, sem impressão. Importa SVG e PDF vetorial, converte
texto digitado em curvas, encaixa as peças pela forma real — não pelo retângulo
em volta — inclusive aproveitando o espaço **dentro** de peças vazadas. Exporta
DXF cortando de dentro para fora, como a máquina espera.

Dá para arrastar e girar peça a peça no preview, e desfazer com **Ctrl+Z**.

### Marcas de registro

Seis formatos, escolhidos pela forma e não pelo nome da máquina: bolinhas,
marcas em L, bolinhas + L, quadrados, cruzes e L de canto. Distância, tamanho e
espessura do traço são ajustáveis e ficam salvos no projeto.

### Plugin do CorelDRAW

Um botão dentro do Corel que manda o desenho direto para o PrintNest — e traz o
arranjo de volta. Instala em dois minutos com o guia ilustrado que vem no
pacote, na pasta **Plugin CorelDRAW**.

### Exportação

PDF de impressão com os vetores preservados, DXF em milímetros com layers
separadas, imagem em alta resolução e formatos específicos para Mimaki e iECHO.
O Centro de Exportação (**Ctrl+E**) mostra as miniaturas para você escolher
quais chapas sair.

### Trabalhando no dia a dia

- **Abas** para vários projetos abertos ao mesmo tempo
- **Ctrl+Z** com histórico profundo no arranjo
- Projetos salvos em `.printnest`, reabrem exatamente como estavam — inclusive
  as peças que você moveu na mão
- Temas claro, escuro, Midnight e Carbon, com editor de cores completo
- Tour de boas-vindas na primeira abertura e tutoriais mão na massa
- Atalhos no padrão CorelDRAW

### Aprendendo a usar

Junto do programa vem o **"Tutor IA - PrintNest.pdf"**. Envie esse arquivo num
chat de inteligência artificial (Claude, ChatGPT, Gemini) e aperte Enter: ela
vira uma especialista no PrintNest e responde suas dúvidas em português, do
básico ao avançado, a qualquer hora.

---

## Instalação

1. Execute o **PrintNest-Setup-1.0.0.exe**
2. O Windows vai mostrar um aviso azul — *"o Windows protegeu seu computador"*.
   Clique em **Mais informações** e depois em **Executar assim mesmo**. Esse
   aviso aparece em todo programa novo que ainda não acumulou downloads; não é
   vírus.
3. Siga o assistente e aceite os termos de uso
4. Na primeira abertura, o PrintNest pede a ativação

**Ativação:** a tela mostra o **ID da Máquina** do seu computador. Envie esse ID
junto com o seu código de compra, e você recebe a chave por e-mail. Cole no
campo indicado e clique em Ativar. A licença é perpétua e vale para este
computador.

**Requisitos:** Windows 10 ou 11, 64 bits. Não precisa instalar mais nada — o
programa já vem completo.

---

## Trocando de computador

Abra **Ajuda → Licença → Desativar (transferir de PC)**. A licença é liberada e
pode ser ativada na máquina nova. Desinstalar o PrintNest **não** apaga a sua
licença.

---

## Atualizações

O PrintNest confere sozinho se há versão nova, sem atrapalhar seu trabalho. Você
também pode conferir quando quiser em **Ajuda → Procurar atualizações**.

---

## Antes de começar

Leia o **PROBLEMAS-CONHECIDOS-1.0.0.md**, que vem nesta mesma pasta. São poucos
itens, todos com solução, e conhecê-los evita perder tempo com algo que já
sabemos e já está na fila de correção.

---

## Suporte

**philipe.fernandes0101@gmail.com**

Ao relatar um problema, conte o que você fez, o que esperava e o que aconteceu.
Se puder, mande um print. Se o programa fechou sozinho, o arquivo
`crash.log` na pasta `%APPDATA%\PrintNest\logs` ajuda muito a encontrar a causa
— é só copiar o endereço e colar no Explorer do Windows.
