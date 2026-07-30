from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TypeVar

from pydantic import BaseModel

from stockagent.agents.errors import AgentOutputError
from stockagent.agents.state import (
    Evidence,
    FundamentalsOutput,
    IndustryOutput,
    RiskOutput,
    SynthesisOutput,
    ValuationOutput,
)
from stockagent.financials import SecFilingReference
from stockagent.report.citations import render_citations
from stockagent.report.composer import ReportComposer, ReportContent
from stockagent.report.evidence import EvidenceBundle


@dataclass(frozen=True)
class GeneratedReport:
    """Rendered Markdown and the auditable evidence bundle from one analysis run."""

    # 已将内部证据标记渲染为脚注的最终报告正文
    markdown: str
    # 与 markdown 来自同一 final state 的证据、市场输入和 filing 元数据
    evidence_bundle: EvidenceBundle


StateOutputT = TypeVar("StateOutputT", bound=BaseModel)


def deliver_report(
    state: Mapping[str, object],
    report_date: date | None = None,
) -> GeneratedReport:
    """Construct one report and its matched evidence bundle from final graph state."""
    industry = _state_output(state, "industry", IndustryOutput)
    fundamentals = _state_output(state, "fundamentals", FundamentalsOutput)
    valuation = _state_output(state, "valuation", ValuationOutput)
    risk = _state_output(state, "risk", RiskOutput)
    synthesis = _state_output(state, "synthesis", SynthesisOutput)
    ticker = state.get("ticker")
    if not isinstance(ticker, str):
        raise AgentOutputError("analysis graph result is missing ticker")
    markdown = ReportComposer().compose(
        ReportContent(
            ticker=ticker,
            report_date=report_date or date.today(),
            summary=synthesis.summary,
            industry_analysis=industry.narrative,
            fundamentals_analysis=fundamentals.narrative,
            valuation_analysis=valuation.narrative,
            risk_assessment=risk.narrative,
            investment_recommendation=synthesis.investment_recommendation,
            annual_financials=fundamentals.annual_financials,
            financial_filings=fundamentals.financial_filings,
        )
    )
    evidence = _collect_evidence(industry, fundamentals, valuation, risk)
    citation_result = render_citations(markdown, evidence)
    return GeneratedReport(
        markdown=citation_result.markdown,
        evidence_bundle=EvidenceBundle(
            evidence=evidence,
            cited_evidence_ids=citation_result.cited_evidence_ids,
            market_inputs=valuation.market_inputs,
            financial_filings=fundamentals.financial_filings,
        ),
    )


def _collect_evidence(
    industry: IndustryOutput,
    fundamentals: FundamentalsOutput,
    valuation: ValuationOutput,
    risk: RiskOutput,
) -> list[Evidence]:
    """Collect web and filing evidence in the report's stable selection order."""
    return [
        *industry.evidence,
        *valuation.evidence,
        *risk.evidence,
        *[_filing_evidence(filing) for filing in fundamentals.financial_filings],
    ]


def _state_output(
    state: Mapping[str, object],
    name: str,
    output_type: type[StateOutputT],
) -> StateOutputT:
    """Return a typed required state output or fail at the graph boundary."""
    output = state.get(name)
    if not isinstance(output, output_type):
        raise AgentOutputError(f"analysis graph result is missing {name}")
    return output


def _filing_evidence(filing: SecFilingReference) -> Evidence:
    """Represent one deterministic annual filing as report evidence."""
    return Evidence(
        id=f"sec-{filing.fiscal_year}",
        kind="sec_filing",
        title=(
            f"SEC {filing.form}｜截至 {filing.period_end.isoformat()}｜"
            f"Filed {filing.filed_at.isoformat()}"
        ),
        url=filing.url,
        publisher="SEC",
        published_date=filing.filed_at,
        source_agent="fundamentals_analyst",
    )
