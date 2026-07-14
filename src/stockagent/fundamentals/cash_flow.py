from __future__ import annotations

from stockagent.financials import CashFlowMetrics
from stockagent.fundamentals._utils import compute_free_cash_flow, compute_series
from stockagent.fundamentals.inputs import CashFlowInput


def compute_cash_flow(fi: CashFlowInput) -> CashFlowMetrics:
    """Compute cash flow metrics from a single year's cash flow input."""
    free_cash_flow = compute_free_cash_flow(fi.operating_cash_flow, fi.capex)

    return CashFlowMetrics(
        fiscal_year=fi.fiscal_year,
        free_cash_flow=free_cash_flow,
    )


def compute_cash_flow_series(inputs: list[CashFlowInput]) -> list[CashFlowMetrics]:
    """Compute cash flow metrics for multiple years, sorted by fiscal year."""
    return compute_series(compute_cash_flow, inputs)
