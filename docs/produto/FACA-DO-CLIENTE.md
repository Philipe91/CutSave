# Faca do cliente — como montar o arquivo PDF

Guia para o cliente (ou para a gráfica orientar o cliente) preparar um PDF em
que o PrintNest reconhece a **linha de corte que já veio desenhada** — em vez
de gerar uma faca por conta própria.

**Não precisa configurar nada:** no modo padrão (Tipo de faca = Automática),
se o PDF tiver uma linha magenta o PrintNest a usa como faca sozinho (aviso
azul na barra). O modo **"Faca do cliente (vetor do PDF)"** força o
comportamento e aceita também as pistas mais fracas (spot/traço sem cor).

**Fidelidade:** a faca do cliente sai 1:1 com o desenho — o PrintNest não
suaviza, não simplifica e não mexe nos nós. "Sangria da faca" ≠ 0 e "Cantos
arredondados" continuam valendo, se o usuário pedir.

**A linha magenta NÃO imprime:** como um RIP faz com a spot CutContour, o
PrintNest remove os traços magenta da impressão, do preview e das
miniaturas — eles são instrução de corte, não arte. O arquivo original do
cliente fica intacto. (Limite: a linha precisa estar no nível da página do
PDF, que é como Corel/Illustrator exportam; dentro de grupos "achatados" em
XObject ela não é removida.)

## A regra de ouro

> Desenhe a faca como **traço vetorial magenta 100% (rosa choque), sem
> preenchimento**, por cima da arte, e exporte em **PDF**.

É a convenção universal das gráficas (a mesma da spot color *CutContour* da
Roland/Mimaki). O PrintNest procura a faca nesta ordem:

1. **Traço magenta/rosa** — RGB 255,0,255 ou CMYK 0/100/0/0 (é o que a spot
   CutContour vira no PDF). É o caminho garantido.
2. **Cor spot não resolvida** — traço numa separação exótica que o leitor de
   PDF não converte; tratado como faca.
3. **Traço sem preenchimento** — se não há magenta, qualquer linha vetorial
   *só de contorno* vence a arte (arte é preenchida, faca é linha).
4. **Nada disso** — o sistema une todos os vetores e usa o contorno geral
   (comportamento antigo), com **aviso amarelo** para conferir o resultado.

A interface sempre diz o que encontrou: aviso azul "detectada pela linha
MAGENTA" = perfeito; aviso amarelo = o arquivo precisa de ajuste.

## Passo a passo no CorelDRAW

1. Desenhe/posicione a arte final (com sangria, se houver).
2. Desenhe o contorno de corte como **objeto vetorial fechado** (elipse,
   retângulo ou curva com nós fechados) exatamente onde a faca deve passar.
3. Selecione o contorno: **preenchimento = nenhum**; **caneta/outline =
   magenta** (CMYK 0/100/0/0 ou RGB 255,0,255). Espessura fina (ex.: 0,2 mm) —
   a espessura não vira faca, só o caminho conta.
4. Deixe a linha **por cima** da arte (Ctrl+PgUp / "Para frente").
5. Exporte/salve como **PDF** (Arquivo → Publicar em PDF). Não converta a
   linha em bitmap; não achate ("flatten") os vetores.

No Illustrator é igual: traço magenta (ou spot "CutContour"), sem fill,
salvar como PDF.

## Erros comuns (o que faz "não dar certo")

| Sintoma | Causa | Correção |
|---|---|---|
| Faca saiu retangular | A linha de corte não é vetor (virou imagem/bitmap ao exportar) | Reexportar mantendo vetores; nunca rasterizar |
| Faca pegou o contorno da arte, não o corte | Linha de corte sem cor magenta e arte cheia de vetores | Pintar o traço de magenta 100% |
| Faca com "dentes"/pontas a mais | Vários objetos magenta soltos (dobras, marcações) | Deixar só o corte em magenta; dobras em outra cor |
| Nada detectado (aviso amarelo) | PDF só tem imagem (JPG/foto de fundo) e nenhum vetor | Desenhar o corte como vetor por cima e reexportar |
| Corte deslocado | Página do PDF maior que a arte (área de trabalho sobrando) | Ajustar a página ao conteúdo antes de exportar |

## Detalhe técnico (para manutenção)

- Extração: `PdfiumVectorExtractor.extract_rings_info` (pypdfium2) devolve
  cada path com `stroked/filled/stroke_rgb`.
- Seleção: `select_cut_rings` em `app/domain/cut/vector.py` (tiers
  magenta → spot → stroke → all); cor de faca = `is_knife_color`
  (r≥180, g≤100, b≥100 — cobre 255,0,255 e o alternate ~236,0,140 da
  CutContour).
- União/contorno externo: `VectorContourGenerator` (Shapely, maior
  componente, anel externo).
- Avisos ao usuário: `_pdf_vector_contour` no `main_window.py`
  (`_faca_notice`).
- Testes: `tests/infrastructure/test_pdfium_vector_extractor.py`
  (arte + faca magenta; só-traço; tudo preenchido).
