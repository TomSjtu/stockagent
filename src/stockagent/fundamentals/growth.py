from __future__ import annotations

from stockagent.financials.models import GrowthMetrics
from stockagent.fundamentals.inputs import GrowthInput


def _safe_growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous


def _safe_cagr(
    current: float | None,
    beginning: float | None,
    periods: int,
) -> float | None:
    if current is None or beginning is None or beginning <= 0 or current < 0:
        return None
    if periods <= 0:
        return None
    return (current / beginning) ** (1 / periods) - 1


def _free_cash_flow(gi: GrowthInput) -> float | None:
    if gi.operating_cash_flow is None or gi.capex is None:
        return None
    return gi.operating_cash_flow - gi.capex


def compute_growth_series(inputs: list[GrowthInput]) -> list[GrowthMetrics]:
    """Compute YoY growth and CAGR metrics for multiple years."""
    sorted_inputs = sorted(inputs, key=lambda item: item.fiscal_year)
    if not sorted_inputs:
        return []

    first = sorted_inputs[0]
    first_free_cash_flow = _free_cash_flow(first)
    metrics: list[GrowthMetrics] = []

    previous: GrowthInput | None = None
    for current in sorted_inputs:
        periods = current.fiscal_year - first.fiscal_year
        current_free_cash_flow = _free_cash_flow(current)
        previous_free_cash_flow = (
            _free_cash_flow(previous) if previous is not None else None
        )

        metrics.append(
            GrowthMetrics(
                fiscal_year=current.fiscal_year,
                revenue_growth=_safe_growth(
                    current.revenue,
                    previous.revenue if previous is not None else None,
                ),
                net_income_growth=_safe_growth(
                    current.net_income,
                    previous.net_income if previous is not None else None,
                ),
                free_cash_flow_growth=_safe_growth(
                    current_free_cash_flow,
                    previous_free_cash_flow,
                ),
                revenue_cagr=_safe_cagr(current.revenue, first.revenue, periods),
                net_income_cagr=_safe_cagr(
                    current.net_income,
                    first.net_income,
                    periods,
                ),
                free_cash_flow_cagr=_safe_cagr(
                    current_free_cash_flow,
                    first_free_cash_flow,
                    periods,
                ),
            )
        )
        previous = current

    return metrics
