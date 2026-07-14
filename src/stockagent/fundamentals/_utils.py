from __future__ import annotations

from typing import Callable, Protocol, TypeVar


class _HasFiscalYear(Protocol):
    fiscal_year: int


_InputT = TypeVar("_InputT")
_MetricsT = TypeVar("_MetricsT", bound=_HasFiscalYear)


def safe_divide(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def compute_free_cash_flow(
    operating_cash_flow: float | None,
    capex: float | None,
) -> float | None:
    if operating_cash_flow is None or capex is None:
        return None
    return operating_cash_flow - capex


def compute_series(
    fn: Callable[[_InputT], _MetricsT],
    inputs: list[_InputT],
) -> list[_MetricsT]:
    return sorted([fn(item) for item in inputs], key=lambda metric: metric.fiscal_year)
