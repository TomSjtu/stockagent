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
    """Divide only when both annual inputs are present and the denominator is nonzero."""
    # 任一操作数为 None 或分母为零时返回 None；否则返回两个 float 的商
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def compute_series(
    fn: Callable[[_InputT], _MetricsT],
    inputs: list[_InputT],
) -> list[_MetricsT]:
    """Apply an annual formula and return results in fiscal-year order."""
    return sorted([fn(item) for item in inputs], key=lambda metric: metric.fiscal_year)
