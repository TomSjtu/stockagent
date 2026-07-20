from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, Field, model_validator

from stockagent.agents.state import Evidence, MarketInputs
from stockagent.financials import SecFilingReference


class EvidenceBundle(BaseModel):
    """The selected sources and inputs needed to audit one report."""

    evidence: list[Evidence] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)
    market_inputs: MarketInputs = Field(default_factory=MarketInputs)
    financial_filings: list[SecFilingReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_cited_evidence_ids(self) -> Self:
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

    ticker: str
    report_date: date
    evidence: list[Evidence]
    cited_evidence_ids: list[str]
    market_inputs: MarketInputs
    financial_filings: list[SecFilingReference]


def serialize_sources(
    *,
    ticker: str,
    report_date: date,
    evidence_bundle: EvidenceBundle,
) -> str:
    """Serialize a report's audit sidecar without inventing missing values."""
    manifest = SourcesManifest(
        ticker=ticker.upper(),
        report_date=report_date,
        **evidence_bundle.model_dump(),
    )
    return f"{manifest.model_dump_json(indent=2)}\n"
