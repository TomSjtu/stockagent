from __future__ import annotations

from stockagent.financials import FinancialHealthMetrics, FinancialRecord
from stockagent.fundamentals._utils import compute_series, safe_divide


def compute_financial_health(record: FinancialRecord) -> FinancialHealthMetrics:
    """Compute financial health ratios from a standardized annual record."""
    metrics = FinancialHealthMetrics(fiscal_year=record.fiscal_year)

    # 将记录字段两两传给 safe_divide，依次写入五个财务健康比率
    metrics.equity_ratio = safe_divide(record.shareholders_equity, record.total_assets)
    metrics.liabilities_to_assets = safe_divide(
        record.total_liabilities,
        record.total_assets,
    )
    metrics.current_ratio = safe_divide(
        record.current_assets,
        record.current_liabilities,
    )
    metrics.cash_ratio = safe_divide(
        record.cash_and_equivalents,
        record.current_liabilities,
    )
    metrics.operating_cash_flow_to_total_liabilities = safe_divide(
        record.operating_cash_flow,
        record.total_liabilities,
    )

    return metrics


def compute_financial_health_series(
    records: list[FinancialRecord],
) -> list[FinancialHealthMetrics]:
    """Compute financial health metrics for multiple years, sorted by fiscal year."""
    return compute_series(compute_financial_health, records)
