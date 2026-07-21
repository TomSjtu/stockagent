from __future__ import annotations

from stockagent.financials import ProfitabilityMetrics
from stockagent.fundamentals._utils import compute_series, safe_divide
from stockagent.fundamentals.inputs import ProfitabilityInput


def compute_profitability(fi: ProfitabilityInput) -> ProfitabilityMetrics:
    """Compute all profitability ratios from a single year's financial data."""
    metrics = ProfitabilityMetrics(fiscal_year=fi.fiscal_year)

    # 用 gross_profit、operating_income 和 net_income 分别除以 revenue，写入三项利润率
    metrics.gross_margin = safe_divide(fi.gross_profit, fi.revenue)
    metrics.operating_margin = safe_divide(fi.operating_income, fi.revenue)
    metrics.net_margin = safe_divide(fi.net_income, fi.revenue)

    # 用 rd_expense 和 sga_expense 分别除以 revenue，写入两项费用率
    metrics.rd_ratio = safe_divide(fi.rd_expense, fi.revenue)
    metrics.sga_ratio = safe_divide(fi.sga_expense, fi.revenue)

    # 计算 total_assets - current_liabilities 作为 capital_employed，再写入 ROA、ROE 和 ROCE
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
