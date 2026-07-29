from __future__ import annotations

import json as _json
import math as _math
from collections.abc import Mapping as _Mapping

from pydantic import ValidationError as _ValidationError

from stockagent.agents.errors import AgentOutputError as _AgentOutputError
from stockagent.agents.state import (
    FundamentalsAgentOutput as _FundamentalsAgentOutput,
    FundamentalsOutput as _FundamentalsOutput,
    ValuationAgentOutput as _ValuationAgentOutput,
    ValuationOutput as _ValuationOutput,
)
from stockagent.financials import SecFilingReference as _SecFilingReference
from stockagent.report.composer import (
    AnnualFinancialSnapshot as _AnnualFinancialSnapshot,
)

__all__ = ["apply_fundamentals_facts", "apply_valuation_facts"]

_FUNDAMENTALS_TOOL = "get_fundamentals_analysis"
_VALUATION_TOOL = "compute_valuation_metrics"


def apply_fundamentals_facts(
    output: _FundamentalsAgentOutput,
    tool_content: str,
    expected_ticker: str,
    expected_years: int,
) -> _FundamentalsOutput:
    """Return a new fundamentals output populated from deterministic tool facts."""
    # 先锁定本次分析的 ticker 和财年窗口，避免工具响应污染其他公司的报告。
    expected_symbol, years = _validate_expected_context(
        expected_ticker,
        expected_years,
        tool_name=_FUNDAMENTALS_TOOL,
    )
    payload = _parse_tool_object(tool_content, tool_name=_FUNDAMENTALS_TOOL)
    _validate_ticker(payload, expected_symbol, tool_name=_FUNDAMENTALS_TOOL)

    # 年度快照和指标按同一 fiscal_year 配对，后续统一转换为报告层模型。
    records = payload.get("records")
    if not isinstance(records, list):
        raise _AgentOutputError(
            f"{_FUNDAMENTALS_TOOL} returned invalid records"
        )
    if len(records) != years:
        raise _AgentOutputError(
            f"{_FUNDAMENTALS_TOOL} returned mismatched years"
        )

    snapshots: list[_AnnualFinancialSnapshot] = []
    filings: list[_SecFilingReference] = []
    fiscal_years: list[int] = []

    for record in records:
        if not isinstance(record, _Mapping):
            raise _AgentOutputError(
                f"{_FUNDAMENTALS_TOOL} returned invalid record"
            )

        fiscal_year = _fiscal_year(
            record,
            source="record",
            tool_name=_FUNDAMENTALS_TOOL,
        )
        profitability = _metrics_for_fiscal_year(
            payload,
            "profitability",
            fiscal_year,
        )
        cash_flow = _metrics_for_fiscal_year(
            payload,
            "cash_flow",
            fiscal_year,
        )
        growth = _metrics_for_fiscal_year(
            payload,
            "growth",
            fiscal_year,
        )

        snapshots.append(
            _AnnualFinancialSnapshot(
                fiscal_year=fiscal_year,
                revenue=_nullable_number(
                    record,
                    "revenue",
                    source="record",
                    tool_name=_FUNDAMENTALS_TOOL,
                ),
                net_income=_nullable_number(
                    record,
                    "net_income",
                    source="record",
                    tool_name=_FUNDAMENTALS_TOOL,
                ),
                operating_cash_flow=_nullable_number(
                    record,
                    "operating_cash_flow",
                    source="record",
                    tool_name=_FUNDAMENTALS_TOOL,
                ),
                capex=_nullable_number(
                    record,
                    "capex",
                    source="record",
                    tool_name=_FUNDAMENTALS_TOOL,
                ),
                free_cash_flow=_nullable_number(
                    cash_flow,
                    "free_cash_flow",
                    source="cash_flow metrics",
                    tool_name=_FUNDAMENTALS_TOOL,
                ),
                gross_margin=_nullable_number(
                    profitability,
                    "gross_margin",
                    source="profitability metrics",
                    tool_name=_FUNDAMENTALS_TOOL,
                ),
                net_margin=_nullable_number(
                    profitability,
                    "net_margin",
                    source="profitability metrics",
                    tool_name=_FUNDAMENTALS_TOOL,
                ),
                revenue_growth=_nullable_number(
                    growth,
                    "revenue_growth",
                    source="growth metrics",
                    tool_name=_FUNDAMENTALS_TOOL,
                ),
            )
        )
        fiscal_years.append(fiscal_year)

        # filing 可以缺失，但如果存在必须与该年度快照对应，避免错误引用来源。
        if "filing" not in record:
            raise _AgentOutputError(
                f"{_FUNDAMENTALS_TOOL} omitted filing from record"
            )
        filing_payload = record["filing"]
        if filing_payload is None:
            continue
        if not isinstance(filing_payload, _Mapping):
            raise _AgentOutputError(
                f"{_FUNDAMENTALS_TOOL} returned invalid filing"
            )
        try:
            filing = _SecFilingReference.model_validate(filing_payload)
        except _ValidationError as exc:
            raise _AgentOutputError(
                f"{_FUNDAMENTALS_TOOL} returned invalid filing"
            ) from exc
        if filing.fiscal_year != fiscal_year:
            raise _AgentOutputError(
                f"{_FUNDAMENTALS_TOOL} returned mismatched filing"
            )
        filings.append(filing)

    if len(set(fiscal_years)) != years:
        raise _AgentOutputError(
            f"{_FUNDAMENTALS_TOOL} returned invalid fiscal years"
        )
    if fiscal_years:
        # 既拒绝重复年度，也拒绝跨过缺失财年的数据窗口。
        ascending_years = sorted(fiscal_years)
        if ascending_years != list(
            range(ascending_years[0], ascending_years[-1] + 1)
        ):
            raise _AgentOutputError(
                f"{_FUNDAMENTALS_TOOL} returned non-contiguous fiscal years"
            )

    # 工具返回顺序不作为报告顺序，按财年排序保证输出稳定、可复现。
    snapshots.sort(key=lambda snapshot: snapshot.fiscal_year)
    filings.sort(key=lambda filing: filing.fiscal_year)
    try:
        return _FundamentalsOutput(
            narrative=output.narrative,
            concerns=output.concerns,
            annual_financials=snapshots,
            financial_filings=filings,
        )
    except _ValidationError as exc:
        raise _AgentOutputError(
            f"{_FUNDAMENTALS_TOOL} produced an invalid fundamentals output"
        ) from exc


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


def _metrics_for_fiscal_year(
    payload: _Mapping[str, object],
    metric_name: str,
    fiscal_year: int,
) -> _Mapping[str, object]:
    # 指标以字符串形式按年度索引，且内部 fiscal_year 仍需再次核对。
    metrics_by_year = payload.get(metric_name)
    if not isinstance(metrics_by_year, _Mapping):
        raise _AgentOutputError(
            f"{_FUNDAMENTALS_TOOL} returned invalid {metric_name} metrics"
        )
    metrics = metrics_by_year.get(str(fiscal_year))
    if not isinstance(metrics, _Mapping):
        raise _AgentOutputError(
            f"{_FUNDAMENTALS_TOOL} omitted {metric_name} metrics for {fiscal_year}"
        )
    if (
        _fiscal_year(
            metrics,
            source=f"{metric_name} metrics",
            tool_name=_FUNDAMENTALS_TOOL,
        )
        != fiscal_year
    ):
        raise _AgentOutputError(
            f"{_FUNDAMENTALS_TOOL} returned mismatched {metric_name} metrics"
        )
    return metrics


def _fiscal_year(
    payload: _Mapping[str, object],
    *,
    source: str,
    tool_name: str,
) -> int:
    fiscal_year = payload.get("fiscal_year")
    if isinstance(fiscal_year, bool) or not isinstance(fiscal_year, int):
        raise _AgentOutputError(f"{tool_name} returned invalid {source}")
    return fiscal_year


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
