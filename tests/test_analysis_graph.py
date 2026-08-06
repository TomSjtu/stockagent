from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from stockagent.agents.orchestrator import (
    AnalysisNodes,
    _build_synthesize_node,
    build_analysis_graph,
    build_analysis_nodes,
)
from stockagent.agents.state import (
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
from stockagent.financials import (
    CashFlowMetrics,
    FinancialRecord,
    GrowthMetrics,
    ProfitabilityMetrics,
    SecFilingReference,
)
from stockagent.fundamentals.analysis import FundamentalsAnalysis
from stockagent.report.composer import AnnualFinancialSnapshot
from stockagent.report.delivery import deliver_report


class AnalysisGraphTest(unittest.TestCase):
    def test_graph_runs_complete_analysis_data_flow(self) -> None:
        observed_inputs: dict[str, set[str]] = {}

        def industry(state: dict) -> dict:
            observed_inputs["industry"] = set(state)
            return {
                "industry": IndustryOutput(
                    narrative=f"{state['ticker']} industry",
                    evidence=[],
                )
            }

        def fundamentals(state: dict) -> dict:
            observed_inputs["fundamentals"] = set(state)
            return {
                "fundamentals": FundamentalsOutput(
                    narrative=f"{state['years']} years fundamentals",
                    concerns=[],
                )
            }

        def valuation(state: dict) -> dict:
            observed_inputs["valuation"] = set(state)
            return {
                "valuation": ValuationOutput(
                    narrative=(
                        f"{state['industry'].narrative}; "
                        f"{state['fundamentals'].narrative}"
                    ),
                    pe_ratio=20.0,
                    pb_ratio=3.0,
                    ps_ratio=5.0,
                )
            }

        def risk(state: dict) -> dict:
            observed_inputs["risk"] = set(state)
            return {
                "risk": RiskOutput(
                    narrative=state["valuation"].narrative,
                    overall_rating="中",
                    key_risks=["competition"],
                    evidence=[],
                )
            }

        def synthesize(state: dict) -> dict:
            observed_inputs["synthesize"] = set(state)
            return {
                "synthesis": SynthesisOutput(
                    summary=state["risk"].narrative,
                    investment_recommendation="recommendation",
                )
            }

        graph = build_analysis_graph(
            AnalysisNodes(
                industry=industry,
                fundamentals=fundamentals,
                valuation=valuation,
                risk=risk,
                synthesize=synthesize,
            )
        )

        result = graph.invoke({"ticker": "AAPL", "years": 3})
        delivery = deliver_report(result, report_date=date(2026, 7, 29))

        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["years"], 3)
        self.assertEqual(result["industry"].narrative, "AAPL industry")
        self.assertEqual(result["fundamentals"].narrative, "3 years fundamentals")
        self.assertIn(
            "## 摘要\n\nAAPL industry; 3 years fundamentals",
            delivery.markdown,
        )
        self.assertEqual(
            result["synthesis"].summary,
            "AAPL industry; 3 years fundamentals",
        )
        self.assertEqual(observed_inputs["industry"], {"ticker", "years"})
        self.assertEqual(observed_inputs["fundamentals"], {"ticker", "years"})
        self.assertEqual(
            observed_inputs["valuation"],
            {"ticker", "years", "industry", "fundamentals"},
        )
        self.assertEqual(
            observed_inputs["risk"],
            {"ticker", "years", "industry", "fundamentals", "valuation"},
        )
        self.assertEqual(
            observed_inputs["synthesize"],
            {
                "ticker",
                "years",
                "industry",
                "fundamentals",
                "valuation",
                "risk",
            },
        )

    def test_valuation_waits_for_both_upstreams_and_runs_once(self) -> None:
        valuation_inputs: list[set[str]] = []

        def industry(_state: dict) -> dict:
            return {
                "industry": IndustryOutput(
                    narrative="industry",
                    evidence=[],
                )
            }

        def fundamentals(_state: dict) -> dict:
            return {
                "fundamentals": FundamentalsOutput(
                    narrative="fundamentals",
                    concerns=[],
                )
            }

        def valuation(state: dict) -> dict:
            valuation_inputs.append(set(state))
            return {
                "valuation": ValuationOutput(
                    narrative="valuation",
                    pe_ratio=None,
                    pb_ratio=None,
                    ps_ratio=None,
                )
            }

        def risk(_state: dict) -> dict:
            return {
                "risk": RiskOutput(
                    narrative="risk",
                    overall_rating="低",
                    key_risks=[],
                    evidence=[],
                )
            }

        def synthesize(_state: dict) -> dict:
            return {
                "synthesis": SynthesisOutput(
                    summary="summary",
                    investment_recommendation="recommendation",
                )
            }

        graph = build_analysis_graph(
            AnalysisNodes(
                industry=industry,
                fundamentals=fundamentals,
                valuation=valuation,
                risk=risk,
                synthesize=synthesize,
            )
        )

        graph.invoke({"ticker": "AAPL", "years": 3})

        self.assertEqual(len(valuation_inputs), 1)
        self.assertTrue({"industry", "fundamentals"}.issubset(valuation_inputs[0]))


class ReportCompositionFlowTest(unittest.TestCase):
    def test_real_nodes_project_financials_through_graph_to_report(self) -> None:
        filing_2023 = self._filing(2023)
        filing_2024 = self._filing(2024)
        analysis = FundamentalsAnalysis(
            ticker="AAPL",
            records=[
                FinancialRecord(
                    "AAPL",
                    "Apple Inc.",
                    2024,
                    revenue=2_000_000_000.0,
                    net_income=180_000_000.0,
                    operating_cash_flow=400_000_000.0,
                    capex=80_000_000.0,
                    eps_diluted=2.0,
                    shareholders_equity=500_000_000.0,
                    filing=filing_2024,
                ),
                FinancialRecord(
                    "AAPL",
                    "Apple Inc.",
                    2023,
                    revenue=1_250_000_000.0,
                    net_income=100_000_000.0,
                    operating_cash_flow=250_000_000.0,
                    capex=50_000_000.0,
                    eps_diluted=1.0,
                    shareholders_equity=400_000_000.0,
                    filing=filing_2023,
                ),
            ],
            profitability={
                2023: ProfitabilityMetrics(
                    fiscal_year=2023,
                    gross_margin=0.4,
                    net_margin=0.08,
                ),
                2024: ProfitabilityMetrics(
                    fiscal_year=2024,
                    gross_margin=0.45,
                    net_margin=0.09,
                ),
            },
            cash_flow={
                2023: CashFlowMetrics(
                    fiscal_year=2023,
                    free_cash_flow=200_000_000.0,
                ),
                2024: CashFlowMetrics(
                    fiscal_year=2024,
                    free_cash_flow=320_000_000.0,
                ),
            },
            financial_health={},
            growth={
                2023: GrowthMetrics(fiscal_year=2023, revenue_growth=None),
                2024: GrowthMetrics(fiscal_year=2024, revenue_growth=0.6),
            },
        )
        agent_results = {
            "industry": {
                "messages": [],
                "structured_response": IndustryOutput(
                    narrative="行业正文",
                    evidence=[],
                ),
            },
            "fundamentals": {
                "messages": [],
                "structured_response": FundamentalsAgentOutput(
                    narrative="基本面正文",
                    concerns=[],
                ),
            },
            "valuation": {
                "messages": [],
                "structured_response": ValuationAgentOutput(
                    narrative="估值正文",
                    evidence=[],
                    market_inputs=MarketInputs(
                        price=40.0,
                        market_cap=200_000_000.0,
                        currency="USD",
                    ),
                ),
            },
            "risk": {
                "messages": [],
                "structured_response": RiskOutput(
                    narrative="风险正文",
                    overall_rating="低",
                    key_risks=[],
                    evidence=[],
                ),
            },
        }
        model = FakeSynthesisModel(
            {
                "summary": "摘要正文",
                "investment_recommendation": "投资建议正文",
            }
        )

        with (
            patch(
                "stockagent.agents.orchestrator.build_industry_agent",
                return_value=FakeAgent(agent_results["industry"]),
            ),
            patch(
                "stockagent.agents.orchestrator.build_fundamentals_agent",
                return_value=FakeAgent(agent_results["fundamentals"]),
            ),
            patch(
                "stockagent.agents.orchestrator.build_valuation_agent",
                return_value=FakeAgent(agent_results["valuation"]),
            ),
            patch(
                "stockagent.agents.orchestrator.build_risk_agent",
                return_value=FakeAgent(agent_results["risk"]),
            ),
            patch(
                "stockagent.agents.facts._analysis.analyze_fundamentals",
                return_value=analysis,
            ),
        ):
            graph = build_analysis_graph(
                build_analysis_nodes(model, FakeProgressReporter())
            )
            result = graph.invoke({"ticker": "aapl", "years": 2})

        delivery = deliver_report(result)
        markdown = delivery.markdown
        self.assertIn("| 指标 | 2023 [^1] | 2024 [^2] |", markdown)
        self.assertIn("| 收入 | 1,250.0 | 2,000.0 |", markdown)
        self.assertIn("| 毛利率 | 40.0% | 45.0% |", markdown)
        self.assertIn(
            "[^1]: SEC 10-K｜截至 2023-12-31｜Filed 2024-02-20｜"
            "https://www.sec.gov/Archives/edgar/data/320193/annual-report-2023.htm",
            markdown,
        )
        self.assertIn(
            "[^2]: SEC 10-K｜截至 2024-12-31｜Filed 2025-02-20｜"
            "https://www.sec.gov/Archives/edgar/data/320193/annual-report-2024.htm",
            markdown,
        )
        self.assertEqual(result["valuation"].pe_ratio, 20.0)
        self.assertEqual(result["valuation"].pb_ratio, 0.4)
        self.assertEqual(result["valuation"].ps_ratio, 0.1)
        self.assertEqual(result["valuation"].market_inputs.price, 40.0)
        self.assertEqual(result["valuation"].market_inputs.market_cap, 200_000_000.0)

    def test_graph_composes_complete_report_and_renders_citations_in_reading_order(
        self,
    ) -> None:
        model = FakeSynthesisModel(
            {
                "summary": "摘要正文 [risk-1]",
                "investment_recommendation": "投资建议正文 [industry-1]",
            }
        )
        filing_2023 = self._filing(2023)
        filing_2024 = self._filing(2024)

        def industry(_state: dict) -> dict:
            return {
                "industry": IndustryOutput(
                    narrative="行业正文 [industry-1]",
                    evidence=[
                        self._evidence("industry-1", "行业来源", "industry_analyst")
                    ],
                )
            }

        def fundamentals(_state: dict) -> dict:
            return {
                "fundamentals": FundamentalsOutput(
                    narrative="基本面正文 [sec-2024]",
                    concerns=[],
                    annual_financials=[
                        AnnualFinancialSnapshot(
                            fiscal_year=2024,
                            revenue=2_000_000_000,
                            net_income=180_000_000,
                            operating_cash_flow=400_000_000,
                            capex=80_000_000,
                            free_cash_flow=320_000_000,
                            gross_margin=0.45,
                            net_margin=0.09,
                            revenue_growth=0.2,
                        ),
                        AnnualFinancialSnapshot(
                            fiscal_year=2023,
                            revenue=1_250_000_000,
                            net_income=100_000_000,
                            operating_cash_flow=250_000_000,
                            capex=50_000_000,
                            free_cash_flow=200_000_000,
                            gross_margin=0.4,
                            net_margin=0.08,
                            revenue_growth=None,
                        ),
                    ],
                    financial_filings=[filing_2024, filing_2023],
                )
            }

        def valuation(_state: dict) -> dict:
            return {
                "valuation": ValuationOutput(
                    narrative="估值正文 [valuation-1]",
                    pe_ratio=20.0,
                    pb_ratio=3.0,
                    ps_ratio=5.0,
                    evidence=[
                        self._evidence("valuation-1", "估值来源", "valuation_analyst")
                    ],
                )
            }

        def risk(_state: dict) -> dict:
            return {
                "risk": RiskOutput(
                    narrative="风险正文 [risk-1]",
                    overall_rating="中",
                    key_risks=[],
                    evidence=[self._evidence("risk-1", "风险来源", "risk_analyst")],
                )
            }

        graph = build_analysis_graph(
            AnalysisNodes(
                industry=industry,
                fundamentals=fundamentals,
                valuation=valuation,
                risk=risk,
                synthesize=_build_synthesize_node(
                    model,
                    FakeProgressReporter(),
                ),
            )
        )

        result = graph.invoke({"ticker": "aapl", "years": 2})

        delivery = deliver_report(result)
        markdown = delivery.markdown
        output_type = model.output_type
        if output_type is None:
            self.fail("汇总模型未请求结构化输出")
        self.assertEqual(output_type.__name__, "SynthesisOutput")
        self.assertEqual(result["synthesis"].summary, "摘要正文 [risk-1]")
        self.assertIn("只生成摘要和投资建议", model.messages[0]["content"])
        self._assert_section_order(
            markdown,
            [
                "## 摘要",
                "## 行业分析",
                "## 财务数据快照",
                "## 基本面分析",
                "## 估值分析",
                "## 风险评估",
                "## 投资建议",
                "## 数据口径",
                "## 免责声明",
                "## 参考来源",
            ],
        )
        self.assertIn("| 指标 | 2023 [^3] | 2024 [^4] |", markdown)
        self.assertIn("| 收入 | 1,250.0 | 2,000.0 |", markdown)
        self.assertIn("摘要正文 [^1]", markdown)
        self.assertIn("行业正文 [^2]", markdown)
        self.assertIn("投资建议正文 [^2]", markdown)
        self.assertNotIn("[industry-1]", markdown)
        self.assertNotIn("[sec-2023]", markdown)
        self.assertEqual(
            delivery.evidence_bundle.cited_evidence_ids,
            ["risk-1", "industry-1", "sec-2023", "sec-2024", "valuation-1"],
        )
        self.assertLess(markdown.index("## 免责声明"), markdown.index("## 参考来源"))

    def _evidence(self, evidence_id: str, title: str, source_agent: str) -> Evidence:
        return Evidence(
            id=evidence_id,
            kind="web",
            title=title,
            url=f"https://example.test/{evidence_id}",
            source_agent=source_agent,
        )

    def _filing(self, fiscal_year: int) -> SecFilingReference:
        return SecFilingReference(
            form="10-K",
            fiscal_year=fiscal_year,
            period_end=date(fiscal_year, 12, 31),
            filed_at=date(fiscal_year + 1, 2, 20),
            cik="320193",
            accession_number=f"0000320193-{fiscal_year + 1}-000001",
            primary_document="annual-report.htm",
            url=(
                "https://www.sec.gov/Archives/edgar/data/320193/"
                f"annual-report-{fiscal_year}.htm"
            ),
        )

    def _assert_section_order(self, markdown: str, sections: list[str]) -> None:
        positions = [markdown.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))


class FakeSynthesisModel:
    def __init__(self, response: dict[str, str]) -> None:
        self.response = response
        self.output_type: type | None = None
        self.messages: list[dict[str, str]] = []

    def with_structured_output(self, output_type: type) -> FakeSynthesisModel:
        self.output_type = output_type
        return self

    def invoke(self, messages: list[dict[str, str]]) -> dict[str, str]:
        self.messages = messages
        return self.response


class FakeAgent:
    def __init__(self, result: object) -> None:
        self.result = result

    def stream(self, _payload: object, *, stream_mode: object) -> object:
        yield ("values", self.result)


class FakeProgressReporter:
    def agent_started(self, agent: str) -> None:
        pass

    def agent_finished(self, agent: str, elapsed_seconds: float) -> None:
        pass

    def tool_started(self, agent: str, tool: str) -> None:
        pass

    def tool_finished(self, agent: str, tool: str) -> None:
        pass

    def tool_failed(self, agent: str, tool: str, detail: str) -> None:
        pass

    def model_output(self, agent: str, produced_characters: int) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
