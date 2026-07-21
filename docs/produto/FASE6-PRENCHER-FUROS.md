# Fase 6 — Preencher furos (peça dentro de peça / "Allow inside")

Documento de manutenção: o que foi construído, **por que** cada decisão foi
tomada, o que foi **medido** e onde estão as armadilhas. Escrito para quem for
tentar melhorar isso depois (inclusive eu mesmo, daqui a seis meses).

Data: 21/07/2026. Branch: `v1.3-redesign`.

---

## 1. O que a fase faz

Peça pequena passa a ocupar o **furo** de uma peça já posicionada — o miolo do
"O", o vão do "8". É o "Allow inside" que o eCut e afins oferecem.

Liga/desliga pelo checkbox **"Preencher furos (peça dentro de peça)"** no
diálogo do Modo Corte, que vira `TrueShapePacker(inside_check=...)`.

---

## 2. Como funciona o motor

### 2.1 `_ifp_hole(hole, piece)` — o coração

É o **espelho do NFP**. Onde o NFP responde "onde B *não* pode ficar perto de
A", o IFP de furo responde "onde B pode ficar *inteiramente dentro* de A".

Somar a borda do furo com `-peça` (Minkowski) varre uma **faixa**. Fora da
faixa a peça escapa do furo; o **anel interno** dela é exatamente
`{t : peça + t ⊆ furo}`. Devolve **todos** os anéis internos, porque furo
côncavo (o vão de um "C") parte a erosão em pedaços desconexos.

Duas defesas, na mesma linha do que `_nfp` já fazia:

- **Filtros baratos antes do Minkowski**: bbox da peça tem que caber no bbox do
  furo, e a área também. São condições *necessárias* para a contenção, então
  não descartam encaixe real — e num lote de letras cortam a esmagadora maioria
  dos pares sem tocar no clipper.
- **Confirmação por contenção real** (`_contains`) de cada anel candidato: o
  Clipper soma pela borda e pode devolver anel que é artefato.

### 2.2 Gap dos dois lados

A peça hospedada infla `gap/2` **e** o furo encolhe `gap/2` (`_shrunk`). Sem os
dois lados o laser funde a peça interna na parede do furo.

`_shrunk` existe separado de `_offset` porque com solução vazia (furo menor que
o dobro da folga) o `max()` do `_offset` estouraria — aqui o certo é devolver
`None` e o furo deixar de valer como vão.

### 2.3 Região válida

```
(IFP da chapa − NFPs de todas as postas)
  ∪  para cada furo de cada posta:
     (IFP do furo − NFPs das outras postas, EXCETO o próprio hospedeiro)
```

**O hospedeiro fica fora da subtração de propósito.** O NFP dele é calculado
sobre o contorno *externo* (o motor de nesting nunca conheceu furo), então
subtraí-lo apagaria justamente o vão que se quer usar. Quem garante que a peça
não vaza para a parede é a contenção do próprio IFP do furo, e o oráculo
confere no fim com os furos descontados.

Isso faz o aninhamento recursivo cair de graça: peça dentro de peça dentro de
peça funciona sem código extra.

### 2.4 Oráculo com furos

`_overlaps` ganhou `holes_a`/`holes_b`. Sem isso ele acusaria sobreposição da
peça hospedada com um miolo que na verdade é vazio. Fatorado em
`_material_paths` (contorno inflado − furos encolhidos) + `_overlaps_paths`.

Ganho de desempenho junto: o material de cada peça é montado **uma vez por
rotação** e só transladado por candidato. Antes cada candidato refazia dois
offsets de clipper por peça já posta.

### 2.5 Os furos NÃO são simplificados

`_prepared` simplifica o contorno (`approximation`) mas passa os furos
intactos. A simplificação tolera até 10% de variação de área, e um furo
simplificado **para fora** faria a peça hospedada encostar na parede real.
Custa NFP/IFP mais lento; é o preço de não arriscar o corte.

---

## 3. A decisão mais importante: quem escolhe encher o furo

**Há duas regras de desempate possíveis no bottom-left, e nenhuma ganha
sempre.** Isto foi medido, não deduzido:

| regra | letras mistas (chapa 400) | anéis + quadrados (chapa 420) |
|---|---|---|
| `(y, x)` puro — furo disputa igual | 49,54% | ganha em chapa apertada |
| furo **antes** de chapa livre | **46,10%** | ganha em chapa folgada |

Preferir o furo na marra tira as peças pequenas da frente do bottom-left e as
peças grandes se entrelaçam **pior**. Por isso a regra virou um **bit do
cromossomo** (`prefer_holes`), ao lado de ordem e rotações — quem decide é a
**busca**, não uma regra fixa.

Com o bit no gene o lote misto voltou de 46,10% para 49,33% (nível de ruído
contra os 49,54% da linha de base) e o ganho dos anéis se manteve.

### O que o elitismo garante — e o que NÃO garante

As sementes **sem** preferência são avaliadas primeiro, então o resultado nunca
fica pior que o chute bottom-left de sempre. **Não** garante empatar com a caixa
desligada em qualquer lote: a população muda 2 dos 16 indivíduos, o passeio
aleatório muda junto, e sobra ~0,4% de diferença para os dois lados.

Não escreva "ligar nunca perde" na documentação. Não é verdade.

### Determinismo preservado

Com `inside_check` desligado o bit fica preso em `False` e **nenhum sorteio do
`rng` é consumido** — os sorteios novos ficam no fim de `_mutated` e do
crossover, atrás de um `if inside_check`. Por isso o motor da Fase 2 continua
bit a bit idêntico e a suíte antiga passou sem edição.

---

## 4. A armadilha que quase passou: o fitness estava errado

**Sintoma:** no teste do Philipe (1 anel 200mm com furo 140 + 16 quadrados de
40mm, chapa 420) a caixa **ligada** deu resultado **pior**:

| | chapa usada | aproveitamento |
|---|---|---|
| ligada | 252 mm | 43% |
| desligada | 210 mm | 52% |

Os 9 quadrados entravam no vão, mas os 7 restantes eram empurrados para uma
linha nova em cima do anel — 42 mm a mais de material.

**Causa — e não é da Fase 6.** O GA minimizava **área do bounding box**:

```
ligada:    bbox 292 × 242 = 70664 mm²   ← o GA prefere esta
desligada: bbox 368 × 200 = 73600 mm²
```

O GA estava certo pelo critério dele. O critério é que estava errado: **em
bobina/chapa aberta a largura é fixa**, o que gasta material é só o
**comprimento**. Minimizar área premia deixar o layout estreito, o que não vale
nada — e foi exatamente o que a Fase 6 explorou.

**Correção — e a armadilha DENTRO da correção.** A primeira tentativa foi
fitness = só o comprimento. Quebrou `test_ga_rotacao_melhora_o_encaixe`, e o
teste estava certo: dois "L" entrelaçados e dois lado a lado ocupam o **mesmo
comprimento**, então o custo virava um **platô** e o GA perdia o incentivo de
entrelaçar — que é justamente o que faz caber mais peça por linha e, aí sim,
encurtar a chapa.

Fitness final é **lexicográfico**:

```
custo = (comprimento ocupado × largura da chapa,   ← o que gasta material
         área do bounding box)                     ← desempate: compacidade
```

Isso exigiu trocar o custo escalar por tupla em `evaluate`, `best`, `consider`
e `pick` (o `_PIOR = (inf, inf)` existe por causa disso).

Depois: a caixa ligada dá 210 mm (empata com desligada) e ainda coloca 6 peças
no vão de graça. Benchmarks de anéis (75,28%) e das 44 letras (518,7 mm)
ficaram **idênticos** — a mudança não mexeu nas linhas de base.

> **Lição para a próxima fase:** antes de acreditar num ganho de nesting,
> confira se a métrica que o GA minimiza é a mesma que custa material ao
> cliente. Bounding box e comprimento de bobina não são a mesma coisa.

---

## 5. Ordem de corte no DXF

**Regra: de dentro para fora.** Peça hospedada → furos → contorno externo.

Se a máquina fecha o contorno externo primeiro, a peça se solta da chapa e o
que faltava cortar sai desalinhado.

Duas correções, e a segunda **não** era da Fase 6:

1. Peça hospedada antes do contorno que a envolve.
2. **Os furos da própria peça antes do contorno externo dela** — isso estava
   errado desde sempre e afeta *todo* trabalho com furo, não só os da Fase 6.

A profundidade é medida **geometricamente na exportação** (`_cut_order`), não
carregada no `Layout`: `PlacedItem` não sabe (nem precisa saber) quem hospedou
quem, e assim a regra vale para aninhamento de qualquer profundidade.

**Cuidado ao mexer:** a reordenação vive em `_layout_contours`, **não** em
`placed_cut_contours`. O preview, o `export_svg` e o `_sheet_stats` dependem de
`placed_cut_contours(...)[0]` ser o contorno *externo*.

---

## 6. Quando esta fase NÃO dá ganho (e é o esperado)

- **Lote de letras todas do mesmo tamanho**: ganho **zero**, por construção.
  Nenhuma letra cabe na contraforma de outra. Não é bug.
- **Chapa folgada**: com `(y, x)` puro sempre sobra chapa livre com `y` menor
  que o miolo, então o vão não é escolhido. O bit `prefer_holes` existe
  justamente para o GA poder testar o contrário quando compensa.
- O ganho pede **peça pequena junto de peça com vão largo**.

Custo: ~1,7× por geração em lote com furos. Em trabalho grande, subir o "Tempo
de otimização" para 30–60s.

---

## 7. Onde está cada coisa

| arquivo | o que tem |
|---|---|
| `app/domain/nesting/true_shape.py` | `_ifp_hole`, `_shrunk`, `_contains`, `_material_paths`, `_overlaps_paths`, `_rotated_parts`, `_subtract`, bit `prefer_holes` no GA |
| `app/application/use_cases/run_true_shape_nesting.py` | `_cut_order`, `_hosts` — ordem de corte |
| `app/presentation/cut_mode_dialog.py` | checkbox `_inside` |
| `tests/domain/nesting/test_true_shape.py` | IFP contra bruteforce, entrada no furo, gap, determinismo |
| `tests/application/test_run_true_shape_nesting.py` | ordem no DXF |
| `corel/GUIA-CLIENTE.md` | texto do cliente |

### O teste que mais importa

`test_ifp_hole_concorda_com_bruteforce` exige **zero falso positivo** — falso
positivo é peça colidindo com a parede do furo, ou seja, peça perdida na
máquina. Cobertura incompleta só custa densidade, por isso ela é exigida em
≥95% e não em 100%. **Não afrouxe o zero.**

---

## 8. Ideias para quem for melhorar

1. **Fitness por chapa cheia** — hoje o custo é o comprimento do bloco. Para
   `pack_sheets` (folha de altura fixa) o objetivo real é outro: caber o máximo
   por folha. Vale separar as duas funções de custo.
2. **`prefer_holes` por peça**, não global — hoje o bit vale para a passada
   inteira. Um bit por peça daria busca mais fina (e cromossomo maior).
3. **Container irregular** (`Use_Last_As_Container` do eCut): `_ifp_rect` só
   sabe chapa retangular. `_ifp_hole` já é o motor genérico que falta — dá para
   reaproveitar passando o contorno do container como "furo".
4. **Ordem de corte por caminho**, não só por aninhamento: hoje a ordem dentro
   de cada nível é a do layout. Ordenar por proximidade encurtaria o percurso
   da máquina.
5. **Custo do IFP**: o `ifp_cache` é por `(hospedeiro, rot, furo, peça, rot)`.
   Em lote com muitas rotações isso explode. Um filtro por "maior furo do lote"
   antes de tudo cortaria mais cedo.

---

## 9. Referência

eCut serve **só como benchmark de resultado**, nunca como fonte de código. As
técnicas usadas aqui são públicas (NFP/IFP por Minkowski, bottom-left-fill,
algoritmo genético — SVGnest e a literatura de nesting irregular).
