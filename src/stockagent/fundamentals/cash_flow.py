from __future__ import annotations

from stockagent.financials.models import CashFlowMetrics
from stockagent.fundamentals.inputs import CashFlowInput


def compute_cash_flow(fi: CashFlowInput) -> CashFlowMetrics:
    """Compute cash flow metrics from a single year's cash flow input."""
    free_cash_flow = (
        fi.operating_cash_flow - fi.capex
        if fi.operating_cash_flow is not None and fi.capex is not None
        else None
    )

    return CashFlowMetrics(
        fiscal_year=fi.fiscal_year,
        free_cash_flow=free_cash_flow,
    )


def compute_cash_flow_series(inputs: list[CashFlowInput]) -> list[CashFlowMetrics]:
    """Compute cash flow metrics for multiple years, sorted by fiscal year."""
    return sorted(
        [compute_cash_flow(fi) for fi in inputs],
        key=lambda metrics: metrics.fiscal_year,
    )
