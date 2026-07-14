from __future__ import annotations

from stockagent.financials import ProfitabilityMetrics
from stockagent.fundamentals._utils import compute_series, safe_divide
from stockagent.fundamentals.inputs import ProfitabilityInput


def compute_profitability(fi: ProfitabilityInput) -> ProfitabilityMetrics:
    """Compute all profitability ratios from a single year's financial data."""
    metrics = ProfitabilityMetrics(fiscal_year=fi.fiscal_year)

    # Margins
    metrics.gross_margin = safe_divide(fi.gross_profit, fi.revenue)
    metrics.operating_margin = safe_divide(fi.operating_income, fi.revenue)
    metrics.net_margin = safe_divide(fi.net_income, fi.revenue)

    # Expense ratios
    metrics.rd_ratio = safe_divide(fi.rd_expense, fi.revenue)
    metrics.sga_ratio = safe_divide(fi.sga_expense, fi.revenue)

    # Return on capital
    metrics.roa = safe_divide(fi.net_income, fi.total_assets)
    metrics.roe = safe_divide(fi.net_income, fi.shareholders_equity)
    capital_employed = (fi.total_assets - fi.current_liabilities
                        if fi.total_assets is not None and fi.current_liabilities is not None
                        else None)
    metrics.roce = safe_divide(fi.operating_income, capital_employed)

    return metrics


def compute_profitability_series(
    inputs: list[ProfitabilityInput],
) -> list[ProfitabilityMetrics]:
    """Compute profitability metrics for multiple years, sorted by fiscal year."""
    return compute_series(compute_profitability, inputs)
