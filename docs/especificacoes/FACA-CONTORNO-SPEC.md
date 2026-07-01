# Faca de Corte — Densidade, Edição Manual e Ferramenta de Contorno (estilo CorelDRAW)

> Documento de referência para uma evolução futura da geração de faca no
> PrintNest Pro. Origem: pedido do Philipe (2026-06-29) — "mudar a densidade da
> faca", "opções de aumentar/diminuir a densidade", "faca manual (o sistema gera
> e o usuário edita)", tudo inspirado no **Interactive Contour Tool** do
> CorelDRAW. Alguns arquivos hoje geram a faca errada.

---

## 1. O problema real (dor do usuário)
- **"Alguns arquivos geram a faca errada"** — a detecção do contorno (imagem/PDF
  rasterizado) às vezes sai com ruído, nós demais ou seguindo mal a arte.
- Falta **controle de densidade/detalhe** da faca (seguir a arte mais "justo" ou
  mais "solto/liso").
- Falta **edição manual** da faca (mover/arrastar os pontos gerados).

## 2. Como se encaixa no que já existe hoje
O motor de faca já tem várias peças deste quebra-cabeça:
- **`offset_contour`** (sangria) — o "offset de caminho" do Corel, só que 1 linha.
  Já é a base do item "OFFSET" da spec.
- **`smooth_contour`** (suavizar 0–5) — reduz nós/serrilhado.
- **Detecção por contorno** (imagem e PDF rasterizado) via OpenCV
  (`findContours` + simplificação) — já é o pipeline raster→vetor.
- **Faca do cliente (vetor do PDF)** — já usa o contorno vetorial pronto.
- **Sangria da faca (PDF)** já corrigida (vale nos 3 modos + fallback).

Ou seja: **não é do zero.** É expor/ampliar controles e adicionar edição.

## 3. Proposta faseada (menor risco → maior valor)

### Fase 1 — Densidade/Detalhe da faca (resolve "gera errado") ⭐ recomendado
- Um controle **"Densidade da faca"** (slider/spin) que muda a **tolerância de
  simplificação** (Douglas-Peucker / `approxPolyDP`): mais densidade = segue a
  arte mais justo (mais nós); menos = mais liso/rápido (menos nós).
- Junto com os já existentes **sensibilidade** e **suavizar**, cobre a maioria
  dos casos de "faca torta". Atualiza ao vivo (igual aos outros campos).
- **Baixo risco:** é parâmetro no pipeline atual, não muda exportação/DXF/PDF.

### Fase 2 — Cantos arredondados na faca (segurança da lâmina)
- Opção de **canto** `round | miter | bevel` no offset (a spec recomenda `round`
  como padrão para não rasgar material). Reusa/expande `offset_contour`.

### Fase 3 — Edição manual da faca (o "faca manual")
- O sistema gera a faca e o usuário **arrasta os nós** no canvas (adicionar,
  mover, remover pontos). Precisa de um editor de nós no `QGraphicsScene`
  (handles) e persistir o contorno editado por peça.
- **Maior esforço** (novo modo de edição no canvas), mas é o "Corel de verdade".

### Fase 4 — Núcleo de offset robusto (pyclipper) — opcional
- Trocar/reforçar o offset por **pyclipper (Clipper2)** para casos complexos
  (união/weld de vários objetos, ilhas/furos, sem auto-interseção). Nova
  dependência; avaliar custo/benefício e licença.

## 4. Parâmetros do Contour Tool (CorelDRAW) — mapa 1:1 (referência)
| Corel | Sistema | Uso em faca |
|---|---|---|
| Direction (outside/inside/to_center) | `direction` | outside = sangria; inside = vinco |
| Steps | `steps` | **faca = 1 linha** |
| Offset (mm) | `offset` | a sangria (já existe) |
| Corners (miter/round/bevel) | `corner_style` | **round por padrão** (lâmina) |
| Miter limit | `miter_limit` | degrada miter→bevel em ângulo agudo (pad. 2.0) |
| Presets | `preset` | ex.: `faca_adesivo_3mm`, `vinco_interno_5mm` |
| Clear/Break apart | `clear`/`break_apart` | faca vinculada → curva independente |

Ignorados na faca (só visual no Corel): cor de contorno/preenchimento,
progressão de cor, aceleração de objeto/cor.

## 5. Adaptações obrigatórias para FACA (da spec)
1. **1 linha, fechada** (steps=1; fechar paths abertos).
2. **Union/weld** de vários objetos ANTES do offset (silhueta única).
3. **Ilhas/furos** (letra "O"/"A") preservados com orientação inversa.
4. **Spot color "CutContour"**, traço hairline, sem fill (RIP reconhece p/ corte).
5. **Cantos round** por padrão.
6. **Simplificação de nós** (tolerância ~0.05 mm) = a "densidade".
7. **Bézier** opcional (corte mais fluido).
8. Distinguir **sangria de impressão** × **linha de corte**.
9. **Raster→vetor** (alpha → findContours → approxPolyDP) — já existe.

## 6. Bibliotecas (para o futuro núcleo)
- **pyclipper (Clipper2)** — offset robusto (JT_ROUND/MITER/SQUARE), padrão CNC.
- **shapely** — alternativa (`.buffer()` com join_style) e `unary_union` p/ weld.
- **OpenCV** — vetorização de raster (já usado).
- Export: **ezdxf** (DXF, já usado), spot em PDF (pikepdf/reportlab) — futuro.

## 7. Casos de erro a validar
- Offset interno maior que a menor dimensão → erro amigável.
- Auto-interseção pós-offset → limpeza booleana (Clipper) ou aviso.
- Pontas afiadas (miter agudo) → miter_limit degrada p/ bevel.
- Path aberto no output → bloquear export, forçar fechamento.
- Nós em excesso → aplicar simplificação (densidade).

---

**Recomendação:** começar pela **Fase 1 (Densidade/Detalhe)** — é o que resolve
o "gera errado" com menor risco, sem tocar em exportação/DXF/PDF. Depois cantos
`round`, e por fim o editor manual de nós.
