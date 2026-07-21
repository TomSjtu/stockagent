from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, Field, model_validator

from stockagent.agents.state import Evidence, MarketInputs
from stockagent.financials import SecFilingReference


class EvidenceBundle(BaseModel):
    """The selected sources and inputs needed to audit one report."""

    # 本次报告收集的网页 Evidence 与 SEC filing Evidence 列表
    evidence: list[Evidence] = Field(default_factory=list)
    # Markdown 实际脚注使用的 Evidence.id 列表
    cited_evidence_ids: list[str] = Field(default_factory=list)
    # valuation 工具实际使用的价格、市值、币种、日期和证据 ID
    market_inputs: MarketInputs = Field(default_factory=MarketInputs)
    # 财务记录关联的年度 SEC filing 元数据列表
    financial_filings: list[SecFilingReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_cited_evidence_ids(self) -> Self:
        """Enforce that every rendered citation refers to exactly one selected source."""
        evidence_ids = [item.id for item in self.evidence]
        selected_evidence_ids = set(evidence_ids)
        if len(evidence_ids) != len(selected_evidence_ids):
            raise ValueError("evidence IDs must be unique in a report evidence bundle")
        if len(self.cited_evidence_ids) != len(set(self.cited_evidence_ids)):
            raise ValueError("cited evidence IDs must be unique")
        unknown_ids = set(self.cited_evidence_ids) - selected_evidence_ids
        if unknown_ids:
            raise ValueError("cited evidence IDs must be selected evidence")
        return self


class SourcesManifest(BaseModel):
    """The JSON sidecar contract for one generated report."""

    # 生成本报告的股票代码
    ticker: str
    # 报告及同名审计文件使用的日期
    report_date: date
    # 本次运行中所有被 Agent 选取的证据
    evidence: list[Evidence]
    # 最终 Markdown 实际引用的证据 ID
    cited_evidence_ids: list[str]
    # 实际传入估值计算的市场输入
    market_inputs: MarketInputs
    # 本次财务窗口中各年度的 SEC filing 元数据
    financial_filings: list[SecFilingReference]


def serialize_sources(
    *,
    ticker: str,
    report_date: date,
    evidence_bundle: EvidenceBundle,
) -> str:
    """Serialize a report's audit sidecar without inventing missing values."""
    # 用大写 ticker、传入日期和 evidence_bundle 字段创建 SourcesManifest，再序列化为缩进 JSON
    manifest = SourcesManifest(
        ticker=ticker.upper(),
        report_date=report_date,
        **evidence_bundle.model_dump(),
    )
    return f"{manifest.model_dump_json(indent=2)}\n"
