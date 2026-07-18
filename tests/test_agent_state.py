from __future__ import annotations

import unittest

from pydantic import ValidationError

from stockagent.agents.state import (
    AnalysisState,
    FundamentalsOutput,
    IndustryOutput,
    RiskOutput,
    ValuationOutput,
)


class AgentStateTest(unittest.TestCase):
    def test_outputs_accept_the_cross_agent_contract(self) -> None:
        industry = IndustryOutput(
            narrative="行业分析",
            sources=["https://example.test/industry"],
        )
        fundamentals = FundamentalsOutput(
            narrative="基本面分析",
            key_metrics={"roe": 0.25, "debt_ratio": None},
            concerns=["收入增速放缓"],
        )
        valuation = ValuationOutput(
            narrative="估值分析",
            pe_ratio=30.0,
            pb_ratio=None,
            ps_ratio=8.0,
            price_source="https://example.test/price",
        )
        risk = RiskOutput(
            narrative="风险分析",
            overall_rating="中",
            key_risks=["需求波动"],
            sources=["https://example.test/risk"],
        )

        self.assertEqual(industry.sources, ["https://example.test/industry"])
        self.assertIsNone(fundamentals.key_metrics["debt_ratio"])
        self.assertEqual(valuation.pe_ratio, 30.0)
        self.assertEqual(risk.overall_rating, "中")

    def test_risk_output_rejects_an_unknown_rating(self) -> None:
        with self.assertRaises(ValidationError):
            RiskOutput(
                narrative="风险分析",
                overall_rating="极高",
                key_risks=[],
                sources=[],
            )

    def test_outputs_do_not_forbid_extra_fields(self) -> None:
        output = IndustryOutput.model_validate(
            {
                "narrative": "行业分析",
                "sources": [],
                "confidence": 0.9,
            }
        )

        self.assertEqual(output.narrative, "行业分析")

    def test_analysis_state_only_requires_initial_inputs(self) -> None:
        self.assertEqual(AnalysisState.__required_keys__, {"ticker", "years"})
        self.assertEqual(
            AnalysisState.__optional_keys__,
            {"industry", "fundamentals", "valuation", "risk", "final_report"},
        )


if __name__ == "__main__":
    unittest.main()
