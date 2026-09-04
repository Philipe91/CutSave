# PrintNest Pro 1.2.0 — Notas da versão

**4 de setembro de 2026**

Esta versão corrige um defeito de **cor na impressão** e traz a escolha de
**RGB ou CMYK** na exportação em imagem. Instale por cima da versão que você já
tem: sua licença e suas configurações são preservadas.

---

## O que foi corrigido

**A arte exportada saía com a cor trocada.**

Quem mandava para o PrintNest um arquivo em CMYK — um JPEG fechado pela
gráfica, por exemplo — via a chapa impressa com cor visivelmente diferente da
arte original.

O motivo: na hora de montar a chapa, o PrintNest reescrevia **toda** imagem
como RGB. Um ciano de 100% virava o ciano de monitor, e o RIP, ao separar
aquele RGB de volta para tinta, produzia uma mistura das quatro cores em vez do
ciano puro. Arquivos que traziam um perfil de cor embutido (Adobe RGB, o perfil
da sua gráfica) perdiam esse perfil e passavam a ser lidos como se fossem
sRGB — o que desloca a imagem inteira.

Agora o arquivo sai **no mesmo espaço de cor em que entrou**:

- CMYK continua CMYK, com as quatro tintas idênticas às do arquivo original;
- tons de cinza continuam em um canal só, sem virar três;
- o perfil de cor embutido no seu arquivo viaja junto para o PDF;
- o *OutputIntent* da arte (o "qual CMYK é este CMYK": Coated FOGRA39, o perfil
  da sua gráfica) é herdado pela chapa, em vez de o RIP ter de adivinhar;
- em trabalho CMYK, as **marcas de registro** passam a sair em preto puro (só o
  canal K). Antes saíam em preto de quatro cores, que sai fora de registro e
  atrapalha a leitura óptica da mesa de corte.

O JPEG também deixou de ser recomprimido: os bytes originais entram no PDF sem
nova compressão, então não há perda de qualidade nem inchaço do arquivo.

---

## O que foi acrescentado

**Escolha de RGB ou CMYK ao exportar imagem.**

Na tela de exportação em imagem — tanto pelo menu **Exportar Imagem
(PNG/JPEG)** quanto pelo **Centro de Exportação** (Ctrl+E) — você agora
escolhe:

| Opção | Para quê |
|---|---|
| **Espaço de cor** | RGB ou CMYK |
| **Perfil** | os perfis de cor instalados no seu Windows, ou o `.icc` da sua gráfica pelo botão *Escolher…* |
| **Qualidade (JPEG)** | segura o tamanho do arquivo em chapa grande |

Se a arte da chapa for CMYK, a tela já abre em CMYK.

---

## Uma limitação que você precisa conhecer

**Para cor fiel à arte, exporte em PDF — não em imagem.**

A exportação em **PDF** preserva as tintas do arquivo original exatamente como
elas entraram. É a rota correta para impressão.

A exportação em **imagem** (PNG/JPEG) passa obrigatoriamente por uma
rasterização em RGB antes de virar arquivo. Quando você escolhe CMYK ali, o
PrintNest converte esse RGB de volta para CMYK usando o perfil que você
escolheu — e **tinta pura não sobrevive à ida e volta**: um preto de 100% K
volta como preto de quatro cores.

Isso não é uma perda nova: antes desta versão a mesma conversão acontecia, só
que dentro do RIP, com um perfil que ninguém escolheu. A diferença é que agora
a conversão está sob o seu controle e o perfil vai gravado dentro do arquivo.

Resumindo: **imagem serve para conferência e preview; PDF é o que vai para a
impressão.**

E o PNG nunca guarda CMYK — é uma limitação do próprio formato, não do
PrintNest. Escolhendo PNG, a imagem sai em RGB.

---

## Como conferir que a correção funcionou

1. Importe um arquivo **CMYK** seu — de preferência o mesmo que saiu com a cor
   errada antes.
2. Monte a chapa normalmente e exporte em **PDF**.
3. Abra o PDF no Acrobat e vá em **Exibir → Ferramentas → Produção de impressão
   → Visualização de saída**.
4. Confira: as separações devem aparecer em **CMYK** (não em RGB), e um ciano
   de 100% deve aparecer só no canal do ciano.
5. As marcas de registro devem aparecer **apenas no canal K**.

Se algo aí não bater, fale com o suporte com o arquivo em mãos — é exatamente o
tipo de caso que precisamos ver.
