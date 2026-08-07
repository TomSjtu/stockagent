from __future__ import annotations

from stockagent.financials import CashFlowMetrics, FinancialRecord
from stockagent.fundamentals._utils import compute_series


def free_cash_flow(
    operating_cash_flow: float | None,
    capex: float | None,
) -> float | None:
    """Compute free cash flow while preserving missing-input semantics."""
    if operating_cash_flow is None or capex is None:
        return None
    return operating_cash_flow - capex


def compute_cash_flow(record: FinancialRecord) -> CashFlowMetrics:
    """Compute cash flow metrics from a standardized annual record."""
    computed_free_cash_flow = free_cash_flow(
        record.operating_cash_flow,
        record.capex,
    )

    return CashFlowMetrics(
        fiscal_year=record.fiscal_year,
        free_cash_flow=computed_free_cash_flow,
    )


def compute_cash_flow_series(records: list[FinancialRecord]) -> list[CashFlowMetrics]:
    """Compute cash flow metrics for multiple years, sorted by fiscal year."""
    return compute_series(compute_cash_flow, records)
