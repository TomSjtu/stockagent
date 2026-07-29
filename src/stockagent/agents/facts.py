from __future__ import annotations

import json as _json
import math as _math
from collections.abc import Mapping as _Mapping
from typing import TypedDict as _TypedDict

from pydantic import ValidationError as _ValidationError

from stockagent import api as _api
from stockagent.agents.errors import AgentOutputError as _AgentOutputError
from stockagent.agents.state import (
    ValuationAgentOutput as _ValuationAgentOutput,
)
from stockagent.agents.state import (
    ValuationOutput as _ValuationOutput,
)
from stockagent.financials import SecFilingReference as _SecFilingReference
from stockagent.report.composer import (
    AnnualFinancialSnapshot as _AnnualFinancialSnapshot,
)

__all__ = ["build_fundamentals_facts", "apply_valuation_facts"]

_VALUATION_TOOL = "compute_valuation_metrics"


class _FundamentalsFacts(_TypedDict):
    annual_financials: list[_AnnualFinancialSnapshot]
    financial_filings: list[_SecFilingReference]


def build_fundamentals_facts(
    ticker: str,
    years: int,
) -> _FundamentalsFacts:
    """Build report-facing fundamentals facts from the typed financial analysis."""
    analysis = _api.analyze(ticker, years)
    snapshots: list[_AnnualFinancialSnapshot] = []
    filings: list[_SecFilingReference] = []
    for record in sorted(analysis.records, key=lambda item: item.fiscal_year):
        fiscal_year = record.fiscal_year
        profitability = analysis.profitability[fiscal_year]
        cash_flow = analysis.cash_flow[fiscal_year]
        growth = analysis.growth[fiscal_year]

        snapshots.append(
            _AnnualFinancialSnapshot(
                fiscal_year=fiscal_year,
                revenue=record.revenue,
                net_income=record.net_income,
                operating_cash_flow=record.operating_cash_flow,
                capex=record.capex,
                free_cash_flow=cash_flow.free_cash_flow,
                gross_margin=profitability.gross_margin,
                net_margin=profitability.net_margin,
                revenue_growth=growth.revenue_growth,
            )
        )
        if record.filing is not None:
            filings.append(record.filing)

    return {
        "annual_financials": snapshots,
        "financial_filings": filings,
    }


def apply_valuation_facts(
    output: _ValuationAgentOutput,
    tool_content: str,
    expected_ticker: str,
    expected_years: int,
) -> _ValuationOutput:
    """Return a new valuation output with deterministic metrics and market inputs."""
    # 估值叙事仍来自模型，但 PE/PB/PS 及市场输入必须以工具结果为准。
    expected_symbol, years = _validate_expected_context(
        expected_ticker,
        expected_years,
        tool_name=_VALUATION_TOOL,
    )
    payload = _parse_tool_object(tool_content, tool_name=_VALUATION_TOOL)
    _validate_ticker(payload, expected_symbol, tool_name=_VALUATION_TOOL)

    payload_years = payload.get("years")
    if (
        isinstance(payload_years, bool)
        or not isinstance(payload_years, int)
        or payload_years != years
    ):
        raise _AgentOutputError(f"{_VALUATION_TOOL} returned mismatched years")

    valuation = payload.get("valuation")
    if not isinstance(valuation, _Mapping):
        raise _AgentOutputError(
            f"{_VALUATION_TOOL} returned invalid valuation data"
        )
    metrics = {
        name: _nullable_number(
            valuation,
            name,
            source="valuation data",
            tool_name=_VALUATION_TOOL,
        )
        for name in ("pe_ratio", "pb_ratio", "ps_ratio")
    }

    tool_market_inputs = payload.get("market_inputs")
    if not isinstance(tool_market_inputs, _Mapping):
        raise _AgentOutputError(
            f"{_VALUATION_TOOL} returned invalid market inputs"
        )
    market_inputs = {
        name: _nullable_number(
            tool_market_inputs,
            name,
            source="market inputs",
            tool_name=_VALUATION_TOOL,
        )
        for name in ("price", "market_cap")
    }

    try:
        return _ValuationOutput(
            narrative=output.narrative,
            evidence=output.evidence,
            pe_ratio=metrics["pe_ratio"],
            pb_ratio=metrics["pb_ratio"],
            ps_ratio=metrics["ps_ratio"],
            market_inputs={
                "price": market_inputs["price"],
                "market_cap": market_inputs["market_cap"],
                "currency": output.market_inputs.currency,
                "as_of": output.market_inputs.as_of,
                "evidence_id": output.market_inputs.evidence_id,
            },
        )
    except _ValidationError as exc:
        raise _AgentOutputError(
            f"{_VALUATION_TOOL} produced an invalid valuation output"
        ) from exc


def _validate_expected_context(
    expected_ticker: str,
    expected_years: int,
    *,
    tool_name: str,
) -> tuple[str, int]:
    # bool 是 int 的子类，必须显式排除，避免把 True 当作一年窗口。
    if not isinstance(expected_ticker, str):
        raise _AgentOutputError(f"{tool_name} received an invalid expected ticker")
    if (
        isinstance(expected_years, bool)
        or not isinstance(expected_years, int)
        or expected_years < 1
    ):
        raise _AgentOutputError(f"{tool_name} received invalid expected years")
    return expected_ticker.upper(), expected_years


def _parse_tool_object(
    tool_content: str,
    *,
    tool_name: str,
) -> _Mapping[str, object]:
    # 工具协议要求顶层 JSON 对象，后续字段校验才能保持明确的错误边界。
    if not isinstance(tool_content, str):
        raise _AgentOutputError(f"{tool_name} returned non-text JSON")
    try:
        payload = _json.loads(tool_content)
    except _json.JSONDecodeError as exc:
        raise _AgentOutputError(f"{tool_name} returned invalid JSON") from exc
    if not isinstance(payload, _Mapping):
        raise _AgentOutputError(f"{tool_name} returned a non-object payload")
    return payload


def _validate_ticker(
    payload: _Mapping[str, object],
    expected_ticker: str,
    *,
    tool_name: str,
) -> None:
    if payload.get("ticker") != expected_ticker:
        raise _AgentOutputError(f"{tool_name} returned a mismatched ticker")


def _nullable_number(
    payload: _Mapping[str, object],
    field_name: str,
    *,
    source: str,
    tool_name: str,
) -> float | None:
    # 缺失字段与显式 null 语义不同：前者表示协议错误，后者表示数据不可用。
    if field_name not in payload:
        raise _AgentOutputError(
            f"{tool_name} omitted {field_name} from {source}"
        )
    value = payload[field_name]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _AgentOutputError(
            f"{tool_name} returned invalid {field_name} in {source}"
        )
    try:
        normalized = float(value)
    except OverflowError as exc:
        raise _AgentOutputError(
            f"{tool_name} returned invalid {field_name} in {source}"
        ) from exc
    if not _math.isfinite(normalized):
        raise _AgentOutputError(
            f"{tool_name} returned invalid {field_name} in {source}"
        )
    return normalized
