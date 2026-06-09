from __future__ import annotations

from dataclasses import dataclass

from src.data.schemas import FundamentalInput


@dataclass(slots=True)
class ProfitabilityMetrics:
    """Computed profitability ratios for one fiscal year."""

    fiscal_year: int
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    roa: float | None = None
    roe: float | None = None
    roce: float | None = None
    rd_ratio: float | None = None
    sga_ratio: float | None = None


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def compute_profitability(fi: FundamentalInput) -> ProfitabilityMetrics:
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
    fundamentals: list[FundamentalInput],
) -> list[ProfitabilityMetrics]:
    """Compute profitability metrics for multiple years, sorted by fiscal year."""
    return sorted(
        [compute_profitability(fi) for fi in fundamentals],
        key=lambda m: m.fiscal_year,
    )
