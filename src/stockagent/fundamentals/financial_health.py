from __future__ import annotations

from stockagent.financials import FinancialHealthMetrics
from stockagent.fundamentals._utils import compute_series, safe_divide
from stockagent.fundamentals.inputs import FinancialHealthInput


def compute_financial_health(fi: FinancialHealthInput) -> FinancialHealthMetrics:
    """Compute financial health ratios from a single year's financial data."""
    metrics = FinancialHealthMetrics(fiscal_year=fi.fiscal_year)

    metrics.equity_ratio = safe_divide(fi.shareholders_equity, fi.total_assets)
    metrics.liabilities_to_assets = safe_divide(fi.total_liabilities, fi.total_assets)
    metrics.current_ratio = safe_divide(fi.current_assets, fi.current_liabilities)
    metrics.cash_ratio = safe_divide(fi.cash_and_equivalents, fi.current_liabilities)
    metrics.operating_cash_flow_to_total_liabilities = safe_divide(
        fi.operating_cash_flow,
        fi.total_liabilities,
    )

    return metrics


def compute_financial_health_series(
    inputs: list[FinancialHealthInput],
) -> list[FinancialHealthMetrics]:
    """Compute financial health metrics for multiple years, sorted by fiscal year."""
    return compute_series(compute_financial_health, inputs)
