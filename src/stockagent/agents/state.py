from datetime import date, datetime
from typing import Literal, NotRequired, Self, TypedDict

from pydantic import BaseModel, Field, model_validator

from stockagent.financials import SecFilingReference


class Evidence(BaseModel):
    """A source selected by an analysis agent for this report run."""

    id: str = Field(min_length=1)
    kind: Literal["web", "sec_filing"]
    title: str
    url: str
    publisher: str | None = None
    published_date: date | None = None
    excerpt: str | None = None
    source_agent: str


class MarketInputs(BaseModel):
    """Market data actually used to calculate the valuation metrics."""

    price: float | None = None
    market_cap: float | None = None
    currency: str | None = None
    as_of: date | datetime | None = None
    evidence_id: str | None = None


class EvidenceOutput(BaseModel):
    """Base contract for agent outputs that select web evidence."""

    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_evidence_ids(self) -> Self:
        ids = [item.id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence IDs must be unique within an agent output")
        return self


class IndustryOutput(EvidenceOutput):
    narrative: str


class FundamentalsOutput(BaseModel):
    narrative: str
    key_metrics: dict[str, float | None]
    concerns: list[str]
    financial_filings: list[SecFilingReference] = Field(default_factory=list)


class ValuationOutput(EvidenceOutput):
    narrative: str
    pe_ratio: float | None
    pb_ratio: float | None
    ps_ratio: float | None
    market_inputs: MarketInputs = Field(default_factory=MarketInputs)


class RiskOutput(EvidenceOutput):
    narrative: str
    overall_rating: Literal["低", "中", "高"]
    key_risks: list[str]


class AnalysisState(TypedDict):
    ticker: str
    years: int
    industry: NotRequired[IndustryOutput]
    fundamentals: NotRequired[FundamentalsOutput]
    valuation: NotRequired[ValuationOutput]
    risk: NotRequired[RiskOutput]
    final_report: NotRequired[str]
