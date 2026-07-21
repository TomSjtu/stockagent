from datetime import date, datetime
from typing import Literal, NotRequired, Self, TypedDict

from pydantic import BaseModel, Field, model_validator

from stockagent.financials import SecFilingReference


class Evidence(BaseModel):
    """A source selected by an analysis agent for this report run."""

    # 本次运行内稳定的证据 ID，供正文引用标记使用
    id: str = Field(min_length=1)
    # 区分网页搜索结果与 SEC filing 引用
    kind: Literal["web", "sec_filing"]
    # 便于读者识别来源的标题
    title: str
    # 来源的原始链接
    url: str
    # 可识别时记录发布机构
    publisher: str | None = None
    # 网页发布日期或 filing 提交日；来源未提供时为空
    published_date: date | None = None
    # 裁剪后的搜索摘要，不保存原始全文
    excerpt: str | None = None
    # 选取该来源的 Agent，便于审计
    source_agent: str


class MarketInputs(BaseModel):
    """Market data actually used to calculate the valuation metrics."""

    # 实际传入估值计算的股价
    price: float | None = None
    # 实际传入估值计算的总市值
    market_cap: float | None = None
    # 来源明确给出时的价格和市值币种
    currency: str | None = None
    # 来源明确给出时的交易日或时间点
    as_of: date | datetime | None = None
    # 支撑该组市场输入的网页证据 ID
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
    cited_evidence_ids: NotRequired[list[str]]
