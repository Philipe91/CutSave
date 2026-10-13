# PrintNest Pro 1.2.2 — Notas da versão

**13 de outubro de 2026**

Esta versão é uma **varredura de qualidade**: o programa inteiro foi revisado
em busca de defeitos, e cerca de 55 foram corrigidos. Instale por cima da
versão que você já tem: sua licença e suas configurações são preservadas.

---

## Tela e monitores

- **Monitor menor:** com uma peça selecionada, os campos da "Faca deste
  arquivo" saíam uns por cima dos outros. Agora o painel rola.
- **Barra de cima no estilo do CorelDRAW:** quando a janela é estreita, o que
  não cabe vai para o botão **»** na ponta direita, em vez de ser cortado.
- **Segundo monitor:** ícones nítidos mesmo quando o outro monitor usa outra
  escala do Windows.
- Avisos legíveis nos temas escuros; o tema "Automático" volta a seguir o
  Windows.

## Faca

- Imagem com uma **moldura fina invisível na borda** gerava faca retangular.
  Agora gera o contorno da arte.
- **Faca do PDF do cliente** não fica mais deslocada da arte em PDFs com
  caixas de página diferentes.
- **Modo Corte:** contornos vizinhos não se invadem mais, e "Organizar" pode
  ser cancelado.
- **Faca compartilhada** com peças de tamanhos diferentes corta todas as peças.

## Impressão e encaixe

- Uma peça quase da largura do rolo não faz mais a próxima ser posta **em
  cima dela**.
- **PDF com página girada** e **foto de celular** imprimem como aparecem na
  prévia.
- PNG em cinza de 16 bits não sai mais branco; banners muito grandes abrem.
- Exportação cancelada ou com erro não deixa arquivo pela metade.

## Projeto e janela

- O projeto `.printnest` salva os **recortes de página** e os **tamanhos** de
  cada arquivo. Projetos antigos abrem como antes.
- Trocar de aba durante a geração não joga mais o resultado na aba errada.
- Campos em cm aceitam qualquer valor válido; Ctrl+Z de tamanho funciona;
  ferramenta Mão (H) arrasta; o zoom tem limite.
- Configuração ou tema corrompido não impedem mais o programa de abrir.
- Abrir vários arquivos pelo Explorer ou pelo Corel abre uma janela só.

---

## Uma mudança que você pode notar

Em PDFs cuja área visível (CropBox) é menor que a folha, o PrintNest agora usa
a **área visível** — a mesma que o Acrobat mostra e imprime. Antes ele usava a
folha inteira, e tamanho, prévia e impressão não batiam.
