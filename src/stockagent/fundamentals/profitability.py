from __future__ import annotations

from stockagent.financials import FinancialRecord, ProfitabilityMetrics
from stockagent.fundamentals._utils import compute_series, safe_divide


def compute_profitability(record: FinancialRecord) -> ProfitabilityMetrics:
    """Compute all profitability ratios from a standardized annual record."""
    metrics = ProfitabilityMetrics(fiscal_year=record.fiscal_year)

    # 用 gross_profit、operating_income 和 net_income 分别除以 revenue，写入三项利润率
    metrics.gross_margin = safe_divide(record.gross_profit, record.revenue)
    metrics.operating_margin = safe_divide(record.operating_income, record.revenue)
    metrics.net_margin = safe_divide(record.net_income, record.revenue)

    # 用 rd_expense 和 sga_expense 分别除以 revenue，写入两项费用率
    metrics.rd_ratio = safe_divide(record.rd_expense, record.revenue)
    metrics.sga_ratio = safe_divide(record.sga_expense, record.revenue)

    # 计算 total_assets - current_liabilities 作为 capital_employed，再写入 ROA、ROE 和 ROCE
    metrics.roa = safe_divide(record.net_income, record.total_assets)
    metrics.roe = safe_divide(record.net_income, record.shareholders_equity)
    capital_employed = (
        record.total_assets - record.current_liabilities
        if record.total_assets is not None and record.current_liabilities is not None
        else None
    )
    metrics.roce = safe_divide(record.operating_income, capital_employed)

    return metrics


def compute_profitability_series(
    records: list[FinancialRecord],
) -> list[ProfitabilityMetrics]:
    """Compute profitability metrics for multiple years, sorted by fiscal year."""
    return compute_series(compute_profitability, records)
