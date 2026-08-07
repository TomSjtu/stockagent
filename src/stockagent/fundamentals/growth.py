from __future__ import annotations

from stockagent.financials import FinancialRecord, GrowthMetrics
from stockagent.fundamentals.cash_flow import free_cash_flow


def _safe_growth(current: float | None, previous: float | None) -> float | None:
    """Return year-over-year growth only for a usable prior-year base."""
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous


def _safe_cagr(
    current: float | None,
    beginning: float | None,
    periods: int,
) -> float | None:
    """Return CAGR only when its values and interval satisfy the formula."""
    # 起点小于等于零、终点为负或期间非正数时返回 None；否则计算 CAGR
    if current is None or beginning is None or beginning <= 0 or current < 0:
        return None
    if periods <= 0:
        return None
    return (current / beginning) ** (1 / periods) - 1


def compute_growth_series(records: list[FinancialRecord]) -> list[GrowthMetrics]:
    """Compute YoY growth and CAGR metrics for multiple years."""
    # 按 fiscal_year 排序；首项作为 CAGR 起点，前一项作为同比基数
    sorted_records = sorted(records, key=lambda item: item.fiscal_year)
    if not sorted_records:
        return []

    first = sorted_records[0]
    first_free_cash_flow = free_cash_flow(first.operating_cash_flow, first.capex)
    metrics: list[GrowthMetrics] = []

    previous: FinancialRecord | None = None
    for current in sorted_records:
        periods = current.fiscal_year - first.fiscal_year
        current_free_cash_flow = free_cash_flow(
            current.operating_cash_flow,
            current.capex,
        )
        previous_free_cash_flow = (
            free_cash_flow(previous.operating_cash_flow, previous.capex)
            if previous is not None
            else None
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
