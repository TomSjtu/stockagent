from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from pydantic import BaseModel

from stockagent.fundamentals import analysis


def compute_valuation_metrics(
    ticker: str,
    price: float | None = None,
    market_cap: float | None = None,
    years: int = 3,
) -> str:
    """Compute trailing PE/PB/PS from market inputs and latest financials as JSON."""
    result = analysis.analyze_fundamentals(ticker, years)
    metrics = analysis.analyze_valuation(
        result.annual_fundamentals,
        price,
        market_cap,
    )
    return _to_json(
        {
            "ticker": result.ticker,
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
    result = analysis.analyze_fundamentals(ticker, years)
    return _to_json(_fundamentals_tool_payload(result))


def _fundamentals_tool_payload(
    result: analysis.FundamentalsAnalysis,
) -> dict[str, Any]:
    """Adapt annual fundamentals to the established LLM tool contract."""
    return {
        "ticker": result.ticker,
        "records": [item.record for item in result.annual_fundamentals],
        "profitability": {
            item.fiscal_year: item.profitability
            for item in result.annual_fundamentals
        },
        "cash_flow": {
            item.fiscal_year: item.cash_flow
            for item in result.annual_fundamentals
        },
        "financial_health": {
            item.fiscal_year: item.financial_health
            for item in result.annual_fundamentals
        },
        "growth": {
            item.fiscal_year: item.growth
            for item in result.annual_fundamentals
        },
    }


def _to_json(value: Any) -> str:
    """Serialize domain values for an LLM tool without changing their semantics."""
    return json.dumps(
        _serialize(value),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _valuation_unavailable_reasons(metrics: Any) -> dict[str, str]:
    """Describe unavailable valuation ratios without substituting numeric defaults."""
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
    """Recursively convert Pydantic and dataclass values to JSON-compatible data."""
    if isinstance(value, BaseModel):
        return _serialize(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _serialize(asdict(value))
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value
