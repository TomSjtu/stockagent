from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel


class IndustryOutput(BaseModel):
    narrative: str
    sources: list[str]


class FundamentalsOutput(BaseModel):
    narrative: str
    key_metrics: dict[str, float | None]
    concerns: list[str]


class ValuationOutput(BaseModel):
    narrative: str
    pe_ratio: float | None
    pb_ratio: float | None
    ps_ratio: float | None
    price_source: str | None


class RiskOutput(BaseModel):
    narrative: str
    overall_rating: Literal["低", "中", "高"]
    key_risks: list[str]
    sources: list[str]


class AnalysisState(TypedDict):
    ticker: str
    years: int
    industry: NotRequired[IndustryOutput]
    fundamentals: NotRequired[FundamentalsOutput]
    valuation: NotRequired[ValuationOutput]
    risk: NotRequired[RiskOutput]
    final_report: NotRequired[str]
