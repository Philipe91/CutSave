# PrintNest Pro 1.2.1 — Notas da versão

**11 de setembro de 2026**

Esta versão corrige a **demora na exportação em imagem** de arte CMYK e traz
uma **janela de acompanhamento** para essa exportação. Instale por cima da
versão que você já tem: sua licença e suas configurações são preservadas.

---

## O que foi corrigido

**Exportar uma chapa em imagem (JPEG/PNG) com arte CMYK levava minutos, e o
programa parecia travado.**

Uma chapa de 1120 × 1750 mm com 40 cópias de um JPEG CMYK, exportada em JPEG a
300 DPI, passava de 10 minutos com a janela marcada como "Não está
respondendo". Não era travamento — o programa terminava — mas não havia como
saber disso, e era fácil fechá-lo no meio.

O motivo: a 1.2.0 passou a guardar a imagem CMYK **com o perfil de cor** no
documento que o rasterizador lê (o que é correto para o PDF de impressão). Só
que, na exportação em imagem, o rasterizador convertia esse CMYK pixel a
pixel, de novo para **cada cópia em cada faixa** da chapa.

Agora a conversão é feita **uma vez por arquivo**, com o mesmo perfil e o
mesmo resultado — a cor da imagem exportada é a mesma da 1.2.0 (medido:
diferença média de 0,04 em 255 por canal, invisível). A mesma chapa sai em
cerca de **45 segundos**.

A exportação em **PDF** não mudou: continua entregando as tintas originais da
arte ao RIP, sem passar por RGB.

---

## O que foi acrescentado

**Janela de acompanhamento na exportação em imagem.**

A exportação agora roda em segundo plano, e uma janela mostra:

| O quê | Para quê |
|---|---|
| **Etapa** | Montando o documento → Exportando → Convertendo para CMYK → Gravando arquivo |
| **Barra de progresso** | por faixa da chapa |
| **Tempo** | decorrido, e estimativa do restante a partir de ~10% |
| **Dicas** | uma dica de uso a cada 6 segundos, enquanto você espera |
| **Cancelar** | interrompe entre faixas (poucos segundos) e **não deixa arquivo pela metade** na pasta |

O programa não fica mais "Não está respondendo" durante a exportação.

---

## Como conferir

1. Importe uma arte **CMYK** sua, monte uma chapa cheia e vá em **Centro de
   Exportação** (Ctrl+E) → JPEG, 300 DPI, CMYK.
2. A janela "Exportando imagem" aparece e a barra de título do PrintNest
   continua normal.
3. A chapa sai em menos de um minuto e abre no Corel/Photoshop como CMYK, com
   perfil embutido, igual à da 1.2.0.
4. Exporte de novo e clique **Cancelar**: a janela fecha em poucos segundos e
   não há arquivo novo na pasta.

Lembrete da 1.2.0, que continua valendo: **para cor fiel à arte, exporte em
PDF** — a imagem é conversão e serve para conferência e preview.
