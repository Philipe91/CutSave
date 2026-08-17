# Curvas originais no Modo Corte — especificação

Data: 2026-08-17 · Origem: relato do Philipe (letras de acrílico do Hospital
Santa Lucia saindo facetadas no corte a laser) · Alvo: 1.1.3

## 1. Problema

Letras vetoriais desenhadas no CorelDRAW com curvas suaves chegam ao corte com
as curvas trocadas por sequências de retas. Em letra grande as cordas retas
ficam visíveis e o corte a laser perde qualidade de acabamento.

Medido no arquivo real do cliente
(`Logo Hospital Santa Lucia for printnest.pdf`, letras de até 264 × 336 mm):

| | nós | curvas Bézier |
|---|---|---|
| Original (PDF do Corel) | 720 | **365** |
| Depois do import do Modo Corte | 2.089 | **0** |

Entram 22 objetos de path, 37 subpaths, 318 retas e 365 curvas. Saem 2.089
vértices, todos retos — quase 3× mais nós e nenhuma curva.

### 1.1 Causa raiz

A curva é destruída **no import**. `PdfVectorImporter._object_rings` e
`SvgVectorImporter._flatten_subpath` chamam `flatten_curve` e guardam apenas
pontos; os pontos de controle da Bézier são descartados e não há como
recuperá-los depois. `Polygon` (e portanto `PolygonWithHoles`, `NestingShape`,
`CutContour`) só sabe representar vértices.

### 1.2 Por que só agora ficou óbvio

Existem duas saídas no Modo Corte e elas divergiram:

- **Exportar DXF** — `DxfExporter` chama `cubic_segments` (domain/cut/curves.py),
  que *adivinha* uma Bézier por cima dos pontos achatados e grava spline. Sai
  curvo, mas é reconstrução, não o original.
- **Enviar para o Corel** — `write_layout_svg._path_d` grava
  `"M " + " L ".join(...) + " Z"`. **Polilinha pura, nenhuma curva**, apesar de
  a docstring do módulo prometer "curvas do corte" e o `export_svg` do diálogo
  dizer "em curvas magenta". A intenção estava documentada; a implementação
  nunca chegou.

O relato do cliente veio pela rota "Enviar para o Corel".

### 1.3 Defeito secundário medido (fica FORA deste escopo)

O refit de `cubic_segments` decide "isto é canto vivo" comparando o giro entre
cordas com `CORNER_DEG = 32°`. Medindo círculos exatos achatados a 0,1 mm:

| raio | giro por corda | trechos que saem RETOS |
|---|---|---|
| 0,3 mm | 45° | 8 de 8 |
| 0,5 mm | 45° | 8 de 8 |
| 1,0 mm | 45° | 8 de 8 |
| 2,0 mm | 22,5° | 0 de 16 |
| 25 mm | 5,6° | 0 de 64 |

Abaixo de ~1,5 mm de raio o giro por corda passa de 32° e **todo** nó é lido
como canto: a curva sai facetada. Causa: a decisão de canto é tomada sobre a
polilinha já achatada, onde a informação de canto original já morreu.

No Modo Corte o defeito desaparece por consequência desta especificação (não
haverá mais refit). Ele **continua vivo na faca de impressão**
(`main_window.py`, que usa `cubic_segments` direto) e fica registrado como
pendência separada — ver seção 8.

## 2. Solução

Não reconstruir curva nenhuma. Carregar a Bézier original do arquivo ao lado
do polígono achatado, sem que o motor de encaixe a use, e escrevê-la na
exportação.

O fundamento geométrico: **rotação e translação não deformam Bézier.** Aplicar
o transform do encaixe aos pontos de controle produz a letra idêntica à do
Corel, na posição do arranjo.

Divisão de responsabilidade:

- **polígono achatado** — encaixe, contenção (furo x corpo), bounding box,
  desenho do preview. O motor de nesting continua intocado; ele lê `.vertices`,
  e o pyclipper reconstrói polígonos a partir de coordenadas, descartando as
  curvas sozinho. Esse descarte é o comportamento correto.
- **Bézier original** — só a exportação (SVG e DXF).

## 3. Arquitetura

### 3.1 Tipo de curva

`BezierSegment` (hoje em `app/domain/cut/curves.py`) desce para
`app/domain/geometry/bezier.py`. Motivo: `domain/geometry` é a camada de baixo
e não pode depender de `domain/cut`. `domain/cut/curves.py` reexporta o nome,
então nenhum import existente quebra.

### 3.2 Anel com curva

`Polygon` ganha **um campo opcional**:

```python
vertices: tuple[Point2D, ...]
curves: tuple[BezierSegment, ...] = ()   # original do arquivo; () = veio reto
```

Contrato de `curves`, quando não vazio:
- descreve o MESMO anel fechado que `vertices`, na mesma ordem de percurso;
- é a fonte de verdade da forma; `vertices` é a amostragem dela;
- trecho reto do original vira `BezierSegment` com controles sobre a corda
  (a checagem `is_line()` que já existe reconhece), então uma reta permanece
  reta exata na saída.

Regra de invalidação: **qualquer operação que mexa na forma sem saber mexer na
curva deve devolver `curves=()`.** Perder a curva degrada a saída para o
comportamento de hoje; manter uma curva dessincronizada dos vértices produziria
corte errado. `_offset`, `_from_clipper` e `simplify_contour` cairão nesse caso
sem alteração de código, porque já reconstroem `Polygon` a partir de pontos.

Operações que PRESERVAM e transformam a curva:
- `Polygon.translated(dx, dy)`
- `Polygon.rotated(degrees, around)`

`scaled` também preserva (escala uniforme não deforma Bézier), mas não é usada
no caminho do Modo Corte.

Igualdade: `Polygon` é dataclass frozen, então o campo novo entra no `__eq__`.
Dois polígonos com os mesmos vértices e curvas diferentes deixam de ser iguais
— comportamento correto, e o default `()` mantém todo construtor posicional
existente (`Polygon(tuple(...))`) funcionando.

### 3.3 Orientação canônica

`group_rings` normaliza orientação por `_ccw`/`_cw`, que fazem
`tuple(reversed(polygon.vertices))`. Quando os vértices são invertidos, a lista
de curvas precisa ser invertida **e cada segmento precisa trocar de sentido**
(`p0↔p1`, `c1↔c2`). Este é o único ponto traiçoeiro da mudança e fica isolado
em `polygon_with_holes.py`.

### 3.4 Contorno de corte

`CutContour` ganha o mesmo campo opcional `curves`, com o mesmo contrato.

### 3.5 Importadores

`PdfVectorImporter` e `SvgVectorImporter` passam a montar, em paralelo ao
achatamento, a lista de `BezierSegment` do subpath (em mm, já com o transform
do arquivo aplicado — transform afim comuta com a avaliação da curva, como o
`_cubic_at` atual já assume). Retas do original entram como segmento com
controles sobre a corda. `to_ring` recebe as curvas e as devolve no `Polygon`.

O contrato de `IVectorImporter` não muda de assinatura: continua
`list[PolygonWithHoles]`, agora com curvas dentro.

### 3.6 Reconstrução da peça posicionada

`placed_cut_contours` já aplica `rotated(around=ORIGIN)` + `translated(dx, dy)`
ao `Polygon`; com 3.2 os controles viajam junto. A mudança é usar
`CutContour(poly.vertices, poly.curves)` em vez de descartar com `.vertices`.

Correção de precisão no mesmo lugar: hoje
`dx = item.position.x - bb.min_x`, onde `bb` é a bounding box do polígono
**achatado**. A curva verdadeira pode estufar para fora dele até a tolerância
do achatamento, ou seja a peça poderia ficar até 0,1 mm mais perto da vizinha
do que o encaixe calculou. Quando houver curvas, a bounding box passa a ser
calculada pelos **extremos exatos** da Bézier (raízes da derivada por eixo,
quadrática) — não por casca de controle, que seria conservadora demais em
curvatura alta.

### 3.7 Exportadores

- `write_layout_svg._path_d`: com curvas, emite `M` + um `C` por segmento + `Z`;
  segmento cujo `is_line()` é verdadeiro sai como `L` (reta exata, arquivo mais
  limpo). Sem curvas, o `M`/`L`/`Z` de hoje, sem mudança.
- `DxfExporter`: com curvas, usa as originais em vez de chamar `cubic_segments`;
  o resto do caminho (Bézier → B-spline por `bezier_to_bspline`, spline fechado
  único por contorno) permanece idêntico. Sem curvas, comportamento atual
  intacto, incluindo o refit.

O espelhamento vertical do DXF (`y' = H - y`) passa a valer também para os
pontos de controle. Espelhamento inverte orientação, o que não afeta a forma
gravada.

## 4. Fluxo de dados

```
PDF/SVG do Corel
   ├─ Bézier original (mm) ──────────────────────────┐
   └─ achatamento (flatten_curve) → vértices ─┐      │
                                              ↓      ↓
                                     Polygon(vertices, curves)
                                              ↓
                            group_rings → PolygonWithHoles
                                (inverte AMBOS junto)
                                              ↓
                                   NestingShape (carrega)
                                              ↓
                    TrueShapePacker ── usa SÓ vertices ──→ Layout
                                              ↓
                        placed_cut_contours (mesmo transform nos dois)
                                              ↓
                                   CutContour(points, curves)
                                         ↓         ↓
                                  SVG (C)     DXF (spline)
```

## 5. Tratamento de erro e degradação

Nenhum caminho novo de exceção. Toda falha em obter curva degrada para o
comportamento de hoje, nunca para corte errado:

- arquivo só com retas → `curves` vazio → polilinha, como hoje;
- path malformado (Bézier sem MOVETO anterior) → o subpath já é pulado hoje,
  segue pulado;
- peça que passou por offset/simplificação → `curves` vazio → DXF cai no refit,
  SVG cai na polilinha;
- número de segmentos incoerente com os vértices → não pode acontecer por
  construção (mesma função monta os dois), mas o exportador não depende dessa
  coerência: ele usa `curves` OU `vertices`, nunca os dois juntos.

## 6. Escopo

**Dentro** (mudanças pequenas):
`domain/geometry/bezier.py` (novo), `domain/geometry/polygon.py`,
`domain/geometry/polygon_with_holes.py`, `domain/cut/curves.py` (reexport),
`domain/model/cut_contour.py`, `infrastructure/importers/_flatten.py`,
`infrastructure/importers/pdf_vector_importer.py`,
`infrastructure/importers/svg_vector_importer.py`,
`application/use_cases/run_true_shape_nesting.py`,
`infrastructure/exporters/svg_layout_exporter.py`,
`infrastructure/exporters/dxf_exporter.py`.

**Fora, deliberadamente:**
- motor de encaixe (`domain/nesting/`) — congelado desde 22/07, e não precisa
  saber de curva;
- texto digitado (`FontToolsTextVectorizer`) — continua achatando; segue
  funcionando pelo refit;
- faca de impressão (`main_window.py` + `PdfiumVectorExtractor`) — continua
  como está; ver seção 8;
- tolerância de achatamento do import — permanece 0,1 mm.

## 7. Testes

Cada item é um teste que falha antes da mudança:

1. `Polygon.rotated`/`translated` levam os controles junto, e girar 90° quatro
   vezes devolve a curva original.
2. `group_rings` invertendo orientação inverte curvas e troca `p0↔p1`/`c1↔c2`;
   o anel resultante continua descrevendo a mesma forma.
3. `_offset`/`simplify_contour` devolvem `curves=()` (a invalidação é obrigatória,
   não acidental).
4. Importador de PDF: círculo Bézier exato entra, 4 segmentos de curva saem.
5. Importador de SVG: idem.
6. `placed_cut_contours` com giro de 90°: a bounding box exata da curva coincide
   com a posição do encaixe (regressão da correção 3.6).
7. `write_layout_svg` emite `C` na letra curva e só `L` no retângulo.
8. `DxfExporter` usa a curva original quando existe e o refit quando não existe.
9. **Regressão do caso real:** o PDF do Hospital Santa Lucia entra com 365
   curvas e sai com 365 curvas no SVG e no DXF, com contagem de nós igual à do
   original (720), não 2.089.
10. Suíte inteira nos 792 verdes (linha de base medida em 2026-08-17,
    `--ignore=tests/presentation`, que pendura como pasta).

## 8. Pendências abertas por esta especificação

- **Faceta em raio pequeno na faca de impressão.** `cubic_segments` faceta
  curvas com raio abaixo de ~1,5 mm (seção 1.3). O Modo Corte deixa de usar o
  refit, mas a faca de impressão continua usando. Correção provável: o nó só é
  canto se o giro dele se destacar dos vizinhos (num arco achatado todos os
  giros são quase iguais; num canto de verdade um giro é muito maior), mantendo
  32° como limite superior. Mexe em saída já aprovada — merece pedido próprio.
- **Contagem de nós no texto digitado.** Letras digitadas dentro do PrintNest
  continuam saindo achatadas. Só vale mexer se o cliente reclamar.

## 9. Ponto de retorno

Tag `checkpoint-antes-curvas-suaves` (`f9bc583`, aponta para `736c75c`).
Voltar: `git reset --hard checkpoint-antes-curvas-suaves`.
