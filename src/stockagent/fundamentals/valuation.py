from __future__ import annotations

from stockagent.financials import FinancialRecord, ValuationMetrics


def _positive(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    return value


def _safe_positive_divide(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    """Divide only positive valuation operands, otherwise report an unavailable ratio."""
    positive_numerator = _positive(numerator)
    positive_denominator = _positive(denominator)
    if positive_numerator is None or positive_denominator is None:
        return None
    return positive_numerator / positive_denominator


def compute_valuation(
    record: FinancialRecord,
    price: float | None,
    market_cap: float | None,
) -> ValuationMetrics:
    """Compute trailing PE/PB/PS from a standardized annual record and market inputs."""
    metrics = ValuationMetrics(
        fiscal_year=record.fiscal_year,
        stock_price=price,
        market_cap=market_cap,
    )

    # 先计算 price / eps_diluted；结果为 None 时改用 market_cap / net_income
    metrics.pe_ratio = _safe_positive_divide(price, record.eps_diluted)
    if metrics.pe_ratio is None:
        metrics.pe_ratio = _safe_positive_divide(market_cap, record.net_income)

    metrics.pb_ratio = _safe_positive_divide(
        market_cap,
        record.shareholders_equity,
    )
    metrics.ps_ratio = _safe_positive_divide(market_cap, record.revenue)

    return metrics
