from __future__ import annotations

from stockagent.financials.models import ProfitabilityMetrics
from stockagent.fundamentals.inputs import ProfitabilityInput


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def compute_profitability(fi: ProfitabilityInput) -> ProfitabilityMetrics:
    """Compute all profitability ratios from a single year's fundamental data."""
    metrics = ProfitabilityMetrics(fiscal_year=fi.fiscal_year)

    # Margins
    metrics.gross_margin = _safe_divide(fi.gross_profit, fi.revenue)
    metrics.operating_margin = _safe_divide(fi.operating_income, fi.revenue)
    metrics.net_margin = _safe_divide(fi.net_income, fi.revenue)

    # Expense ratios
    metrics.rd_ratio = _safe_divide(fi.rd_expense, fi.revenue)
    metrics.sga_ratio = _safe_divide(fi.sga_expense, fi.revenue)

    # Return on capital
    metrics.roa = _safe_divide(fi.net_income, fi.total_assets)
    metrics.roe = _safe_divide(fi.net_income, fi.shareholders_equity)
    capital_employed = (fi.total_assets - fi.current_liabilities
                        if fi.total_assets is not None and fi.current_liabilities is not None
                        else None)
    metrics.roce = _safe_divide(fi.operating_income, capital_employed)

    return metrics


def compute_profitability_series(
    inputs: list[ProfitabilityInput],
) -> list[ProfitabilityMetrics]:
    """Compute profitability metrics for multiple years, sorted by fiscal year."""
    return sorted(
        [compute_profitability(fi) for fi in inputs],
        key=lambda m: m.fiscal_year,
    )
