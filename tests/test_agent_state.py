from __future__ import annotations

import unittest

from pydantic import ValidationError

from stockagent.agents.state import (
    AnalysisState,
    Evidence,
    FundamentalsAgentOutput,
    FundamentalsOutput,
    IndustryOutput,
    MarketInputs,
    RiskOutput,
    SynthesisOutput,
    ValuationAgentOutput,
    ValuationOutput,
)
from stockagent.financials import SecFilingReference


class AgentStateTest(unittest.TestCase):
    def test_agent_and_state_models_own_distinct_fields(self) -> None:
        fundamentals_agent = FundamentalsAgentOutput(
            narrative="基本面分析",
            concerns=[],
        )
        fundamentals = FundamentalsOutput(narrative="基本面分析", concerns=[])
        valuation_agent = ValuationAgentOutput(narrative="估值分析")
        valuation = ValuationOutput(narrative="估值分析")
        synthesis = SynthesisOutput(
            summary="摘要",
            investment_recommendation="投资建议",
        )

        self.assertEqual(
            set(type(fundamentals_agent).model_fields),
            {"narrative", "concerns"},
        )
        self.assertEqual(
            set(type(valuation_agent).model_fields),
            {"narrative", "evidence", "market_inputs"},
        )
        self.assertEqual(fundamentals.annual_financials, [])
        self.assertEqual(fundamentals.financial_filings, [])
        self.assertIsNone(valuation.pe_ratio)
        self.assertIsNone(valuation.pb_ratio)
        self.assertIsNone(valuation.ps_ratio)
        self.assertEqual(
            set(type(synthesis).model_fields),
            {"summary", "investment_recommendation"},
        )

    def test_valuation_agent_output_rejects_unknown_market_evidence_id(self) -> None:
        with self.assertRaises(ValidationError):
            ValuationAgentOutput(
                narrative="估值分析",
                evidence=[],
                market_inputs=MarketInputs(evidence_id="valuation-1"),
            )

    def test_outputs_accept_the_cross_agent_contract(self) -> None:
        industry = IndustryOutput(
            narrative="行业分析",
            evidence=[
                Evidence(
                    id="industry-1",
                    kind="web",
                    title="行业报告",
                    url="https://example.test/industry",
                    publisher="Example Research",
                    published_date="2026-07-01",
                    excerpt="行业需求增长。",
                    source_agent="industry_analyst",
                )
            ],
        )
        fundamentals = FundamentalsOutput(
            narrative="基本面分析",
            concerns=["收入增速放缓"],
            financial_filings=[
                SecFilingReference(
                    form="10-K",
                    fiscal_year=2025,
                    period_end="2026-01-25",
                    filed_at="2026-02-20",
                    cik="1045810",
                    accession_number="0001045810-26-000010",
                    primary_document="nvda-20260125.htm",
                    url="https://www.sec.gov/Archives/edgar/data/1045810/"
                    "000104581026000010/nvda-20260125.htm",
                )
            ],
        )
        valuation = ValuationOutput(
            narrative="估值分析",
            pe_ratio=30.0,
            pb_ratio=None,
            ps_ratio=8.0,
            evidence=[
                Evidence(
                    id="valuation-1",
                    kind="web",
                    title="Market data",
                    url="https://example.test/price",
                    publisher=None,
                    published_date=None,
                    excerpt=None,
                    source_agent="valuation_analyst",
                )
            ],
            market_inputs=MarketInputs(
                price=170.5,
                market_cap=4_000_000_000_000.0,
                currency="USD",
                as_of="2026-07-20",
                evidence_id="valuation-1",
            ),
        )
        risk = RiskOutput(
            narrative="风险分析",
            overall_rating="中",
            key_risks=["需求波动"],
            evidence=[],
        )

        self.assertEqual(industry.evidence[0].id, "industry-1")
        self.assertEqual(fundamentals.financial_filings[0].fiscal_year, 2025)
        self.assertEqual(valuation.pe_ratio, 30.0)
        self.assertEqual(valuation.market_inputs.evidence_id, "valuation-1")
        self.assertEqual(risk.overall_rating, "中")

    def test_risk_output_rejects_an_unknown_rating(self) -> None:
        with self.assertRaises(ValidationError):
            RiskOutput(
                narrative="风险分析",
                overall_rating="极高",
                key_risks=[],
                evidence=[],
            )

    def test_output_rejects_duplicate_evidence_ids(self) -> None:
        evidence = {
            "id": "industry-1",
            "kind": "web",
            "title": "行业报告",
            "url": "https://example.test/industry",
            "publisher": None,
            "published_date": None,
            "excerpt": None,
            "source_agent": "industry_analyst",
        }

        with self.assertRaises(ValidationError):
            IndustryOutput(narrative="行业分析", evidence=[evidence, evidence])

    def test_valuation_agent_output_rejects_duplicate_evidence_ids(self) -> None:
        evidence = Evidence(
            id="valuation-1",
            kind="web",
            title="市场数据",
            url="https://example.test/market",
            source_agent="valuation_analyst",
        )

        with self.assertRaises(ValidationError):
            ValuationAgentOutput(
                narrative="估值分析",
                evidence=[evidence, evidence],
            )

    def test_evidence_models_preserve_missing_values_in_json(self) -> None:
        output = ValuationOutput(
            narrative="估值分析",
            pe_ratio=None,
            pb_ratio=None,
            ps_ratio=None,
            evidence=[
                Evidence(
                    id="valuation-1",
                    kind="web",
                    title="市场数据",
                    url="https://example.test/market",
                    publisher=None,
                    published_date=None,
                    excerpt=None,
                    source_agent="valuation_analyst",
                )
            ],
            market_inputs=MarketInputs(
                price=None,
                market_cap=None,
                currency=None,
                as_of=None,
                evidence_id=None,
            ),
        )

        payload = output.model_dump(mode="json")

        self.assertIsNone(payload["evidence"][0]["publisher"])
        self.assertIsNone(payload["evidence"][0]["published_date"])
        self.assertIsNone(payload["market_inputs"]["price"])
        self.assertIsNone(payload["market_inputs"]["as_of"])

    def test_outputs_do_not_forbid_extra_fields(self) -> None:
        output = IndustryOutput.model_validate(
            {
                "narrative": "行业分析",
                "evidence": [],
                "confidence": 0.9,
            }
        )

        self.assertEqual(output.narrative, "行业分析")

    def test_analysis_state_only_requires_initial_inputs(self) -> None:
        self.assertEqual(AnalysisState.__required_keys__, {"ticker", "years"})
        self.assertEqual(
            AnalysisState.__optional_keys__,
            {
                "industry",
                "fundamentals",
                "valuation",
                "risk",
                "synthesis",
                "final_report",
                "cited_evidence_ids",
            },
        )


if __name__ == "__main__":
    unittest.main()
