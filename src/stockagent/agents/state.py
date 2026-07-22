from datetime import date, datetime
from typing import Literal, NotRequired, Self, TypedDict

from pydantic import BaseModel, Field, model_validator

from stockagent.financials import SecFilingReference
from stockagent.report.composer import AnnualFinancialSnapshot


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

    # Agent 选入输出的 Evidence 列表
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_evidence_ids(self) -> Self:
        """Reject duplicate IDs before evidence is merged into the report bundle."""
        ids = [item.id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence IDs must be unique within an agent output")
        return self


class IndustryOutput(EvidenceOutput):
    """Structured industry analysis written by the industry agent."""

    # 行业 Agent 生成的中文 Markdown 片段，可包含 [industry-*] 证据标记
    narrative: str


class FundamentalsOutput(BaseModel):
    """Structured fundamentals analysis and its deterministic filing references."""

    # 基本面 Agent 生成的中文 Markdown 片段，可包含 [sec-*] 证据标记
    narrative: str
    # Agent 输出的指标名称到数值的映射，用于报告中的重点展示
    key_metrics: dict[str, float | None]
    # Agent 输出的基本面关注点列表
    concerns: list[str]
    # 从 get_fundamentals_analysis 工具 records 提取的年度 SEC filing 列表
    financial_filings: list[SecFilingReference] = Field(default_factory=list)
    # 从同一确定性工具结果提取的年度财务快照，供报告编排器直接渲染
    annual_financials: list[AnnualFinancialSnapshot] = Field(default_factory=list)


class ValuationOutput(EvidenceOutput):
    """Structured valuation analysis with deterministic metric fields."""

    # 估值 Agent 生成的中文 Markdown 片段，可包含 [valuation-*] 证据标记
    narrative: str
    # compute_valuation_metrics 返回的市盈率，工具不可计算时为 None
    pe_ratio: float | None
    # compute_valuation_metrics 返回的市净率，工具不可计算时为 None
    pb_ratio: float | None
    # compute_valuation_metrics 返回的市销率，工具不可计算时为 None
    ps_ratio: float | None
    # 传给 compute_valuation_metrics 的市场输入及其 Evidence ID
    market_inputs: MarketInputs = Field(default_factory=MarketInputs)


class RiskOutput(EvidenceOutput):
    """Structured risk assessment written after upstream analysis is available."""

    # 风险 Agent 生成的中文 Markdown 片段，可包含 [risk-*] 证据标记
    narrative: str
    # 风险 Agent 在 "低"、"中"、"高" 中选择的总体评级
    overall_rating: Literal["低", "中", "高"]
    # 风险 Agent 输出的具体风险条目
    key_risks: list[str]


class AnalysisState(TypedDict):
    """Typed local outputs exchanged between LangGraph nodes in one run."""

    # graph.invoke 初始 state 中传入的股票代码
    ticker: str
    # graph.invoke 初始 state 中传入的财年数
    years: int
    # industry 节点写入的 IndustryOutput
    industry: NotRequired[IndustryOutput]
    # fundamentals 节点写入的 FundamentalsOutput
    fundamentals: NotRequired[FundamentalsOutput]
    # valuation 节点写入的 ValuationOutput
    valuation: NotRequired[ValuationOutput]
    # risk 节点写入的 RiskOutput
    risk: NotRequired[RiskOutput]
    # synthesize 节点写入的、已替换脚注标记的完整 Markdown 报告
    final_report: NotRequired[str]
    # synthesize 节点写入的证据 ID 列表，顺序与 Markdown 脚注编号一致
    cited_evidence_ids: NotRequired[list[str]]
