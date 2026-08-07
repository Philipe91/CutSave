"""Baseline de aproveitamento do nesting do MODO IMPRESSAO.

Por que existe (07/08/2026): o Philipe autorizou mexer no motor de encaixe do
Modo Impressao (`MaxRectsPacker`) para economizar chapa e girar peca sozinho,
com a condicao de haver um ponto de volta. Poder voltar e o minimo; o que ele
quer de verdade e SABER se ficou melhor. Sem numero medido antes, "melhorou"
e opiniao.

Entao: este script mede o motor de hoje num conjunto fixo de casos e congela
os numeros em `docs/qa/BASELINE-NESTING-IMPRESSAO.json`. Qualquer mudanca no
motor e comparada contra esse arquivo — e piorar QUALQUER caso reprova, nao
importa quanto tenha melhorado nos outros.

    python scripts/nesting_baseline.py --gravar   # congela o estado de hoje
    python scripts/nesting_baseline.py            # compara; sai != 0 se piorou

A comparacao tambem roda na suite (tests/application/test_nesting_baseline.py),
entao a regressao aparece sem ninguem lembrar de rodar isto na mao.

NAO confundir os dois motores: o do Modo CORTE (`TrueShapePacker`) esta
congelado desde 22/07 e nao entra aqui.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ is None and str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.application.use_cases.run_grid_nesting import RunGridNestingUseCase
from app.domain.geometry import Size
from app.domain.model.artwork import ArtKind, Artwork, FileFormat
from app.domain.model.material import Material
from app.domain.nesting.max_rects import MaxRectsPacker

ARQUIVO_BASELINE = (
    Path(__file__).resolve().parent.parent / "docs" / "qa"
    / "BASELINE-NESTING-IMPRESSAO.json"
)
# margem de ruido: diferenca menor que isto nao conta como piora (float e
# ordenacao estavel, mas nao vale reprovar por 0,001%)
TOLERANCIA_PCT = 0.05


@dataclass(frozen=True)
class Caso:
    """Um cenario de chapa. 'pecas' = lista de (largura, altura, quantidade)."""

    nome: str
    largura_chapa: float
    comprimento_chapa: float
    espacamento: float
    pecas: tuple[tuple[float, float, int], ...]
    porque: str


# Casos escolhidos pelo que eles EXERCITAM, nao por serem bonitos. Cada um
# cobre uma forma de desperdicio diferente; um motor que melhora a media mas
# piora um destes esta trocando um problema por outro.
CASOS = (
    Caso(
        "identicas-largura-justa", 1300.0, 3000.0, 5.0, ((420.0, 297.0, 40),),
        "muitas peças iguais: mede o desperdício da borda direita",
    ),
    Caso(
        "identicas-deitadas", 1300.0, 3000.0, 5.0, ((297.0, 420.0, 40),),
        "as MESMAS peças em pé. Medido em 07/08: dá o mesmo 63,97% do caso "
        "anterior — com peças todas iguais o motor já empata nas duas "
        "orientações, então o ganho da rotação NÃO vem daqui. Fica no conjunto "
        "como controle: se um motor com rotação piorar este caso, quebrou algo",
    ),
    Caso(
        "tamanhos-misturados", 1300.0, 3000.0, 5.0,
        ((600.0, 400.0, 8), (300.0, 200.0, 20), (150.0, 150.0, 30)),
        "grandes + médias + pequenas: mede se as pequenas preenchem os vãos",
    ),
    Caso(
        "tiras-compridas", 1300.0, 3000.0, 5.0, ((1200.0, 90.0, 25),),
        "peça quase da largura da chapa: sobra pouco e o encaixe erra feio",
    ),
    Caso(
        "poucas-grandes", 1300.0, 3000.0, 5.0, ((800.0, 600.0, 6),),
        "peça grande demais para caber duas lado a lado: metade da chapa vaga",
    ),
    Caso(
        "mistura-extrema", 1300.0, 3000.0, 5.0,
        ((1100.0, 700.0, 3), (250.0, 250.0, 24), (80.0, 60.0, 60)),
        "uma dominante e muitas miúdas: o pior caso do MaxRects hoje",
    ),
    Caso(
        "chapa-estreita", 600.0, 3000.0, 3.0,
        ((280.0, 180.0, 30), (140.0, 100.0, 40)),
        "chapa estreita: pouca liberdade lateral, cada mm conta",
    ),
    Caso(
        "sem-espacamento", 1300.0, 3000.0, 0.0, ((320.0, 240.0, 36),),
        "sangria zero: separa o desperdício do motor do desperdício do vão",
    ),
)


def _artwork(indice: int, largura: float, altura: float) -> Artwork:
    return Artwork(
        id=f"a{indice}", name=f"a{indice}", file_format=FileFormat.PDF,
        size=Size(largura, altura), kind=ArtKind.RETANGULAR,
    )


def medir(caso: Caso) -> dict:
    """Roda o motor do Modo Impressao e devolve as medidas do caso."""
    artes = []
    for largura, altura, qtd in caso.pecas:
        for _ in range(qtd):
            artes.append(_artwork(len(artes), largura, altura))
    material = Material(
        name=caso.nome, width=caso.largura_chapa, spacing=caso.espacamento,
        spacing_y=caso.espacamento,
    )
    chapas = RunGridNestingUseCase(MaxRectsPacker()).execute_sheets(
        artes, material, caso.comprimento_chapa
    )
    postas = sum(c.item_count for c in chapas)
    area_pecas = sum(l * a * q for l, a, q in caso.pecas)
    area_chapas = sum(c.material.width * c.used_length for c in chapas)
    return {
        "chapas": len(chapas),
        "pecas": postas,
        "pecas_pedidas": len(artes),
        "comprimento_usado_mm": round(sum(c.used_length for c in chapas), 2),
        # a metrica que importa: quanto da chapa consumida virou peca
        "aproveitamento_pct": round(area_pecas / area_chapas * 100.0, 3)
        if area_chapas > 0 else 0.0,
    }


def medir_todos() -> dict:
    return {caso.nome: medir(caso) for caso in CASOS}


def carregar_baseline() -> dict:
    if not ARQUIVO_BASELINE.exists():
        raise FileNotFoundError(
            f"Baseline ausente: {ARQUIVO_BASELINE}. "
            "Rode 'python scripts/nesting_baseline.py --gravar' primeiro."
        )
    return json.loads(ARQUIVO_BASELINE.read_text(encoding="utf-8"))["casos"]


def comparar(atual: dict, baseline: dict) -> list[str]:
    """Regressoes encontradas. Vazio = nada piorou."""
    problemas = []
    for nome, base in baseline.items():
        agora = atual.get(nome)
        if agora is None:
            problemas.append(f"{nome}: sumiu do conjunto de casos")
            continue
        if agora["pecas"] < base["pecas"]:
            problemas.append(
                f"{nome}: colocou {agora['pecas']} peças, antes colocava "
                f"{base['pecas']}"
            )
        if agora["chapas"] > base["chapas"]:
            problemas.append(
                f"{nome}: usou {agora['chapas']} chapas, antes usava "
                f"{base['chapas']}"
            )
        queda = base["aproveitamento_pct"] - agora["aproveitamento_pct"]
        if queda > TOLERANCIA_PCT:
            problemas.append(
                f"{nome}: aproveitamento caiu de {base['aproveitamento_pct']:.2f}% "
                f"para {agora['aproveitamento_pct']:.2f}% (-{queda:.2f})"
            )
    return problemas


def _gravar(atual: dict) -> None:
    ARQUIVO_BASELINE.parent.mkdir(parents=True, exist_ok=True)
    conteudo = {
        "o_que_e": (
            "Aproveitamento do nesting do MODO IMPRESSAO (MaxRectsPacker) medido "
            "ANTES de mexer no motor. Gerado por scripts/nesting_baseline.py. "
            "Piorar qualquer caso reprova a mudança."
        ),
        "casos": atual,
        "porque_cada_caso": {c.nome: c.porque for c in CASOS},
    }
    ARQUIVO_BASELINE.write_text(
        json.dumps(conteudo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gravar", action="store_true",
                    help="congela as medidas de agora como baseline")
    args = ap.parse_args(argv)

    atual = medir_todos()
    largura = max(len(c.nome) for c in CASOS)
    for nome, m in atual.items():
        print(
            f"{nome:<{largura}}  {m['aproveitamento_pct']:6.2f}%  "
            f"{m['chapas']} chapa(s)  {m['pecas']}/{m['pecas_pedidas']} peças"
        )
    if args.gravar:
        _gravar(atual)
        print(f"\nBaseline gravado em {ARQUIVO_BASELINE}")
        return 0
    problemas = comparar(atual, carregar_baseline())
    if problemas:
        print("\nREGRESSAO:")
        for p in problemas:
            print(f"  - {p}")
        return 1
    print("\nNada piorou.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
