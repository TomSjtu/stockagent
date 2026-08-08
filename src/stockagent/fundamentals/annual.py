from __future__ import annotations

from stockagent.financials import (
    CashFlowMetrics,
    FinancialHealthMetrics,
    FinancialRecord,
    ProfitabilityMetrics,
)


def free_cash_flow(
    operating_cash_flow: float | None,
    capex: float | None,
) -> float | None:
    """Compute free cash flow while preserving missing-input semantics."""
    if operating_cash_flow is None or capex is None:
        return None
    return operating_cash_flow - capex


def _safe_divide(
    numerator: float | None,
    denominator: float | None,
) -> float | None:
    """Divide only when both annual inputs are present and the denominator is nonzero."""
    # 任一操作数为 None 或分母为零时返回 None；否则返回两个 float 的商
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def compute_profitability(record: FinancialRecord) -> ProfitabilityMetrics:
    """Compute all profitability ratios from a standardized annual record."""
    metrics = ProfitabilityMetrics(fiscal_year=record.fiscal_year)

    # 用 gross_profit、operating_income 和 net_income 分别除以 revenue，写入三项利润率
    metrics.gross_margin = _safe_divide(record.gross_profit, record.revenue)
    metrics.operating_margin = _safe_divide(record.operating_income, record.revenue)
    metrics.net_margin = _safe_divide(record.net_income, record.revenue)

    # 用 rd_expense 和 sga_expense 分别除以 revenue，写入两项费用率
    metrics.rd_ratio = _safe_divide(record.rd_expense, record.revenue)
    metrics.sga_ratio = _safe_divide(record.sga_expense, record.revenue)

    # 计算 total_assets - current_liabilities 作为 capital_employed，再写入 ROA、ROE 和 ROCE
    metrics.roa = _safe_divide(record.net_income, record.total_assets)
    metrics.roe = _safe_divide(record.net_income, record.shareholders_equity)
    capital_employed = (
        record.total_assets - record.current_liabilities
        if record.total_assets is not None and record.current_liabilities is not None
        else None
    )
    metrics.roce = _safe_divide(record.operating_income, capital_employed)

    return metrics


def compute_cash_flow(record: FinancialRecord) -> CashFlowMetrics:
    """Compute cash flow metrics from a standardized annual record."""
    return CashFlowMetrics(
        fiscal_year=record.fiscal_year,
        free_cash_flow=free_cash_flow(record.operating_cash_flow, record.capex),
    )


def compute_financial_health(record: FinancialRecord) -> FinancialHealthMetrics:
    """Compute financial health ratios from a standardized annual record."""
    metrics = FinancialHealthMetrics(fiscal_year=record.fiscal_year)

    # 将记录字段两两传给 _safe_divide，依次写入五个财务健康比率
    metrics.equity_ratio = _safe_divide(
        record.shareholders_equity,
        record.total_assets,
    )
    metrics.liabilities_to_assets = _safe_divide(
        record.total_liabilities,
        record.total_assets,
    )
    metrics.current_ratio = _safe_divide(
        record.current_assets,
        record.current_liabilities,
    )
    metrics.cash_ratio = _safe_divide(
        record.cash_and_equivalents,
        record.current_liabilities,
    )
    metrics.operating_cash_flow_to_total_liabilities = _safe_divide(
        record.operating_cash_flow,
        record.total_liabilities,
    )

    return metrics
