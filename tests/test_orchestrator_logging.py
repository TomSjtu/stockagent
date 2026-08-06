from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from stockagent.agents import run_stock_analysis_agent
from stockagent.agents.errors import AgentOutputError
from stockagent.agents.state import (
    Evidence,
    FundamentalsOutput,
    IndustryOutput,
    RiskOutput,
    SynthesisOutput,
    ValuationOutput,
)
from stockagent.config import DEFAULT_LLM_MODEL, LLMConfig
from stockagent.financials import SecFilingReference


class FakeGraph:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.initial_state: dict[str, object] | None = None

    def invoke(self, initial_state: dict[str, object]) -> dict[str, object]:
        self.initial_state = initial_state
        return self.result


class OrchestratorRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://example.test/v1",
            model=DEFAULT_LLM_MODEL,
        )

    def test_run_stock_analysis_agent_builds_dag_and_returns_delivery(self) -> None:
        progress_reporter = object()
        evidence = Evidence(
            id="industry-1",
            kind="web",
            title="Industry source",
            url="https://example.test/industry",
            source_agent="industry_analyst",
        )
        graph = FakeGraph(
            {
                "ticker": "nvda",
                "years": 3,
                "final_report": "旧报告不应被读取",
                "cited_evidence_ids": ["旧引用不应被读取"],
                "industry": IndustryOutput(narrative="industry", evidence=[evidence]),
                "fundamentals": FundamentalsOutput(
                    narrative="fundamentals",
                    concerns=[],
                ),
                "valuation": ValuationOutput(
                    narrative="valuation",
                    pe_ratio=None,
                    pb_ratio=None,
                    ps_ratio=None,
                ),
                "risk": RiskOutput(
                    narrative="risk",
                    overall_rating="低",
                    key_risks=[],
                    evidence=[],
                ),
                "synthesis": SynthesisOutput(
                    summary="行业结论 [industry-1]",
                    investment_recommendation="保持观察",
                ),
            }
        )

        with (
            patch(
                "stockagent.agents.orchestrator.build_model", return_value="model"
            ) as build_model,
            patch(
                "stockagent.agents.orchestrator.build_analysis_nodes",
                return_value="nodes",
            ) as build_nodes,
            patch(
                "stockagent.agents.orchestrator.build_analysis_graph",
                return_value=graph,
            ) as build_graph,
        ):
            report = run_stock_analysis_agent(
                "nvda",
                3,
                self.llm_config,
                progress_reporter,
            )

        self.assertIn("# NVDA 研究报告", report.markdown)
        self.assertIn("## 摘要\n\n行业结论 [^1]", report.markdown)
        self.assertIn("## 投资建议\n\n保持观察", report.markdown)
        self.assertEqual(report.evidence_bundle.evidence, [evidence])
        self.assertEqual(report.evidence_bundle.cited_evidence_ids, ["industry-1"])
        build_model.assert_called_once_with(self.llm_config)
        build_nodes.assert_called_once_with("model", progress_reporter)
        build_graph.assert_called_once_with("nodes")
        self.assertEqual(graph.initial_state, {"ticker": "nvda", "years": 3})

    def test_run_stock_analysis_agent_rejects_missing_synthesis(self) -> None:
        progress_reporter = object()
        graph = FakeGraph(
            {
                "ticker": "NVDA",
                "years": 3,
                "industry": IndustryOutput(narrative="industry", evidence=[]),
                "fundamentals": FundamentalsOutput(
                    narrative="fundamentals",
                    concerns=[],
                ),
                "valuation": ValuationOutput(narrative="valuation"),
                "risk": RiskOutput(
                    narrative="risk",
                    overall_rating="低",
                    key_risks=[],
                    evidence=[],
                ),
            }
        )

        with (
            patch("stockagent.agents.orchestrator.build_model", return_value="model"),
            patch(
                "stockagent.agents.orchestrator.build_analysis_nodes",
                return_value="nodes",
            ),
            patch(
                "stockagent.agents.orchestrator.build_analysis_graph",
                return_value=graph,
            ),
        ):
            with self.assertRaisesRegex(AgentOutputError, "synthesis"):
                run_stock_analysis_agent(
                    "NVDA",
                    3,
                    self.llm_config,
                    progress_reporter,
                )

    def test_run_stock_analysis_agent_includes_financial_filings_as_sec_evidence(
        self,
    ) -> None:
        progress_reporter = object()
        filing = SecFilingReference(
            form="10-K",
            fiscal_year=2024,
            period_end=date(2024, 12, 31),
            filed_at=date(2025, 2, 20),
            cik="123456",
            accession_number="0000123456-25-000001",
            primary_document="annual-report.htm",
            url=(
                "https://www.sec.gov/Archives/edgar/data/123456/"
                "000012345625000001/annual-report.htm"
            ),
        )
        graph = FakeGraph(
            {
                "ticker": "nvda",
                "years": 3,
                "final_report": "旧报告不应被读取",
                "cited_evidence_ids": ["旧引用不应被读取"],
                "industry": IndustryOutput(narrative="industry", evidence=[]),
                "fundamentals": FundamentalsOutput(
                    narrative="fundamentals",
                    concerns=[],
                    financial_filings=[filing],
                ),
                "valuation": ValuationOutput(
                    narrative="valuation",
                    pe_ratio=None,
                    pb_ratio=None,
                    ps_ratio=None,
                ),
                "risk": RiskOutput(
                    narrative="risk",
                    overall_rating="低",
                    key_risks=[],
                    evidence=[],
                ),
                "synthesis": SynthesisOutput(
                    summary="年度数据 [sec-2024]",
                    investment_recommendation="保持观察",
                ),
            }
        )

        with (
            patch("stockagent.agents.orchestrator.build_model", return_value="model"),
            patch(
                "stockagent.agents.orchestrator.build_analysis_nodes",
                return_value="nodes",
            ),
            patch(
                "stockagent.agents.orchestrator.build_analysis_graph",
                return_value=graph,
            ),
        ):
            report = run_stock_analysis_agent(
                "nvda",
                3,
                self.llm_config,
                progress_reporter,
            )

        self.assertEqual(report.evidence_bundle.cited_evidence_ids, ["sec-2024"])
        self.assertEqual(report.evidence_bundle.financial_filings, [filing])
        self.assertEqual(report.evidence_bundle.evidence[0].id, "sec-2024")
        self.assertEqual(
            report.evidence_bundle.evidence[0].title,
            "SEC 10-K｜截至 2024-12-31｜Filed 2025-02-20",
        )


if __name__ == "__main__":
    unittest.main()
