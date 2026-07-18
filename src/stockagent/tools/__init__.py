"""Agent tool adapters."""

from stockagent.tools.financials import (
    compute_cash_flow_metrics,
    compute_financial_health_metrics,
    compute_growth_metrics,
    compute_profitability_metrics,
    compute_valuation_metrics,
    fetch_company_financials,
    get_fundamentals_analysis,
)
from stockagent.tools.search import web_search

__all__ = [
    "compute_cash_flow_metrics",
    "compute_financial_health_metrics",
    "compute_growth_metrics",
    "compute_profitability_metrics",
    "compute_valuation_metrics",
    "fetch_company_financials",
    "get_fundamentals_analysis",
    "web_search",
]
