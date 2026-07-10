from __future__ import annotations

from stockagent.financials import ValuationMetrics
from stockagent.fundamentals.inputs import ValuationInput


def _positive(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    return value


def _safe_positive_divide(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    positive_numerator = _positive(numerator)
    positive_denominator = _positive(denominator)
    if positive_numerator is None or positive_denominator is None:
        return None
    return positive_numerator / positive_denominator


def compute_valuation(vi: ValuationInput) -> ValuationMetrics:
    """Compute trailing PE/PB/PS from one year's data and market inputs."""
    metrics = ValuationMetrics(
        fiscal_year=vi.fiscal_year,
        stock_price=vi.price,
        market_cap=vi.market_cap,
    )

    metrics.pe_ratio = _safe_positive_divide(vi.price, vi.eps_diluted)
    if metrics.pe_ratio is None:
        metrics.pe_ratio = _safe_positive_divide(vi.market_cap, vi.net_income)

    metrics.pb_ratio = _safe_positive_divide(
        vi.market_cap,
        vi.shareholders_equity,
    )
    metrics.ps_ratio = _safe_positive_divide(vi.market_cap, vi.revenue)

    return metrics
