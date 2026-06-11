from __future__ import annotations

from stockagent.financials.models import FinancialHealthMetrics
from stockagent.fundamentals.inputs import FinancialHealthInput


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def compute_financial_health(fi: FinancialHealthInput) -> FinancialHealthMetrics:
    """Compute financial health ratios from a single year's financial data."""
    metrics = FinancialHealthMetrics(fiscal_year=fi.fiscal_year)

    metrics.equity_ratio = _safe_divide(fi.shareholders_equity, fi.total_assets)
    metrics.liabilities_to_assets = _safe_divide(fi.total_liabilities, fi.total_assets)
    metrics.current_ratio = _safe_divide(fi.current_assets, fi.current_liabilities)
    metrics.cash_ratio = _safe_divide(fi.cash_and_equivalents, fi.current_liabilities)
    metrics.operating_cash_flow_to_total_liabilities = _safe_divide(
        fi.operating_cash_flow,
        fi.total_liabilities,
    )

    return metrics


def compute_financial_health_series(
    inputs: list[FinancialHealthInput],
) -> list[FinancialHealthMetrics]:
    """Compute financial health metrics for multiple years, sorted by fiscal year."""
    return sorted(
        [compute_financial_health(fi) for fi in inputs],
        key=lambda metrics: metrics.fiscal_year,
    )
