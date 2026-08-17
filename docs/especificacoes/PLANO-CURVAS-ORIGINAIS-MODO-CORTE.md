# Curvas originais no Modo Corte — plano de implementação

> **Para executores agênticos:** SUB-SKILL OBRIGATÓRIA: use
> superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans para implementar tarefa por tarefa. Os passos
> usam caixas (`- [ ]`) para acompanhamento.

**Goal:** As Béziers originais do arquivo do CorelDRAW atravessam o Modo Corte
intactas e são gravadas no SVG e no DXF, em vez de serem achatadas em retas.

**Architecture:** O polígono achatado continua sendo a única coisa que o motor
de encaixe vê; a Bézier original viaja ao lado dele, num campo opcional de
`Polygon` e `CutContour`, e só é lida pelos exportadores. Rotação e translação
não deformam Bézier, então o mesmo transform do encaixe aplicado aos pontos de
controle devolve a letra idêntica à do Corel, na posição do arranjo.

**Tech Stack:** Python 3.10, dataclasses frozen com slots, pypdfium2 (PDF),
svgelements (SVG), ezdxf (DXF), pytest.

**Spec:** [docs/especificacoes/CURVAS-ORIGINAIS-MODO-CORTE.md](CURVAS-ORIGINAIS-MODO-CORTE.md)

## Global Constraints

- Python do projeto: `.venv/Scripts/python.exe` (não o `python` do PATH, que
  não tem pytest).
- Rodar a suíte SEMPRE com `--ignore=tests/presentation` — essa pasta pendura
  quando executada como pasta. Linha de base a bater: **792 testes, 0 falhas,
  0 erros, 5 pulados**.
- A suíte não imprime resumo no stdout deste ambiente. Para ler a contagem use
  `--junit-xml=<arquivo>` e leia os atributos do XML.
- **Não tocar em `app/domain/nesting/`.** O motor de encaixe está congelado
  desde 22/07; ele lê `.vertices` e deve continuar cego às curvas.
- **Não tocar em `app/presentation/main_window.py`,
  `app/infrastructure/importers/pdfium_vector_extractor.py` nem
  `app/infrastructure/text/fonttools_text_vectorizer.py`.** Faca de impressão e
  texto digitado ficam como estão.
- Unidade de todas as coordenadas: milímetros, origem topo-esquerda, Y crescendo
  para baixo.
- Regra de invalidação, válida em todas as tarefas: qualquer operação que mexa
  na forma sem saber mexer na curva devolve `curves=()`. Perder a curva degrada
  para o comportamento de hoje; uma curva dessincronizada dos vértices produz
  corte errado.
- Comentários e docstrings em português, sem acento em identificadores, no estilo
  do restante do repositório (explicar o *porquê*, não o *o quê*).
- Mensagens de commit no estilo do repositório: `feat:` / `fix:` em minúsculas,
  descrição curta em português.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `app/domain/geometry/bezier.py` (novo) | O tipo `BezierSegment` e as operações puras sobre ele: inverter sentido, transladar, girar, caixa envolvente exata. Fica em `geometry` porque é a camada de baixo — `domain/cut` pode depender dela, nunca o contrário. |
| `app/domain/cut/curves.py` (modificar) | Reexporta `BezierSegment` do novo lar para não quebrar os imports existentes. O refit (`cubic_segments`) continua igual, servindo a faca de impressão. |
| `app/domain/geometry/polygon.py` (modificar) | `Polygon` ganha o campo opcional `curves` e leva os controles junto em `translated`/`rotated`/`scaled`. |
| `app/domain/geometry/polygon_with_holes.py` (modificar) | `_ccw`/`_cw` invertem a lista de curvas junto com os vértices. |
| `app/domain/model/cut_contour.py` (modificar) | `CutContour` ganha o mesmo campo opcional. |
| `app/infrastructure/importers/_flatten.py` (modificar) | `to_ring` aceita as curvas do subpath e as devolve dentro do `Polygon`. |
| `app/infrastructure/importers/pdf_vector_importer.py` (modificar) | Monta a lista de `BezierSegment` em paralelo ao achatamento. |
| `app/infrastructure/importers/svg_vector_importer.py` (modificar) | Idem, para os segmentos do svgelements. |
| `app/application/use_cases/run_true_shape_nesting.py` (modificar) | Transporta as curvas para o `CutContour` e passa a posicionar pela caixa envolvente exata da curva. |
| `app/infrastructure/exporters/svg_layout_exporter.py` (modificar) | Emite `C` quando há curva, `L` quando o trecho é reto. |
| `app/infrastructure/exporters/dxf_exporter.py` (modificar) | Usa a curva original quando existe; cai no refit quando não existe. |

---

### Task 1: O tipo `BezierSegment` em `domain/geometry`

**Files:**
- Create: `app/domain/geometry/bezier.py`
- Modify: `app/domain/geometry/__init__.py`
- Modify: `app/domain/cut/curves.py:31-43` (trocar a definição por reexport)
- Test: `tests/domain/geometry/test_bezier.py`

**Interfaces:**
- Consumes: `app.domain.geometry.point.Point2D`,
  `app.domain.geometry.bounding_box.BoundingBox`
- Produces:
  - `BezierSegment(p0: Point2D, c1: Point2D, c2: Point2D, p1: Point2D)`
  - `BezierSegment.is_line(tol: float = 1e-6) -> bool`
  - `BezierSegment.reversed() -> BezierSegment`
  - `BezierSegment.translated(dx: float, dy: float) -> BezierSegment`
  - `BezierSegment.rotated(degrees: float, around: Point2D | None = None) -> BezierSegment`
  - `BezierSegment.scaled(factor: float, around: Point2D | None = None) -> BezierSegment`
  - `BezierSegment.point_at(t: float) -> Point2D`
  - `bezier_bounds(segments: Sequence[BezierSegment]) -> BoundingBox`
  - `line_segment(a: Point2D, b: Point2D) -> BezierSegment`

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/domain/geometry/test_bezier.py`:

```python
import math

import pytest

from app.domain.geometry import Point2D
from app.domain.geometry.bezier import (
    BezierSegment,
    bezier_bounds,
    line_segment,
)


def _quarter_circle(r: float = 10.0) -> BezierSegment:
    """Arco de 90 graus de (r, 0) a (0, r), a aproximacao classica de Bezier."""
    k = 4.0 / 3.0 * (math.sqrt(2.0) - 1.0) * r
    return BezierSegment(
        Point2D(r, 0.0), Point2D(r, k), Point2D(k, r), Point2D(0.0, r)
    )


def test_line_segment_tem_controles_sobre_a_corda():
    seg = line_segment(Point2D(0.0, 0.0), Point2D(9.0, 0.0))
    assert seg.is_line()


def test_arco_nao_e_reta():
    assert not _quarter_circle().is_line()


def test_reversed_troca_extremos_e_controles():
    seg = _quarter_circle()
    rev = seg.reversed()
    assert rev.p0 == seg.p1
    assert rev.c1 == seg.c2
    assert rev.c2 == seg.c1
    assert rev.p1 == seg.p0


def test_reversed_percorre_a_mesma_curva_ao_contrario():
    seg = _quarter_circle()
    rev = seg.reversed()
    for k in range(11):
        t = k / 10
        a = seg.point_at(t)
        b = rev.point_at(1.0 - t)
        assert a.x == pytest.approx(b.x, abs=1e-12)
        assert a.y == pytest.approx(b.y, abs=1e-12)


def test_translated_desloca_os_quatro_pontos():
    seg = _quarter_circle().translated(3.0, -2.0)
    base = _quarter_circle()
    assert seg.p0.x == pytest.approx(base.p0.x + 3.0)
    assert seg.c1.y == pytest.approx(base.c1.y - 2.0)
    assert seg.c2.x == pytest.approx(base.c2.x + 3.0)
    assert seg.p1.y == pytest.approx(base.p1.y - 2.0)


def test_rotated_360_em_quatro_giros_volta_ao_original():
    seg = _quarter_circle()
    girado = seg
    for _ in range(4):
        girado = girado.rotated(90.0, around=Point2D(0.0, 0.0))
    for a, b in zip(
        (girado.p0, girado.c1, girado.c2, girado.p1),
        (seg.p0, seg.c1, seg.c2, seg.p1),
        strict=True,
    ):
        assert a.x == pytest.approx(b.x, abs=1e-9)
        assert a.y == pytest.approx(b.y, abs=1e-9)


def test_bezier_bounds_e_exata_nao_a_casca_de_controle():
    """O arco de 90 graus de raio 10 vai de (10,0) a (0,10) e NAO passa por
    (10,10) — a casca de controle daria o canto errado; os extremos exatos dao
    a caixa justa do arco."""
    box = bezier_bounds([_quarter_circle(10.0)])
    assert box.min_x == pytest.approx(0.0, abs=1e-9)
    assert box.min_y == pytest.approx(0.0, abs=1e-9)
    assert box.max_x == pytest.approx(10.0, abs=1e-9)
    assert box.max_y == pytest.approx(10.0, abs=1e-9)


def test_bezier_bounds_de_arco_que_estufa_alem_dos_extremos():
    """Meia-volta: de (10,0) a (-10,0) passando por cima. O topo real fica em
    0.75 da altura dos controles, entao a caixa NAO e a dos extremos."""
    seg = BezierSegment(
        Point2D(10.0, 0.0), Point2D(10.0, 8.0), Point2D(-10.0, 8.0), Point2D(-10.0, 0.0)
    )
    box = bezier_bounds([seg])
    assert box.max_y == pytest.approx(6.0, abs=1e-9)  # 0.75 * 8
    assert box.min_y == pytest.approx(0.0, abs=1e-9)


def test_bezier_bounds_vazio_recusa():
    from app.shared.errors import ValidationError

    with pytest.raises(ValidationError):
        bezier_bounds([])
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
.venv/Scripts/python.exe -m pytest tests/domain/geometry/test_bezier.py -v
```

Esperado: FALHA no import — `No module named 'app.domain.geometry.bezier'`.

- [ ] **Step 3: Criar `app/domain/geometry/bezier.py`**

```python
"""Bezier cubica como dado de primeira classe da geometria.

Mora em 'geometry' (a camada de baixo) porque 'Polygon' precisa carregar a
curva ORIGINAL do arquivo importado ao lado dos vertices achatados: o encaixe
usa os vertices, a exportacao usa a curva. Se este tipo ficasse em
'domain/cut', a camada de baixo dependeria da de cima.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.geometry.bounding_box import BoundingBox
from app.domain.geometry.point import Point2D
from app.shared.errors import ValidationError

_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class BezierSegment:
    """Trecho de Bezier cubica: dois extremos (p0, p1) e dois controles."""

    p0: Point2D
    c1: Point2D
    c2: Point2D
    p1: Point2D

    def is_line(self, tol: float = 1e-6) -> bool:
        """True se os controles estao sobre a corda (trecho reto exato).

        Serve para o exportador escrever LINHA em vez de curva: reta gravada
        como reta deixa o arquivo limpo e o corte previsivel.
        """
        return (
            _dist_point_line(self.c1, self.p0, self.p1) <= tol
            and _dist_point_line(self.c2, self.p0, self.p1) <= tol
        )

    def reversed(self) -> BezierSegment:
        """Mesmo trecho percorrido ao contrario.

        Inverter um anel exige inverter cada trecho TAMBEM por dentro: so
        virar a lista deixaria cada curva apontando para o lado errado.
        """
        return BezierSegment(self.p1, self.c2, self.c1, self.p0)

    def translated(self, dx: float, dy: float) -> BezierSegment:
        return BezierSegment(
            self.p0.translated(dx, dy),
            self.c1.translated(dx, dy),
            self.c2.translated(dx, dy),
            self.p1.translated(dx, dy),
        )

    def rotated(self, degrees: float, around: Point2D | None = None) -> BezierSegment:
        """Gira os quatro pontos. Giro e translacao NAO deformam Bezier — e por
        isso que a curva original sobrevive ao encaixe sem perder nada."""
        return BezierSegment(
            self.p0.rotated(degrees, around),
            self.c1.rotated(degrees, around),
            self.c2.rotated(degrees, around),
            self.p1.rotated(degrees, around),
        )

    def scaled(self, factor: float, around: Point2D | None = None) -> BezierSegment:
        """Escala uniforme tambem preserva a forma da curva."""
        return BezierSegment(
            self.p0.scaled(factor, around),
            self.c1.scaled(factor, around),
            self.c2.scaled(factor, around),
            self.p1.scaled(factor, around),
        )

    def point_at(self, t: float) -> Point2D:
        u = 1.0 - t
        x = (
            u * u * u * self.p0.x + 3 * u * u * t * self.c1.x
            + 3 * u * t * t * self.c2.x + t * t * t * self.p1.x
        )
        y = (
            u * u * u * self.p0.y + 3 * u * u * t * self.c1.y
            + 3 * u * t * t * self.c2.y + t * t * t * self.p1.y
        )
        return Point2D(x, y)

    def extrema_x(self) -> list[float]:
        """Valores de x nos extremos EXATOS do trecho (pontas + raizes de dx/dt)."""
        return self._extrema(self.p0.x, self.c1.x, self.c2.x, self.p1.x, axis_x=True)

    def extrema_y(self) -> list[float]:
        return self._extrema(self.p0.y, self.c1.y, self.c2.y, self.p1.y, axis_x=False)

    def _extrema(
        self, a0: float, a1: float, a2: float, a3: float, *, axis_x: bool
    ) -> list[float]:
        """Pontas mais as raizes de a*t^2 + b*t + c = 0 dentro de (0, 1).

        A derivada de uma cubica e uma quadratica; resolver exato evita a casca
        de controle, que em curvatura alta superestima muito a caixa e faria a
        peca reservar espaco que ela nao ocupa.
        """
        values = [a0, a3]
        a = -a0 + 3 * a1 - 3 * a2 + a3
        b = 2 * (a0 - 2 * a1 + a2)
        c = a1 - a0
        for t in _quadratic_roots(a, b, c):
            if 0.0 < t < 1.0:
                p = self.point_at(t)
                values.append(p.x if axis_x else p.y)
        return values


def line_segment(a: Point2D, b: Point2D) -> BezierSegment:
    """Reta como Bezier: controles em 1/3 e 2/3 da corda.

    Assim um contorno com trechos retos e curvos vira UMA lista homogenea, e
    is_line() reconhece de volta quem era reto na hora de gravar.
    """
    return BezierSegment(
        a,
        Point2D(a.x + (b.x - a.x) / 3.0, a.y + (b.y - a.y) / 3.0),
        Point2D(b.x - (b.x - a.x) / 3.0, b.y - (b.y - a.y) / 3.0),
        b,
    )


def bezier_bounds(segments: Sequence[BezierSegment]) -> BoundingBox:
    """Caixa envolvente EXATA da curva (nao da casca de controle)."""
    xs: list[float] = []
    ys: list[float] = []
    for s in segments:
        xs.extend(s.extrema_x())
        ys.extend(s.extrema_y())
    if not xs:
        raise ValidationError("bezier_bounds requer ao menos um segmento.")
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))


def _quadratic_roots(a: float, b: float, c: float) -> list[float]:
    if abs(a) < _EPS:  # degenera em linear
        return [] if abs(b) < _EPS else [-c / b]
    disc = b * b - 4 * a * c
    if disc < 0:
        return []
    root = math.sqrt(disc)
    return [(-b + root) / (2 * a), (-b - root) / (2 * a)]


def _dist_point_line(p: Point2D, a: Point2D, b: Point2D) -> float:
    vx, vy = b.x - a.x, b.y - a.y
    n = math.hypot(vx, vy)
    if n < _EPS:
        return math.hypot(p.x - a.x, p.y - a.y)
    return abs((p.x - a.x) * vy - (p.y - a.y) * vx) / n
```

- [ ] **Step 4: Rodar e confirmar que passa**

```
.venv/Scripts/python.exe -m pytest tests/domain/geometry/test_bezier.py -v
```

Esperado: 9 PASSED.

- [ ] **Step 5: Reexportar em `domain/geometry/__init__.py`**

Adicionar o import (mantendo a ordem alfabética dos imports existentes — antes
da linha de `bounding_box`):

```python
from app.domain.geometry.bezier import BezierSegment, bezier_bounds, line_segment
```

E acrescentar ao `__all__`, em ordem alfabética: `"BezierSegment"`,
`"bezier_bounds"`, `"line_segment"`.

- [ ] **Step 6: Trocar a definição em `domain/cut/curves.py` por reexport**

Remover as linhas 31-43 (o `@dataclass` `BezierSegment` com o método
`is_line`). **Manter** `_dist_point_line` — ele continua sendo usado por
`cubic_segments` e `flatten` no mesmo arquivo.

No lugar da classe, colocar o import junto aos outros do topo:

```python
from app.domain.geometry.bezier import BezierSegment
```

E declarar o reexport explícito (o `DxfExporter` faz
`from app.domain.cut.curves import cubic_segments, has_curves`; outros módulos
podem importar `BezierSegment` daqui):

```python
__all__ = ["BezierSegment", "CORNER_DEG", "cubic_segments", "flatten", "has_curves"]
```

Acrescentar ao fim da docstring do módulo:

```
O tipo BezierSegment mora em app.domain.geometry.bezier (a camada de baixo,
porque Polygon carrega curva) e e reexportado aqui por compatibilidade.
```

- [ ] **Step 7: Rodar os testes que dependem de `curves.py`**

```
.venv/Scripts/python.exe -m pytest tests/domain/cut tests/infrastructure/test_dxf_exporter.py tests/qa/test_qa_f3_dxf_contorno_unico.py -v
```

Esperado: todos PASSED — o reexport não muda comportamento nenhum.

- [ ] **Step 8: Commit**

```bash
git add app/domain/geometry/bezier.py app/domain/geometry/__init__.py app/domain/cut/curves.py tests/domain/geometry/test_bezier.py
git commit -m "refactor: BezierSegment desce para domain/geometry com caixa exata"
```

---

### Task 2: `Polygon` carrega a curva original

**Files:**
- Modify: `app/domain/geometry/polygon.py`
- Test: `tests/domain/geometry/test_polygon.py`

**Interfaces:**
- Consumes: `BezierSegment` (Task 1)
- Produces:
  - `Polygon(vertices: tuple[Point2D, ...], curves: tuple[BezierSegment, ...] = ())`
  - `Polygon.translated`/`rotated`/`scaled` preservam e transformam `curves`
  - `Polygon.from_points` continua devolvendo `curves=()`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/domain/geometry/test_polygon.py`:

```python
def test_polygon_sem_curvas_por_padrao():
    from app.domain.geometry import Point2D, Polygon

    poly = Polygon((Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)))
    assert poly.curves == ()


def test_translated_leva_os_controles_junto():
    import pytest

    from app.domain.geometry import Point2D, Polygon
    from app.domain.geometry.bezier import BezierSegment

    seg = BezierSegment(Point2D(0, 0), Point2D(3, 1), Point2D(7, 1), Point2D(10, 0))
    poly = Polygon((Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)), curves=(seg,))
    movido = poly.translated(5.0, -1.0)
    assert movido.curves[0].c1.x == pytest.approx(8.0)
    assert movido.curves[0].c1.y == pytest.approx(0.0)


def test_rotated_leva_os_controles_junto():
    import pytest

    from app.domain.geometry import Point2D, Polygon
    from app.domain.geometry.bezier import BezierSegment

    seg = BezierSegment(Point2D(1, 0), Point2D(2, 0), Point2D(3, 0), Point2D(4, 0))
    poly = Polygon((Point2D(1, 0), Point2D(4, 0), Point2D(4, 4)), curves=(seg,))
    girado = poly.rotated(90.0, around=Point2D(0, 0))
    assert girado.curves[0].p0.x == pytest.approx(0.0, abs=1e-9)
    assert girado.curves[0].p0.y == pytest.approx(1.0, abs=1e-9)


def test_from_points_nao_inventa_curva():
    from app.domain.geometry import Point2D, Polygon

    poly = Polygon.from_points([Point2D(0, 0), Point2D(1, 0), Point2D(1, 1)])
    assert poly.curves == ()
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
.venv/Scripts/python.exe -m pytest tests/domain/geometry/test_polygon.py -v
```

Esperado: os 4 novos FALHAM — `Polygon.__init__() got an unexpected keyword
argument 'curves'`, e `AttributeError: 'Polygon' object has no attribute
'curves'` no primeiro e no último.

- [ ] **Step 3: Adicionar o campo e propagar nos transforms**

Em `app/domain/geometry/polygon.py`, import novo junto aos outros:

```python
from app.domain.geometry.bezier import BezierSegment
```

Trocar a declaração da classe:

```python
@dataclass(frozen=True, slots=True)
class Polygon:
    """Poligono fechado (anel de vertices em mm). Fechamento implicito.

    'curves' guarda a Bezier ORIGINAL do arquivo importado, quando existe: os
    vertices sao a amostragem dela e servem ao encaixe (contencao, area, bbox),
    a curva serve a exportacao. Descrevem o MESMO anel, na mesma ordem de
    percurso.

    REGRA DE INVALIDACAO: operacao que mexe na forma sem saber mexer na curva
    devolve curves=(). Perder a curva so degrada a saida para polilinha (o
    comportamento antigo); uma curva dessincronizada dos vertices cortaria
    errado. Por isso todo caminho que reconstroi Polygon a partir de
    coordenadas (offset do pyclipper, simplificacao do shapely) zera o campo
    sozinho, sem precisar de codigo.
    """

    vertices: tuple[Point2D, ...]
    curves: tuple[BezierSegment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertices", tuple(self.vertices))
        object.__setattr__(self, "curves", tuple(self.curves))
        if len(self.vertices) < 3:
            raise ValidationError("Polygon requer ao menos 3 vertices.")
```

Trocar os três transforms:

```python
    def translated(self, dx: float, dy: float) -> Polygon:
        return Polygon(
            tuple(p.translated(dx, dy) for p in self.vertices),
            tuple(s.translated(dx, dy) for s in self.curves),
        )

    def rotated(self, degrees: float, around: Point2D | None = None) -> Polygon:
        center = around if around is not None else self.centroid
        return Polygon(
            tuple(p.rotated(degrees, center) for p in self.vertices),
            tuple(s.rotated(degrees, center) for s in self.curves),
        )

    def scaled(self, factor: float, around: Point2D | None = None) -> Polygon:
        center = around if around is not None else self.centroid
        return Polygon(
            tuple(p.scaled(factor, center) for p in self.vertices),
            tuple(s.scaled(factor, center) for s in self.curves),
        )
```

`signed_area`, `area`, `is_clockwise`, `perimeter`, `centroid`,
`bounding_box`, `contains` e `from_points` **não mudam** — todos continuam
olhando só para `vertices`, que é o que o encaixe precisa.

- [ ] **Step 4: Rodar e confirmar que passa**

```
.venv/Scripts/python.exe -m pytest tests/domain/geometry -v
```

Esperado: todos PASSED.

- [ ] **Step 5: Confirmar que o nesting continua cego às curvas**

```
.venv/Scripts/python.exe -m pytest tests/domain/nesting tests/application -q -p no:cacheprovider
```

Esperado: nenhuma falha. Se algum teste comparava `Polygon` por igualdade e
quebrou, é sinal de que aquele caminho estava carregando curva onde não devia —
investigar em vez de ajustar o teste.

- [ ] **Step 6: Commit**

```bash
git add app/domain/geometry/polygon.py tests/domain/geometry/test_polygon.py
git commit -m "feat: Polygon carrega a Bezier original ao lado dos vertices"
```

---

### Task 3: `group_rings` inverte a curva junto com os vértices

**Files:**
- Modify: `app/domain/geometry/polygon_with_holes.py:25-32` (`_ccw` e `_cw`)
- Test: `tests/domain/geometry/test_polygon_with_holes.py`

**Interfaces:**
- Consumes: `Polygon.curves` (Task 2), `BezierSegment.reversed()` (Task 1)
- Produces: `PolygonWithHoles` cujos `outer.curves` e `holes[i].curves`
  descrevem o anel na MESMA ordem de percurso dos vértices normalizados.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/domain/geometry/test_polygon_with_holes.py`:

```python
def test_normalizacao_de_orientacao_inverte_as_curvas_junto():
    """Se o anel entra no sentido errado, os vertices sao invertidos. As curvas
    precisam ser invertidas TAMBEM por dentro (p0<->p1, c1<->c2), senao a
    exportacao percorreria a curva ao contrario dos vertices."""
    import pytest

    from app.domain.geometry import Point2D, Polygon, PolygonWithHoles
    from app.domain.geometry.bezier import BezierSegment, line_segment

    # triangulo no sentido horario (signed_area negativa): sera invertido
    a, b, c = Point2D(0, 0), Point2D(0, 10), Point2D(10, 0)
    curvo = BezierSegment(a, Point2D(0, 3), Point2D(0, 7), b)
    poly = Polygon((a, b, c), curves=(curvo, line_segment(b, c), line_segment(c, a)))
    assert poly.is_clockwise  # precondicao do teste

    forma = PolygonWithHoles(poly)

    assert forma.outer.vertices[0] == c  # confirmou a inversao dos vertices
    # o trecho curvo agora e o ULTIMO e aponta de b para a
    ultimo = forma.outer.curves[-1]
    assert ultimo.p0 == b
    assert ultimo.p1 == a
    assert ultimo.c1.y == pytest.approx(7.0)
    assert ultimo.c2.y == pytest.approx(3.0)


def test_curva_e_vertices_ficam_na_mesma_ordem_de_percurso():
    """Invariante geral: o primeiro vertice e o inicio do primeiro trecho, e o
    fim de cada trecho e o inicio do proximo."""
    from app.domain.geometry import Point2D, Polygon, PolygonWithHoles
    from app.domain.geometry.bezier import line_segment

    a, b, c = Point2D(0, 0), Point2D(0, 10), Point2D(10, 0)
    poly = Polygon(
        (a, b, c), curves=(line_segment(a, b), line_segment(b, c), line_segment(c, a))
    )
    forma = PolygonWithHoles(poly)
    curves = forma.outer.curves
    assert curves[0].p0 == forma.outer.vertices[0]
    for i in range(len(curves)):
        assert curves[i].p1 == curves[(i + 1) % len(curves)].p0


def test_furo_normalizado_tambem_inverte_a_curva():
    from app.domain.geometry import Point2D, Polygon, PolygonWithHoles
    from app.domain.geometry.bezier import line_segment

    outer = Polygon((Point2D(0, 0), Point2D(20, 0), Point2D(20, 20), Point2D(0, 20)))
    h1, h2, h3 = Point2D(5, 5), Point2D(15, 5), Point2D(15, 15)
    furo = Polygon(
        (h1, h2, h3),
        curves=(line_segment(h1, h2), line_segment(h2, h3), line_segment(h3, h1)),
    )
    forma = PolygonWithHoles(outer, (furo,))
    curves = forma.holes[0].curves
    assert len(curves) == 3
    assert curves[0].p0 == forma.holes[0].vertices[0]
    for i in range(3):
        assert curves[i].p1 == curves[(i + 1) % 3].p0
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
.venv/Scripts/python.exe -m pytest tests/domain/geometry/test_polygon_with_holes.py -v
```

Esperado: os 3 novos FALHAM — as curvas voltam na ordem original, com
`ultimo.p0 == a` em vez de `b`.

- [ ] **Step 3: Inverter as curvas em `_ccw`/`_cw`**

Substituir as duas funções em `app/domain/geometry/polygon_with_holes.py`:

```python
def _reversed_ring(polygon: Polygon) -> Polygon:
    """Anel percorrido ao contrario.

    Inverter os vertices exige tres coisas na curva, nao duas:
    1. virar a lista de ponta a ponta;
    2. trocar o sentido de cada trecho (reversed(), que troca p0<->p1);
    3. ROTACIONAR a lista em uma posicao.

    O passo 3 e o que engana. Com vertices (v0..vn-1) e trechos s_i = v_i->v_i+1,
    os vertices invertidos comecam em vn-1, entao o primeiro trecho tem que sair
    de vn-1 — ou seja s'_n-2. Sem a rotacao, os passos 1 e 2 deixam em primeiro
    s'_n-1, que sai de v0: vertices e curva comecariam em pontos diferentes e a
    exportacao gravaria a letra fora de fase com os vertices.
    """
    rev = [s.reversed() for s in reversed(polygon.curves)]
    return Polygon(
        tuple(reversed(polygon.vertices)),
        tuple(rev[1:] + rev[:1]) if rev else (),
    )


def _ccw(polygon: Polygon) -> Polygon:
    """Anel com area assinada POSITIVA (anti-horario no sentido do shoelace)."""
    return _reversed_ring(polygon) if polygon.is_clockwise else polygon


def _cw(polygon: Polygon) -> Polygon:
    """Anel com area assinada NEGATIVA (horario no sentido do shoelace)."""
    return polygon if polygon.is_clockwise else _reversed_ring(polygon)
```

Nota sobre a ordem (custou um teste vermelho para descobrir): virar a lista e
inverter cada trecho **não** basta. Isso deixa em primeiro o trecho que sai de
`v0`, mas os vértices invertidos começam em `v_{n-1}`. Falta rotacionar a lista
em uma posição. O teste do invariante (`curves[0].p0 == vertices[0]` mais o
encadeamento `curves[i].p1 == curves[i+1].p0`) é o que pega isso — o teste que
olha só um trecho específico passa por sorte.

- [ ] **Step 4: Rodar e confirmar que passa**

```
.venv/Scripts/python.exe -m pytest tests/domain/geometry -v
```

Esperado: todos PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/domain/geometry/polygon_with_holes.py tests/domain/geometry/test_polygon_with_holes.py
git commit -m "fix: normalizacao de orientacao inverte a curva junto com os vertices"
```

---

### Task 4: `CutContour` carrega a curva

**Files:**
- Modify: `app/domain/model/cut_contour.py`
- Test: `tests/domain/test_cut_contour.py`
- Test: `tests/domain/test_contour_ops.py`

**Interfaces:**
- Consumes: `BezierSegment` (Task 1)
- Produces: `CutContour(points: tuple[Point2D, ...], curves: tuple[BezierSegment, ...] = ())`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/domain/test_cut_contour.py`:

```python
def test_cut_contour_sem_curvas_por_padrao():
    from app.domain.geometry import Point2D
    from app.domain.model.cut_contour import CutContour

    c = CutContour((Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)))
    assert c.curves == ()


def test_cut_contour_aceita_curvas():
    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import BezierSegment
    from app.domain.model.cut_contour import CutContour

    seg = BezierSegment(Point2D(0, 0), Point2D(3, 2), Point2D(7, 2), Point2D(10, 0))
    c = CutContour((Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)), (seg,))
    assert c.curves == (seg,)
```

Acrescentar a `tests/domain/test_contour_ops.py`:

```python
def test_simplify_contour_descarta_a_curva():
    """Simplificar move os nos: a curva original deixa de descrever o anel e
    PRECISA ser descartada (regra de invalidacao). Sem curva, a saida degrada
    para o comportamento antigo, que e correto — nunca para corte errado."""
    import math

    from app.domain.cut.contour_ops import simplify_contour
    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import line_segment
    from app.domain.model.cut_contour import CutContour

    pts = tuple(
        Point2D(50 * math.cos(i * math.pi / 16), 50 * math.sin(i * math.pi / 16))
        for i in range(32)
    )
    curves = tuple(line_segment(pts[i], pts[(i + 1) % 32]) for i in range(32))
    c = CutContour(pts, curves)
    assert c.curves != ()

    simplificado = simplify_contour(c, 1.0)
    assert simplificado.curves == ()


def test_smooth_contour_descarta_a_curva():
    """Chaikin cria nos novos: mesma regra de invalidacao."""
    from app.domain.cut.contour_ops import smooth_contour
    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import line_segment
    from app.domain.model.cut_contour import CutContour

    pts = (Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10))
    curves = tuple(line_segment(pts[i], pts[(i + 1) % 4]) for i in range(4))
    c = CutContour(pts, curves)

    suavizado = smooth_contour(c, 1)
    assert suavizado.curves == ()
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
.venv/Scripts/python.exe -m pytest tests/domain/test_cut_contour.py tests/domain/test_contour_ops.py -v
```

Esperado: os 4 novos FALHAM (`unexpected keyword argument` / `no attribute
'curves'`).

- [ ] **Step 3: Adicionar o campo**

Em `app/domain/model/cut_contour.py`, import novo:

```python
from app.domain.geometry.bezier import BezierSegment
```

```python
@dataclass(frozen=True, slots=True)
class CutContour:
    """Contorno de corte fechado (anel de pontos em mm).

    O fechamento e implicito: o ultimo ponto conecta ao primeiro.

    'curves' guarda a Bezier ORIGINAL do arquivo, quando o contorno veio de um
    importador vetorial: os exportadores gravam a curva de verdade em vez de
    reconstruir uma por cima dos pontos. Vazio = contorno so de retas (ou
    contorno que passou por operacao que invalida a curva), e a saida usa
    'points', como antes.
    """

    points: tuple[Point2D, ...]
    curves: tuple[BezierSegment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "curves", tuple(self.curves))
        if len(self.points) < 3:
            raise ValidationError("CutContour requer ao menos 3 pontos.")
```

`origin` e `size` **não mudam** (continuam pelos pontos — quem precisa de
precisão de curva usa `bezier_bounds`).

Nenhuma alteração em `contour_ops.py`: `simplify_contour` e `smooth_contour` já
reconstroem `CutContour([...])` só com pontos, então o campo nasce vazio — a
invalidação sai de graça. Os testes do Step 1 existem justamente para travar
isso e pegar uma regressão futura.

- [ ] **Step 4: Rodar e confirmar que passa**

```
.venv/Scripts/python.exe -m pytest tests/domain -q -p no:cacheprovider
```

Esperado: nenhuma falha.

- [ ] **Step 5: Commit**

```bash
git add app/domain/model/cut_contour.py tests/domain/test_cut_contour.py tests/domain/test_contour_ops.py
git commit -m "feat: CutContour carrega a Bezier original"
```

---

### Task 5: Importador de PDF grava a curva original

**Files:**
- Modify: `app/infrastructure/importers/_flatten.py:60-77` (`to_ring`)
- Modify: `app/infrastructure/importers/pdf_vector_importer.py:80-117`
- Test: `tests/infrastructure/test_pdf_vector_importer.py`

**Interfaces:**
- Consumes: `Polygon(vertices, curves)` (Task 2), `BezierSegment`,
  `line_segment` (Task 1)
- Produces:
  - `to_ring(points, scale, curves=()) -> Polygon | None` — a lista `curves`
    chega em unidade do arquivo (pt/px) e sai convertida para mm pelo mesmo
    `scale`; se os trechos não formarem um anel fechado começando no primeiro
    vértice, devolve o anel **sem** curvas (degrada, nunca corta errado).

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/infrastructure/test_pdf_vector_importer.py` (garantir que
`import pytest` e `import pikepdf` existem no topo; se o arquivo já tiver um
helper que monta PDF a partir de um stream de conteúdo, usar o helper existente
em vez de repetir o `pikepdf.Pdf.new()`):

```python
def _pdf_com_path(tmp_path, d: str, size=(200, 200), nome="p.pdf") -> str:
    import pikepdf

    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=size)
    page.contents_add(pikepdf.Stream(pdf, d.encode()))
    out = tmp_path / nome
    pdf.save(str(out))
    return str(out)


def _circulo_d(r: float, cx: float, cy: float) -> str:
    k = 4.0 / 3.0 * (2.0**0.5 - 1.0) * r
    return (
        f"{cx + r} {cy} m "
        f"{cx + r} {cy + k} {cx + k} {cy + r} {cx} {cy + r} c "
        f"{cx - k} {cy + r} {cx - r} {cy + k} {cx - r} {cy} c "
        f"{cx - r} {cy - k} {cx - k} {cy - r} {cx} {cy - r} c "
        f"{cx + k} {cy - r} {cx + r} {cy - k} {cx + r} {cy} c h f"
    )


def test_circulo_bezier_do_pdf_sai_com_curvas(tmp_path):
    """4 Beziers entram, 4 trechos curvos saem — nenhum achatamento perdido."""
    from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter

    path = _pdf_com_path(tmp_path, _circulo_d(50.0, 100.0, 100.0), nome="circulo.pdf")

    shapes = PdfVectorImporter().load(path)

    assert len(shapes) == 1
    curves = shapes[0].outer.curves
    assert len(curves) == 4, f"esperava 4 trechos de curva, veio {len(curves)}"
    assert all(not s.is_line() for s in curves)


def test_retangulo_do_pdf_sai_com_quatro_retas(tmp_path):
    """Reta do original entra como trecho reto (is_line), nao como curva."""
    from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter

    path = _pdf_com_path(
        tmp_path, "20 20 m 80 20 l 80 60 l 20 60 l h f", size=(100, 100), nome="ret.pdf"
    )

    shapes = PdfVectorImporter().load(path)

    assert len(shapes) == 1
    curves = shapes[0].outer.curves
    assert len(curves) == 4
    assert all(s.is_line() for s in curves)


def test_curva_e_vertices_descrevem_o_mesmo_anel(tmp_path):
    """Invariante do contrato: fim de um trecho = inicio do proximo, e o
    primeiro trecho comeca no primeiro vertice."""
    from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter

    path = _pdf_com_path(
        tmp_path, _circulo_d(40.0, 60.0, 60.0), size=(120, 120), nome="anel.pdf"
    )

    ring = PdfVectorImporter().load(path)[0].outer
    curves = ring.curves
    assert curves
    assert curves[0].p0.x == pytest.approx(ring.vertices[0].x, abs=1e-9)
    assert curves[0].p0.y == pytest.approx(ring.vertices[0].y, abs=1e-9)
    for i in range(len(curves)):
        prox = curves[(i + 1) % len(curves)]
        assert curves[i].p1.x == pytest.approx(prox.p0.x, abs=1e-9)
        assert curves[i].p1.y == pytest.approx(prox.p0.y, abs=1e-9)
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
.venv/Scripts/python.exe -m pytest tests/infrastructure/test_pdf_vector_importer.py -v
```

Esperado: os 3 novos FALHAM com `len(curves) == 0`.

- [ ] **Step 3: `to_ring` aceita as curvas**

Substituir `to_ring` em `app/infrastructure/importers/_flatten.py`:

```python
def to_ring(
    points: list[tuple[float, float]],
    scale: float,
    curves: Sequence[BezierSegment] = (),
) -> Polygon | None:
    """unidade do arquivo -> mm (fator 'scale'), remove duplicatas consecutivas
    e o ponto de fechamento; descarta aneis degenerados (<3 pontos ou area ~0).

    'curves' vem na unidade do arquivo e sai escalada para mm. Se a lista
    estiver vazia ou nao formar um anel fechado que comeca no primeiro vertice,
    o Polygon sai SEM curvas: a saida degrada para polilinha (o comportamento
    antigo), que e correto — o que nao pode e curva dessincronizada dos
    vertices.
    """
    pts: list[Point2D] = []
    for x_raw, y_raw in points:
        p = Point2D(x_raw * scale, y_raw * scale)
        if pts and abs(p.x - pts[-1].x) <= DEDUP_EPS and abs(p.y - pts[-1].y) <= DEDUP_EPS:
            continue
        pts.append(p)
    # ultimo ponto == primeiro: fechamento explicito vira implicito
    if len(pts) >= 2 and (
        abs(pts[-1].x - pts[0].x) <= DEDUP_EPS and abs(pts[-1].y - pts[0].y) <= DEDUP_EPS
    ):
        pts.pop()
    if len(pts) < 3:
        return None
    scaled = _scaled_curves(curves, scale)
    if not _closes(scaled, pts[0]):
        scaled = ()
    ring = Polygon(tuple(pts), scaled)
    return ring if ring.area > _AREA_EPS else None


def _scaled_curves(
    curves: Sequence[BezierSegment], scale: float
) -> tuple[BezierSegment, ...]:
    return tuple(
        BezierSegment(
            Point2D(s.p0.x * scale, s.p0.y * scale),
            Point2D(s.c1.x * scale, s.c1.y * scale),
            Point2D(s.c2.x * scale, s.c2.y * scale),
            Point2D(s.p1.x * scale, s.p1.y * scale),
        )
        for s in curves
    )


def _closes(curves: Sequence[BezierSegment], first: Point2D) -> bool:
    """A lista descreve um anel fechado que comeca no primeiro vertice?"""
    if not curves:
        return False
    if abs(curves[0].p0.x - first.x) > _RING_EPS or abs(curves[0].p0.y - first.y) > _RING_EPS:
        return False
    for i in range(len(curves)):
        prox = curves[(i + 1) % len(curves)]
        if (
            abs(curves[i].p1.x - prox.p0.x) > _RING_EPS
            or abs(curves[i].p1.y - prox.p0.y) > _RING_EPS
        ):
            return False
    return True
```

Trocar a linha de import de `collections.abc` no topo do arquivo por:

```python
from collections.abc import Callable, Sequence
```

E acrescentar:

```python
from app.domain.geometry.bezier import BezierSegment
```

E a constante, junto das outras do topo:

```python
# Folga (mm) da checagem de anel fechado da curva. Mais larga que DEDUP_EPS
# porque o pdfium devolve float de 32 bits e o arredondamento chega a alguns
# micrometros.
_RING_EPS = 1e-3
```

- [ ] **Step 4: Importador de PDF monta os segmentos**

Em `app/infrastructure/importers/pdf_vector_importer.py`, substituir
`_object_rings` (linhas 80-117) por:

```python
    def _object_rings(self, obj, page_h: float) -> list[Polygon]:
        """Cada subpath (MOVETO ate o proximo MOVETO) do objeto vira um anel
        em mm. Fechamento fica implicito (Polygon fecha sozinho).

        Alem dos vertices achatados, monta a lista de BezierSegment ORIGINAL do
        subpath: e ela que os exportadores gravam. Reta do arquivo entra como
        trecho com controles sobre a corda (line_segment), para a lista ficar
        homogenea e is_line() reconhecer de volta na hora de gravar.
        """
        m = raw.FS_MATRIX()
        raw.FPDFPageObj_GetMatrix(obj.raw, m)

        def xform(x: float, y: float) -> tuple[float, float]:
            # matriz do objeto e depois PDF (baixo-esq) -> tela (topo-esq)
            tx = m.a * x + m.c * y + m.e
            ty = m.b * x + m.d * y + m.f
            return tx, page_h - ty

        tol_pt = self._approximation / PT2MM
        subpaths: list[tuple[list[tuple[float, float]], list[BezierSegment]]] = []
        points: list[tuple[float, float]] = []
        segs: list[BezierSegment] = []
        pending_bezier: list[tuple[float, float]] = []
        for i in range(raw.FPDFPath_CountSegments(obj.raw)):
            seg = raw.FPDFPath_GetPathSegment(obj.raw, i)
            xc, yc = ctypes.c_float(), ctypes.c_float()
            raw.FPDFPathSegment_GetPoint(seg, xc, yc)
            pt = xform(xc.value, yc.value)
            seg_type = raw.FPDFPathSegment_GetType(seg)
            if seg_type == raw.FPDF_SEGMENT_MOVETO:
                if points:
                    subpaths.append((points, segs))
                points = [pt]
                segs = []
                pending_bezier = []
            elif seg_type == raw.FPDF_SEGMENT_LINETO:
                if points:
                    segs.append(line_segment(_pt(points[-1]), _pt(pt)))
                points.append(pt)
            elif seg_type == raw.FPDF_SEGMENT_BEZIERTO:
                pending_bezier.append(pt)
                if len(pending_bezier) == 3:
                    if points:  # sem MOVETO previo o path e malformado: pula
                        start = points[-1]
                        segs.append(
                            BezierSegment(
                                _pt(start),
                                _pt(pending_bezier[0]),
                                _pt(pending_bezier[1]),
                                _pt(pending_bezier[2]),
                            )
                        )
                        flatten_curve(_cubic_at(start, *pending_bezier), tol_pt, points)
                    pending_bezier = []
        if points:
            subpaths.append((points, segs))
        return [
            ring
            for sp, sc in subpaths
            if (ring := to_ring(sp, PT2MM, _closed(sc, sp))) is not None
        ]
```

Acrescentar, no fim do módulo, os dois helpers:

```python
def _pt(xy: tuple[float, float]) -> Point2D:
    return Point2D(xy[0], xy[1])


def _closed(
    segs: list[BezierSegment], points: list[tuple[float, float]]
) -> list[BezierSegment]:
    """Fecha o anel da curva quando o subpath nao volta ao inicio.

    No PDF o 'h' (close) nao aparece como segmento: o subpath simplesmente
    termina longe do inicio e o fechamento e implicito. Os vertices ganham esse
    fechamento de graca (Polygon fecha sozinho); a lista de curvas precisa do
    trecho explicito, senao ela nao descreve o anel inteiro e to_ring descarta
    tudo.
    """
    if not segs or not points:
        return segs
    fim = segs[-1].p1
    inicio = _pt(points[0])
    if abs(fim.x - inicio.x) <= 1e-6 and abs(fim.y - inicio.y) <= 1e-6:
        return segs
    return [*segs, line_segment(fim, inicio)]
```

Imports novos no topo:

```python
from app.domain.geometry import Point2D
from app.domain.geometry.bezier import BezierSegment, line_segment
```

- [ ] **Step 5: Rodar e confirmar que passa**

```
.venv/Scripts/python.exe -m pytest tests/infrastructure/test_pdf_vector_importer.py tests/application/test_import_pdf_use_case.py -v
```

Esperado: todos PASSED.

- [ ] **Step 6: Medir no arquivo real do cliente**

```
.venv/Scripts/python.exe -c "from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter; s=PdfVectorImporter().load(r'C:\Users\Pc Fechamento\Pictures\Logo Hospital Santa Lucia for printnest.pdf'); print('pecas', len(s)); print('trechos', sum(len(f.outer.curves)+sum(len(h.curves) for h in f.holes) for f in s))"
```

Esperado: 27 peças e um total de trechos **maior que zero**, na casa de 700 (o
original tem 365 curvas + 318 retas = 683 trechos, mais os fechamentos
implícitos). Se vier zero, `_closes` está rejeitando os anéis — investigar
`_RING_EPS` antes de seguir.

- [ ] **Step 7: Commit**

```bash
git add app/infrastructure/importers/_flatten.py app/infrastructure/importers/pdf_vector_importer.py tests/infrastructure/test_pdf_vector_importer.py
git commit -m "feat: importador de PDF guarda a Bezier original do arquivo"
```

---

### Task 6: Importador de SVG grava a curva original

**Files:**
- Modify: `app/infrastructure/importers/svg_vector_importer.py:58-90`
- Test: `tests/infrastructure/test_svg_vector_importer.py`

**Interfaces:**
- Consumes: `to_ring(points, scale, curves)` (Task 5), `BezierSegment`,
  `line_segment` (Task 1)
- Produces: nada novo — só passa a preencher `Polygon.curves`.

Nota sobre o svgelements: `se.CubicBezier` tem `.start`, `.control1`,
`.control2`, `.end`. `se.QuadraticBezier` tem `.start`, `.control`, `.end` e
converte para cúbica **exata** por `c1 = start + 2/3*(control-start)`,
`c2 = end + 2/3*(control-end)`. `se.Arc` **não** tem forma cúbica exata: para
arco, cair no achatamento e devolver o anel sem curvas (degradar), em vez de
aproximar às escondidas.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/infrastructure/test_svg_vector_importer.py`:

```python
def test_circulo_cubico_do_svg_sai_com_quatro_curvas(tmp_path):
    from app.infrastructure.importers.svg_vector_importer import SvgVectorImporter

    r, cx, cy = 50.0, 60.0, 60.0
    k = 4.0 / 3.0 * (2.0**0.5 - 1.0) * r
    d = (
        f"M {cx + r},{cy} "
        f"C {cx + r},{cy + k} {cx + k},{cy + r} {cx},{cy + r} "
        f"C {cx - k},{cy + r} {cx - r},{cy + k} {cx - r},{cy} "
        f"C {cx - r},{cy - k} {cx - k},{cy - r} {cx},{cy - r} "
        f"C {cx + k},{cy - r} {cx + r},{cy - k} {cx + r},{cy} Z"
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="120px" height="120px" '
        f'viewBox="0 0 120 120"><path d="{d}" fill="black"/></svg>'
    )
    out = tmp_path / "circulo.svg"
    out.write_text(svg, encoding="utf-8")

    shapes = SvgVectorImporter().load(str(out))

    assert len(shapes) == 1
    curves = shapes[0].outer.curves
    assert len(curves) == 4
    assert all(not s.is_line() for s in curves)


def test_retangulo_do_svg_sai_com_trechos_retos(tmp_path):
    from app.infrastructure.importers.svg_vector_importer import SvgVectorImporter

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100px" height="100px" '
        'viewBox="0 0 100 100"><path d="M 10,10 L 90,10 L 90,50 L 10,50 Z" '
        'fill="black"/></svg>'
    )
    out = tmp_path / "ret.svg"
    out.write_text(svg, encoding="utf-8")

    curves = SvgVectorImporter().load(str(out))[0].outer.curves

    assert len(curves) == 4
    assert all(s.is_line() for s in curves)


def test_arco_degrada_para_polilinha_sem_inventar_curva(tmp_path):
    """Arco de SVG nao tem cubica exata. Preferimos perder a curva (saida
    antiga, correta) a gravar uma aproximacao silenciosa."""
    from app.infrastructure.importers.svg_vector_importer import SvgVectorImporter

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100px" height="100px" '
        'viewBox="0 0 100 100">'
        '<path d="M 20,50 A 30,30 0 1 1 80,50 A 30,30 0 1 1 20,50 Z" fill="black"/>'
        "</svg>"
    )
    out = tmp_path / "arco.svg"
    out.write_text(svg, encoding="utf-8")

    shapes = SvgVectorImporter().load(str(out))

    assert shapes, "o arco deve continuar virando peca, so sem curva"
    assert shapes[0].outer.curves == ()
    assert len(shapes[0].outer.vertices) > 8  # achatou de verdade
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
.venv/Scripts/python.exe -m pytest tests/infrastructure/test_svg_vector_importer.py -v
```

Esperado: os dois primeiros FALHAM com `len(curves) == 0`; o terceiro já passa
(nada preenche curvas ainda) — ele existe para travar a degradação depois.

- [ ] **Step 3: Montar os segmentos no importador de SVG**

Substituir `_element_rings` e `_flatten_subpath` em
`app/infrastructure/importers/svg_vector_importer.py`:

```python
    def _element_rings(self, shape: se.Shape) -> list[Polygon]:
        """Cada subcurva fechada do elemento vira um anel (Polygon) em mm."""
        path = abs(se.Path(shape))  # abs() garante o transform aplicado
        rings: list[Polygon] = []
        for subpath in path.as_subpaths():
            pts_px, curves_px = self._flatten_subpath(subpath)
            ring = to_ring(pts_px, _PX2MM, curves_px)
            if ring is not None:
                rings.append(ring)
        return rings

    def _flatten_subpath(
        self, subpath
    ) -> tuple[list[tuple[float, float]], list[BezierSegment]]:
        """Subcurva -> (pontos em px, curvas originais em px).

        Fechamento fica implicito (Polygon fecha sozinho); o Close so confirma
        o retorno ao inicio. A lista de curvas sai VAZIA se aparecer qualquer
        segmento sem cubica exata (se.Arc): melhor degradar para polilinha do
        que gravar uma aproximacao que o operador nao pediu.
        """
        tol_px = self._approximation / _PX2MM
        points: list[tuple[float, float]] = []
        curves: list[BezierSegment] = []
        exato = True
        for seg in subpath:
            if isinstance(seg, se.Move):
                if seg.end is not None:
                    points.append((seg.end.x, seg.end.y))
            elif isinstance(seg, (se.Line, se.Close)):
                if seg.end is None:
                    continue
                if points:
                    curves.append(
                        line_segment(_pt(points[-1]), _pt((seg.end.x, seg.end.y)))
                    )
                points.append((seg.end.x, seg.end.y))
            elif isinstance(seg, se.CubicBezier):
                curves.append(
                    BezierSegment(
                        _pt((seg.start.x, seg.start.y)),
                        _pt((seg.control1.x, seg.control1.y)),
                        _pt((seg.control2.x, seg.control2.y)),
                        _pt((seg.end.x, seg.end.y)),
                    )
                )
                flatten_curve(self._point_at(seg), tol_px, points)
            elif isinstance(seg, se.QuadraticBezier):
                # quadratica -> cubica e EXATO: c1 = s + 2/3(c-s), c2 = e + 2/3(c-e)
                sx, sy = seg.start.x, seg.start.y
                qx, qy = seg.control.x, seg.control.y
                ex, ey = seg.end.x, seg.end.y
                curves.append(
                    BezierSegment(
                        _pt((sx, sy)),
                        _pt((sx + 2.0 / 3.0 * (qx - sx), sy + 2.0 / 3.0 * (qy - sy))),
                        _pt((ex + 2.0 / 3.0 * (qx - ex), ey + 2.0 / 3.0 * (qy - ey))),
                        _pt((ex, ey)),
                    )
                )
                flatten_curve(self._point_at(seg), tol_px, points)
            elif isinstance(seg, se.Curve):  # se.Arc e o caso restante
                exato = False
                flatten_curve(self._point_at(seg), tol_px, points)
        return points, (curves if exato else [])
```

Acrescentar no fim do módulo:

```python
def _pt(xy: tuple[float, float]) -> Point2D:
    return Point2D(xy[0], xy[1])
```

Imports novos no topo:

```python
from app.domain.geometry import Point2D
from app.domain.geometry.bezier import BezierSegment, line_segment
```

Na docstring do módulo, onde diz "Curvas (Bezier/arco) viram polilinha por
subdivisao adaptativa", acrescentar:

```
  A Bezier ORIGINAL tambem e guardada (Polygon.curves) para a exportacao
  gravar curva de verdade; arco (se.Arc) nao tem cubica exata e por isso o
  anel dele sai sem curvas, degradando para polilinha.
```

- [ ] **Step 4: Rodar e confirmar que passa**

```
.venv/Scripts/python.exe -m pytest tests/infrastructure/test_svg_vector_importer.py -v
```

Esperado: 3 novos PASSED, mais os que já existiam.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/importers/svg_vector_importer.py tests/infrastructure/test_svg_vector_importer.py
git commit -m "feat: importador de SVG guarda a Bezier original do arquivo"
```

---

### Task 7: A peça posicionada leva a curva, e posiciona pela caixa exata

**Files:**
- Modify: `app/application/use_cases/run_true_shape_nesting.py:65-78`
  (`placed_cut_contours`)
- Test: `tests/application/test_run_true_shape_nesting.py`

**Interfaces:**
- Consumes: `Polygon.curves` (Task 2), `CutContour(points, curves)` (Task 4),
  `bezier_bounds` (Task 1)
- Produces: `placed_cut_contours` devolve `CutContour` com `curves` preenchido e
  posiciona a peça pela caixa envolvente **exata** da curva quando ela existe.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/application/test_run_true_shape_nesting.py`. Antes de
escrever, conferir como os testes vizinhos do arquivo constroem `PlacedItem` e
usar a mesma forma — se a assinatura não for `(artwork_id, position, rotation)`,
adaptar a construção, não a lógica do teste.

```python
def _shape_curvo(estufa: float = -2.0):
    """Triangulo cujo lado de baixo e uma curva que estufa 'estufa' em Y."""
    from app.domain.geometry import Point2D, Polygon
    from app.domain.geometry.bezier import BezierSegment, line_segment
    from app.domain.nesting.true_shape import NestingShape

    a, b, c = Point2D(0, 0), Point2D(20, 0), Point2D(20, 20)
    curvo = BezierSegment(a, Point2D(0, estufa), Point2D(20, estufa), b)
    contorno = Polygon((a, b, c), curves=(curvo, line_segment(b, c), line_segment(c, a)))
    return NestingShape("shape-0001", contorno)


def test_peca_posicionada_leva_a_curva():
    from app.application.use_cases.run_true_shape_nesting import placed_cut_contours
    from app.domain.geometry import Point2D
    from app.domain.model.placement import PlacedItem

    shape = _shape_curvo()
    item = PlacedItem("shape-0001", Point2D(100.0, 50.0), 0.0)

    contours = placed_cut_contours(shape, item)

    assert len(contours[0].curves) == 3


def test_giro_de_90_graus_gira_os_controles():
    import pytest

    from app.application.use_cases.run_true_shape_nesting import placed_cut_contours
    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import bezier_bounds
    from app.domain.model.placement import PlacedItem

    shape = _shape_curvo()

    reto = placed_cut_contours(shape, PlacedItem("shape-0001", Point2D(0.0, 0.0), 0.0))
    girado = placed_cut_contours(shape, PlacedItem("shape-0001", Point2D(0.0, 0.0), 90.0))

    box_reto = bezier_bounds(reto[0].curves)
    box_girado = bezier_bounds(girado[0].curves)
    assert box_girado.width == pytest.approx(box_reto.height, abs=1e-9)
    assert box_girado.height == pytest.approx(box_reto.width, abs=1e-9)


def test_curva_nao_estufa_para_fora_da_posicao_do_encaixe():
    """REGRESSAO: a peca era posicionada pela caixa do poligono ACHATADO. Uma
    curva que estufa para fora dele ficaria antes da posicao pedida, ou seja
    mais perto da vizinha do que o encaixe calculou. Com a caixa exata da
    curva, o canto minimo cai EXATAMENTE na posicao."""
    import pytest

    from app.application.use_cases.run_true_shape_nesting import placed_cut_contours
    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import bezier_bounds
    from app.domain.model.placement import PlacedItem

    # controles a -8: a curva estufa 6mm (0.75 * 8) para y negativo, muito alem
    # do que os tres vertices mostram
    shape = _shape_curvo(estufa=-8.0)
    item = PlacedItem("shape-0001", Point2D(100.0, 50.0), 0.0)

    box = bezier_bounds(placed_cut_contours(shape, item)[0].curves)

    assert box.min_x == pytest.approx(100.0, abs=1e-9)
    assert box.min_y == pytest.approx(50.0, abs=1e-9)


def test_sem_curva_o_posicionamento_nao_muda():
    """Peca puramente poligonal continua caindo exatamente onde caia."""
    import pytest

    from app.application.use_cases.run_true_shape_nesting import placed_cut_contours
    from app.domain.geometry import Point2D, Polygon
    from app.domain.model.placement import PlacedItem
    from app.domain.nesting.true_shape import NestingShape

    shape = NestingShape(
        "shape-0001", Polygon((Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)))
    )
    item = PlacedItem("shape-0001", Point2D(7.0, 3.0), 0.0)

    pontos = placed_cut_contours(shape, item)[0].points

    assert min(p.x for p in pontos) == pytest.approx(7.0)
    assert min(p.y for p in pontos) == pytest.approx(3.0)
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
.venv/Scripts/python.exe -m pytest tests/application/test_run_true_shape_nesting.py -v
```

Esperado: os 3 primeiros novos FALHAM (`len(contours[0].curves) == 0`, e no
terceiro `min_y == 44.0` em vez de `50.0`); o quarto já passa.

- [ ] **Step 3: Transportar a curva e usar a caixa exata**

Substituir `placed_cut_contours` em
`app/application/use_cases/run_true_shape_nesting.py`:

```python
def placed_cut_contours(shape: NestingShape, item: PlacedItem) -> list[CutContour]:
    """Peca REAL reconstruida na posicao do layout: outer + um CutContour por
    furo, todos com o MESMO transform (ver convencao no topo do modulo).

    A Bezier ORIGINAL do arquivo viaja dentro do Polygon e recebe o mesmo giro
    e o mesmo deslocamento — giro e translacao nao deformam curva, entao a
    letra sai identica a do Corel na posicao do arranjo.

    REFERENCIA DE POSICAO: quando ha curva, o canto minimo vem da caixa EXATA
    dela, nao da caixa do poligono achatado. A curva pode estufar para fora das
    cordas: usando a caixa achatada, a peca cairia antes da posicao pedida e
    ficaria mais perto da vizinha do que o encaixe calculou.
    """
    degrees = float(item.rotation)
    outer = shape.contour.rotated(degrees, around=_ORIGIN)
    bb = bezier_bounds(outer.curves) if outer.curves else outer.bounding_box
    dx = item.position.x - bb.min_x
    dy = item.position.y - bb.min_y
    moved = outer.translated(dx, dy)
    contours = [CutContour(moved.vertices, moved.curves)]
    for hole in shape.holes:
        h = hole.rotated(degrees, around=_ORIGIN).translated(dx, dy)
        contours.append(CutContour(h.vertices, h.curves))
    return contours
```

Import novo no topo:

```python
from app.domain.geometry.bezier import bezier_bounds
```

Acrescentar ao bloco RECONSTRUCAO da docstring do módulo:

```
Com curva original presente, a referencia de posicao e a caixa EXATA da Bezier
(bezier_bounds), nao a do poligono achatado.
```

- [ ] **Step 4: Rodar e confirmar que passa**

```
.venv/Scripts/python.exe -m pytest tests/application -q -p no:cacheprovider
```

Esperado: nenhuma falha.

- [ ] **Step 5: Commit**

```bash
git add app/application/use_cases/run_true_shape_nesting.py tests/application/test_run_true_shape_nesting.py
git commit -m "feat: peca posicionada leva a curva original e posiciona pela caixa exata"
```

---

### Task 8: SVG do "Enviar para o Corel" emite curvas

**Files:**
- Modify: `app/infrastructure/exporters/svg_layout_exporter.py:26-33` (`_path_d`)
- Test: `tests/infrastructure/test_svg_layout_exporter.py`

**Interfaces:**
- Consumes: `CutContour.curves` (Task 4)
- Produces: nada novo — muda só o conteúdo do atributo `d`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/infrastructure/test_svg_layout_exporter.py`:

```python
def test_contorno_com_curva_sai_com_comando_C(tmp_path):
    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import BezierSegment, line_segment
    from app.domain.model.cut_contour import CutContour
    from app.infrastructure.exporters.svg_layout_exporter import write_layout_svg

    a, b, c = Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)
    curvo = BezierSegment(a, Point2D(3, 2), Point2D(7, 2), b)
    contorno = CutContour((a, b, c), (curvo, line_segment(b, c), line_segment(c, a)))
    out = str(tmp_path / "curva.svg")

    write_layout_svg([[contorno]], 100.0, 50.0, out)
    d = open(out, encoding="utf-8").read()

    assert " C " in d, "trecho curvo tem que sair como C, nao como L"
    assert d.count(" C ") == 1, "so o trecho curvo e C; os retos sao L"


def test_retangulo_continua_so_com_L(tmp_path):
    """Regressao: contorno sem curva sai exatamente como antes."""
    from app.domain.geometry import Point2D
    from app.domain.model.cut_contour import CutContour
    from app.infrastructure.exporters.svg_layout_exporter import write_layout_svg

    contorno = CutContour(
        (Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10))
    )
    out = str(tmp_path / "ret.svg")

    write_layout_svg([[contorno]], 50.0, 20.0, out)
    d = open(out, encoding="utf-8").read()

    assert " C " not in d
    assert " L " in d


def test_trechos_retos_dentro_de_contorno_curvo_saem_como_L(tmp_path):
    """Reta gravada como reta: arquivo mais limpo e corte mais previsivel que
    uma 'curva' cujos controles estao sobre a corda."""
    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import line_segment
    from app.domain.model.cut_contour import CutContour
    from app.infrastructure.exporters.svg_layout_exporter import write_layout_svg

    a, b, c = Point2D(0, 0), Point2D(10, 0), Point2D(10, 10)
    contorno = CutContour(
        (a, b, c), (line_segment(a, b), line_segment(b, c), line_segment(c, a))
    )
    out = str(tmp_path / "retas.svg")

    write_layout_svg([[contorno]], 50.0, 20.0, out)
    d = open(out, encoding="utf-8").read()

    assert " C " not in d
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
.venv/Scripts/python.exe -m pytest tests/infrastructure/test_svg_layout_exporter.py -v
```

Esperado: o primeiro FALHA (`" C " not in d`); os outros dois já passam.

- [ ] **Step 3: Emitir `C` quando houver curva**

Substituir `_path_d` em `app/infrastructure/exporters/svg_layout_exporter.py`:

```python
def _path_d(rings: Sequence[CutContour]) -> str:
    return " ".join(_ring_d(ring) for ring in rings)


def _ring_d(ring: CutContour) -> str:
    """Um subpath do atributo 'd'.

    Com a Bezier ORIGINAL do arquivo (ring.curves), grava 'C' por trecho — e a
    curva de verdade, sem reconstrucao, e o Corel abre com a MESMA contagem de
    nos do desenho de origem. Trecho cujos controles estao sobre a corda vira
    'L': reta gravada como reta deixa o arquivo limpo e o corte previsivel. Sem
    curva (faca detectada na imagem, ou contorno simplificado), cai na
    polilinha de sempre.
    """
    if not ring.curves:
        return (
            "M " + " L ".join(f"{p.x:.3f},{p.y:.3f}" for p in ring.points) + " Z"
        )
    start = ring.curves[0].p0
    out = [f"M {start.x:.3f},{start.y:.3f}"]
    for s in ring.curves:
        if s.is_line():
            out.append(f"L {s.p1.x:.3f},{s.p1.y:.3f}")
        else:
            out.append(
                f"C {s.c1.x:.3f},{s.c1.y:.3f} {s.c2.x:.3f},{s.c2.y:.3f} "
                f"{s.p1.x:.3f},{s.p1.y:.3f}"
            )
    out.append("Z")
    return " ".join(out)
```

Na docstring do módulo, onde promete "curvas do corte" (agora verdade),
acrescentar à lista de convenções:

```
- Curva: com a Bezier original do arquivo, cada trecho sai como 'C' (o Corel
  abre com a MESMA contagem de nos do desenho de origem); trecho reto sai como
  'L'. Sem curva original, polilinha, como antes.
```

- [ ] **Step 4: Rodar e confirmar que passa**

```
.venv/Scripts/python.exe -m pytest tests/infrastructure/test_svg_layout_exporter.py -v
```

Esperado: todos PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/exporters/svg_layout_exporter.py tests/infrastructure/test_svg_layout_exporter.py
git commit -m "fix: Enviar para o Corel grava curva de verdade, nao polilinha"
```

---

### Task 9: DXF usa a curva original quando existe

**Files:**
- Modify: `app/infrastructure/exporters/dxf_exporter.py:53-76`
- Test: `tests/infrastructure/test_dxf_exporter.py`

**Interfaces:**
- Consumes: `CutContour.curves` (Task 4), `BezierSegment` (Task 1)
- Produces: nada novo — o DXF continua saindo com SPLINE fechado por contorno
  curvo e LWPOLYLINE por contorno reto.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar a `tests/infrastructure/test_dxf_exporter.py`:

```python
def test_dxf_usa_a_curva_original_em_vez_de_refazer(tmp_path):
    """Com a Bezier do arquivo, o spline sai dos controles ORIGINAIS. Prova: um
    contorno de 3 nos cuja curva estufa 6mm. O refit (que so ve os nos) nunca
    produziria essa altura; a curva original produz."""
    import ezdxf

    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import BezierSegment, line_segment
    from app.domain.model.cut_contour import CutContour
    from app.infrastructure.exporters.dxf_exporter import DxfExporter

    a, b, c = Point2D(0, 0), Point2D(20, 0), Point2D(20, 20)
    curvo = BezierSegment(a, Point2D(0, -8), Point2D(20, -8), b)
    contorno = CutContour((a, b, c), (curvo, line_segment(b, c), line_segment(c, a)))
    out = str(tmp_path / "curva.dxf")

    DxfExporter().export([contorno], out)

    doc = ezdxf.readfile(out)
    splines = list(doc.modelspace().query("SPLINE"))
    assert len(splines) == 1
    alturas = [p.y for p in splines[0].control_points]
    # a curva estufa 6mm alem da corda, entao a altura passa dos 20mm dos nos
    assert max(alturas) - min(alturas) > 24.0


def test_dxf_sem_curva_original_continua_no_refit(tmp_path):
    """Regressao: contorno de deteccao (sem curva) mantem o comportamento
    aprovado — refit por cubic_segments e spline fechado."""
    import math

    import ezdxf

    from app.domain.geometry import Point2D
    from app.domain.model.cut_contour import CutContour
    from app.infrastructure.exporters.dxf_exporter import DxfExporter

    pts = tuple(
        Point2D(50 + 40 * math.cos(i * math.pi / 8), 50 + 40 * math.sin(i * math.pi / 8))
        for i in range(16)
    )
    out = str(tmp_path / "refit.dxf")

    DxfExporter().export([CutContour(pts)], out)

    doc = ezdxf.readfile(out)
    assert len(list(doc.modelspace().query("SPLINE"))) == 1


def test_dxf_de_retas_continua_lwpolyline(tmp_path):
    import ezdxf

    from app.domain.geometry import Point2D
    from app.domain.geometry.bezier import line_segment
    from app.domain.model.cut_contour import CutContour
    from app.infrastructure.exporters.dxf_exporter import DxfExporter

    a, b, c, d = Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)
    contorno = CutContour(
        (a, b, c, d),
        (line_segment(a, b), line_segment(b, c), line_segment(c, d), line_segment(d, a)),
    )
    out = str(tmp_path / "ret.dxf")

    DxfExporter().export([contorno], out)

    doc = ezdxf.readfile(out)
    assert len(list(doc.modelspace().query("LWPOLYLINE"))) == 1
    assert not list(doc.modelspace().query("SPLINE"))
```

- [ ] **Step 2: Rodar e confirmar que falha**

```
.venv/Scripts/python.exe -m pytest tests/infrastructure/test_dxf_exporter.py -v
```

Esperado: o primeiro FALHA (a altura fica em ~20mm, porque o refit ignora os
controles originais); os outros dois já passam.

- [ ] **Step 3: Preferir a curva original**

Em `app/infrastructure/exporters/dxf_exporter.py`, substituir o laço
`for contour in contours:` (linhas 53-76) por:

```python
        for contour in contours:
            flipped = [Point2D(p.x, fy(p.y)) for p in contour.points]
            # contorno CURVO sai como UM SPLINE FECHADO por contorno (F3:
            # render_splines_and_polylines quebrava o caminho a cada canto —
            # a letra abria em pedacos no Corel). Bezier -> B-spline e EXATO
            # (mesma curva, nos internos com multiplicidade 3 preservam os
            # cantos vivos); retas/retangulos seguem como polyline.
            #
            # ORIGEM DA CURVA: se o contorno trouxe a Bezier do ARQUIVO
            # (importador vetorial), usa ela — e a curva de verdade, com a
            # contagem de nos do desenho. Sem ela (faca detectada na imagem,
            # ou contorno simplificado), cai no refit de cubic_segments, que
            # adivinha uma curva por cima dos pontos.
            segs = (
                [_flip_segment(s, fy) for s in contour.curves]
                if contour.curves
                else cubic_segments(flipped)
            )
            if segs and has_curves(segs):
                beziers = [
                    Bezier4P((
                        Vec3(s.p0.x, s.p0.y, 0.0),
                        Vec3(s.c1.x, s.c1.y, 0.0),
                        Vec3(s.c2.x, s.c2.y, 0.0),
                        Vec3(s.p1.x, s.p1.y, 0.0),
                    ))
                    for s in segs
                ]
                spline = msp.add_spline(dxfattribs={"layer": CUT_LAYER})
                spline.apply_construction_tool(bezier_to_bspline(beziers))
                spline.closed = True
                continue
            points = [(p.x, p.y) for p in flipped]
            msp.add_lwpolyline(points, close=True, dxfattribs={"layer": CUT_LAYER})
```

Acrescentar, no fim do módulo (fora da classe):

```python
def _flip_segment(s: BezierSegment, fy) -> BezierSegment:
    """Espelha o trecho no mesmo eixo do resto da geometria (y' = H - y).

    Espelhar inverte o sentido de percurso do anel, o que nao altera a forma
    gravada — o DXF descreve a mesma curva.
    """
    return BezierSegment(
        Point2D(s.p0.x, fy(s.p0.y)),
        Point2D(s.c1.x, fy(s.c1.y)),
        Point2D(s.c2.x, fy(s.c2.y)),
        Point2D(s.p1.x, fy(s.p1.y)),
    )
```

Import novo no topo:

```python
from app.domain.geometry.bezier import BezierSegment
```

- [ ] **Step 4: Rodar e confirmar que passa**

```
.venv/Scripts/python.exe -m pytest tests/infrastructure/test_dxf_exporter.py tests/application/test_export_dxf_use_case.py tests/qa/test_qa_f3_dxf_contorno_unico.py -v
```

Esperado: todos PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/exporters/dxf_exporter.py tests/infrastructure/test_dxf_exporter.py
git commit -m "feat: DXF grava a curva original do arquivo quando ela existe"
```

---

### Task 10: Regressão com o arquivo real do cliente e fecho da suíte

**Files:**
- Create: `tests/qa/test_qa_curvas_originais_modo_corte.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: tudo das tarefas 1-9.
- Produces: nada — é o teste de aceitação do defeito relatado.

Sobre a arte do cliente: o teste **não** commita o logo do hospital no
repositório. Ele procura o PDF em `tests/fixtures/` e, se não achar, em
`~/Pictures`; se nenhum dos dois existir, `pytest.skip`. Assim a suíte roda em
qualquer máquina e continua valendo como prova na máquina do Philipe. Se depois
se decidir versionar a arte, basta copiá-la para `tests/fixtures/` — sem
mudança de código.

- [ ] **Step 1: Escrever o teste de aceitação**

Criar `tests/qa/test_qa_curvas_originais_modo_corte.py`:

```python
"""QA do defeito relatado em 2026-08-17: letras de acrilico saindo facetadas.

Medicao no arquivo do cliente ANTES da correcao: 720 nos e 365 curvas Bezier
entravam; 2.089 vertices e ZERO curvas saiam. Este teste trava o numero.

Ver docs/especificacoes/CURVAS-ORIGINAIS-MODO-CORTE.md
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import ezdxf
import pytest

from app.application.use_cases.run_true_shape_nesting import (
    placed_cut_contours,
    to_nesting_shapes,
)
from app.domain.geometry import Point2D
from app.domain.model.placement import PlacedItem
from app.infrastructure.exporters.dxf_exporter import DxfExporter
from app.infrastructure.exporters.svg_layout_exporter import write_layout_svg
from app.infrastructure.importers.pdf_vector_importer import PdfVectorImporter

_NOME = "Logo Hospital Santa Lucia for printnest.pdf"
_CANDIDATOS = (
    Path(__file__).resolve().parents[1] / "fixtures" / _NOME,
    Path(os.path.expanduser("~")) / "Pictures" / _NOME,
)


def _arquivo() -> Path:
    for p in _CANDIDATOS:
        if p.is_file():
            return p
    pytest.skip(f"arte do cliente ausente (procurei em: {', '.join(map(str, _CANDIDATOS))})")


def _pecas_posicionadas():
    """Cada peca posta numa posicao fixa — o alvo aqui e a GRAVACAO, nao o
    encaixe, entao nao roda o packer (mais rapido e deterministico)."""
    shapes = to_nesting_shapes(PdfVectorImporter().load(str(_arquivo())))
    return [
        placed_cut_contours(s, PlacedItem(s.artwork_id, Point2D(10.0 * i, 10.0), 0.0))
        for i, s in enumerate(shapes)
    ]


def test_letras_do_cliente_entram_e_saem_com_curva():
    """As 365 curvas do PDF do Corel chegam ao contorno importado."""
    shapes = PdfVectorImporter().load(str(_arquivo()))

    curvos = sum(
        sum(1 for s in ring.curves if not s.is_line())
        for shape in shapes
        for ring in (shape.outer, *shape.holes)
    )
    assert curvos >= 365, f"esperava ao menos as 365 curvas do original, veio {curvos}"


def test_svg_para_o_corel_sai_com_curva_e_sem_explosao_de_nos():
    """O SVG do 'Enviar para o Corel' grava C, e a contagem de nos fica na
    ordem do original (720), nao dos 2.089 vertices achatados."""
    pieces = _pecas_posicionadas()

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "layout.svg")
        write_layout_svg(pieces, 3000.0, 3000.0, out)
        d = Path(out).read_text(encoding="utf-8")

    assert " C " in d, "o SVG do Corel voltou a sair sem curva"
    nos = d.count(" C ") + d.count(" L ")
    assert nos < 1200, f"explosao de nos: {nos} (o original tem ~720)"


def test_dxf_sai_com_spline():
    contours = [c for piece in _pecas_posicionadas() for c in piece]

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "corte.dxf")
        DxfExporter().export(contours, out)
        doc = ezdxf.readfile(out)

    assert list(doc.modelspace().query("SPLINE")), "nenhum spline no DXF"
```

- [ ] **Step 2: Rodar e verificar**

```
.venv/Scripts/python.exe -m pytest tests/qa/test_qa_curvas_originais_modo_corte.py -v
```

Esperado: 3 PASSED na máquina do Philipe (arte presente em `~/Pictures`);
3 SKIPPED em máquina sem a arte.

- [ ] **Step 3: Rodar a suíte inteira e comparar com a linha de base**

```
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests/presentation --junit-xml=depois.xml
.venv/Scripts/python.exe -c "import xml.etree.ElementTree as ET; s=ET.parse('depois.xml').getroot().find('testsuite').attrib; print({k:s[k] for k in ('tests','failures','errors','skipped')})"
```

Esperado: `failures: 0`, `errors: 0`, e `tests` maior que 792 (os testes novos).
Qualquer falha aqui é regressão — investigar, não ajustar o teste.

- [ ] **Step 4: Rodar a pasta de apresentação, arquivo por arquivo**

Ela pendura como pasta, então:

```
.venv/Scripts/python.exe -m pytest tests/presentation/test_main_window.py -q -p no:cacheprovider
.venv/Scripts/python.exe -m pytest tests/presentation/test_cut_mode_dialog.py -q -p no:cacheprovider
```

Se houver outros arquivos em `tests/presentation`, rodar cada um. Esperado: sem
falhas. É aqui que se pega quebra no Modo Corte e na faca de impressão.

- [ ] **Step 5: Apagar o XML temporário e commitar o teste**

```bash
rm -f depois.xml
git add tests/qa/test_qa_curvas_originais_modo_corte.py
git commit -m "test: regressao das curvas originais com o arquivo real do cliente"
```

- [ ] **Step 6: Atualizar o CHANGELOG**

Acrescentar em `CHANGELOG.md`, na seção da 1.1.3 (criar a seção se não existir),
no estilo das entradas vizinhas:

```markdown
### Corrigido
- Modo Corte: as curvas do arquivo original (CorelDRAW) são preservadas até o
  corte. O "Enviar para o Corel" gravava polilinha — letras grandes saíam
  facetadas e o laser perdia acabamento. Agora tanto o SVG quanto o DXF levam a
  Bézier do desenho, com a mesma contagem de nós do original.
```

```bash
git add CHANGELOG.md
git commit -m "docs: changelog da correcao das curvas do Modo Corte"
```

- [ ] **Step 7: Prova visual no aplicativo (manual, com o Philipe)**

Não é teste automatizado; é a confirmação que fecha o pedido:

1. Abrir o PrintNest, entrar no Modo Corte.
2. Importar `Logo Hospital Santa Lucia for printnest.pdf`.
3. Clicar em Organizar.
4. Clicar em **Enviar para o Corel**.
5. No CorelDRAW, selecionar uma letra e olhar a contagem de nós na barra de
   status: deve estar na ordem do desenho original, não em centenas.
6. Sobrepor com a letra original (o mesmo teste que gerou as imagens do relato):
   as linhas devem coincidir, sem faceta.
7. Repetir com **Exportar DXF** e abrir o `.dxf` no Corel.

---

## Auto-revisão do plano

**Cobertura da especificação:**

| Seção da spec | Tarefa |
|---|---|
| 3.1 `BezierSegment` desce para geometry | Task 1 |
| 3.2 `Polygon.curves` + regra de invalidação | Task 2 (campo/transforms), Task 4 (testes da invalidação em `contour_ops`) |
| 3.3 orientação canônica inverte curvas | Task 3 |
| 3.4 `CutContour.curves` | Task 4 |
| 3.5 importadores gravam a curva | Task 5 (PDF), Task 6 (SVG) |
| 3.6 transporte + bbox exata | Task 7 |
| 3.7 exportadores | Task 8 (SVG), Task 9 (DXF) |
| 5 degradação sem exceção nova | Task 5 (`_closes` → sem curva), Task 6 (arco → sem curva), Tasks 8 e 9 (ramo sem curva) |
| 7 testes 1-10 | 1→Task 2; 2→Task 3; 3→Task 4; 4→Task 5; 5→Task 6; 6→Task 7; 7→Task 8; 8→Task 9; 9→Task 10; 10→Task 10 Step 3 |

**Lacuna encontrada e corrigida:** a especificação não previa o fechamento
implícito do anel na lista de curvas — o `h` (close) do PDF não aparece como
segmento. Sem tratar isso, `_closes` rejeitaria todas as curvas e a correção não
teria efeito nenhum. Coberto pelo helper `_closed` na Task 5, Step 4, e pelo
diagnóstico da mesma tarefa no Step 6.

**Segunda lacuna:** a spec citava `simplify_contour` como caminho de
invalidação, mas `smooth_contour` (Chaikin) tem exatamente o mesmo problema e
não estava listado. Coberto na Task 4.

**Consistência de nomes e tipos:** `BezierSegment`, `line_segment`,
`bezier_bounds`, `Polygon.curves`, `CutContour.curves`,
`to_ring(points, scale, curves)`, `_flip_segment`, `_reversed_ring` — mesmos
nomes em todas as tarefas que os consomem. `is_line()` aparece nas Tasks 1, 5,
6, 8, 9 e 10 sempre com a mesma assinatura. `_pt` é helper local e é definido
separadamente nos dois importadores (Tasks 5 e 6), de propósito: são módulos
independentes e um import cruzado entre importadores seria acoplamento inútil.
