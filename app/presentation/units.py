"""Unidade de exibicao (mm/cm).

Regra de ouro: TUDO e armazenado em milimetros (dominio, settings, posicoes da
cena). Este modulo so converte/formata para EXIBIR e EDITAR na unidade que o
usuario escolheu. Estado global simples (uma janela por processo), com funcoes
puras de formatacao faceis de testar.
"""

from __future__ import annotations

MM = "mm"
CM = "cm"
_VALID = (MM, CM)

# valor_exibido = mm * _PER_MM[unidade]
_PER_MM = {MM: 1.0, CM: 0.1}
# casas decimais usadas ao exibir/editar comprimentos
_DECIMALS = {MM: 1, CM: 2}

_current = CM  # padrao: centimetros (preferencia do usuario)


def set_unit(unit: str) -> None:
    global _current
    if unit in _VALID:
        _current = unit


def unit() -> str:
    return _current


def _u(u: str | None) -> str:
    return u if u in _VALID else _current


def from_mm(mm: float, u: str | None = None) -> float:
    """Converte mm para a unidade de exibicao."""
    return float(mm) * _PER_MM[_u(u)]


def to_mm(value: float, u: str | None = None) -> float:
    """Converte um valor na unidade de exibicao de volta para mm."""
    return float(value) / _PER_MM[_u(u)]


def decimals(u: str | None = None) -> int:
    return _DECIMALS[_u(u)]


def step_mm(u: str | None = None) -> float:
    """Passo (em mm) de um incremento natural na unidade: 1mm ou 1cm."""
    return 1.0 if _u(u) == MM else 10.0


def fmt_len(mm: float, u: str | None = None, *, with_unit: bool = True) -> str:
    """Comprimento formatado, ex.: '13,00 cm' ou '130.0 mm'."""
    uu = _u(u)
    txt = f"{from_mm(mm, uu):.{_DECIMALS[uu]}f}"
    return f"{txt} {uu}" if with_unit else txt


def fmt_area(mm2: float, u: str | None = None) -> str:
    """Area formatada na unidade quadrada correspondente (cm2 ou mm2)."""
    if _u(u) == CM:
        return f"{mm2 / 100.0:.2f} cm²"
    return f"{mm2:.0f} mm²"


def fmt_xy(x_mm: float, y_mm: float, u: str | None = None) -> str:
    """Par X, Y formatado, ex.: '12,30, -0,90 cm'."""
    uu = _u(u)
    d = _DECIMALS[uu]
    return f"{from_mm(x_mm, uu):.{d}f}, {from_mm(y_mm, uu):.{d}f} {uu}"
