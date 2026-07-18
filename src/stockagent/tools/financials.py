from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from stockagent import api


def fetch_company_financials(ticker: str, years: int = 3) -> str:
    """Fetch annual financial data for a company as JSON."""
    records = api.fetch_financials(ticker, years)
    return _to_json(
        {
            "ticker": ticker.upper(),
            "years": years,
            "records": records,
        }
    )


def compute_profitability_metrics(ticker: str, years: int = 3) -> str:
    """Compute profitability metrics such as margins, ROA, ROE, and ROCE."""
    records = api.fetch_financials(ticker, years)
    return _metric_payload(
        ticker,
        years,
        "profitability",
        api.compute_profitability(records),
    )


def compute_growth_metrics(ticker: str, years: int = 3) -> str:
    """Compute revenue, net-income, and free-cash-flow growth metrics."""
    records = api.fetch_financials(ticker, years)
    return _metric_payload(ticker, years, "growth", api.compute_growth(records))


def compute_cash_flow_metrics(ticker: str, years: int = 3) -> str:
    """Compute cash-flow metrics including free cash flow."""
    records = api.fetch_financials(ticker, years)
    return _metric_payload(
        ticker,
        years,
        "cash_flow",
        api.compute_cash_flow(records),
    )


def compute_financial_health_metrics(ticker: str, years: int = 3) -> str:
    """Compute leverage, liquidity, and balance-sheet health metrics."""
    records = api.fetch_financials(ticker, years)
    return _metric_payload(
        ticker,
        years,
        "financial_health",
        api.compute_financial_health(records),
    )


def compute_valuation_metrics(
    ticker: str,
    price: float | None = None,
    market_cap: float | None = None,
    years: int = 3,
) -> str:
    """Compute trailing PE/PB/PS from market inputs and latest financials."""
    records = api.fetch_financials(ticker, years)
    metrics = api.compute_valuation(records, price, market_cap)
    return _to_json(
        {
            "ticker": ticker.upper(),
            "years": years,
            "fiscal_year": metrics.fiscal_year,
            "valuation": metrics,
            "market_inputs": {
                "price": price,
                "market_cap": market_cap,
            },
            "unavailable": _valuation_unavailable_reasons(metrics),
        }
    )


def get_fundamentals_analysis(ticker: str, years: int = 3) -> str:
    """Fetch records and compute all deterministic financial metrics."""
    result = api.analyze(ticker, years)
    return _to_json(result)


def _metric_payload(
    ticker: str,
    years: int,
    metric_name: str,
    metrics: dict[int, Any],
) -> str:
    return _to_json(
        {
            "ticker": ticker.upper(),
            "years": years,
            metric_name: metrics,
        }
    )


def _to_json(value: Any) -> str:
    return json.dumps(
        _serialize(value),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _valuation_unavailable_reasons(metrics: Any) -> dict[str, str]:
    reasons = {}
    if metrics.pe_ratio is None:
        reasons["pe_ratio"] = (
            "missing positive price/eps_diluted or positive market_cap/net_income"
        )
    if metrics.pb_ratio is None:
        reasons["pb_ratio"] = "missing positive market_cap/shareholders_equity"
    if metrics.ps_ratio is None:
        reasons["ps_ratio"] = "missing positive market_cap/revenue"
    return reasons


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return _serialize(asdict(value))
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value
