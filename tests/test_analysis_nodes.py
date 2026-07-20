from __future__ import annotations

import json
import unittest
from datetime import date
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from stockagent.agents.errors import AgentOutputError
from stockagent.agents.orchestrator import build_analysis_nodes
from stockagent.agents.state import (
    Evidence,
    FundamentalsOutput,
    IndustryOutput,
    MarketInputs,
    RiskOutput,
    ValuationOutput,
)
from stockagent.financials import SecFilingReference


class FakeAgent:
    def __init__(self, result: object) -> None:
        self.result = result
        self.payload: object | None = None
        self.config: object | None = None

    def invoke(self, payload: object, config: object | None = None) -> object:
        self.payload = payload
        self.config = config
        return self.result


class FakeModel:
    def __init__(self, result: object) -> None:
        self.result = result
        self.payload: object | None = None

    def invoke(self, payload: object) -> object:
        self.payload = payload
        return self.result


class AnalysisNodesTest(unittest.TestCase):
    def _build_nodes(
        self,
        *,
        industry_result: object,
        fundamentals_result: object,
        valuation_result: object,
        risk_result: object,
        synthesize_result: object = AIMessage(content="# Report"),
    ) -> tuple[object, dict[str, FakeAgent], FakeModel]:
        agents = {
            "industry": FakeAgent(industry_result),
            "fundamentals": FakeAgent(fundamentals_result),
            "valuation": FakeAgent(valuation_result),
            "risk": FakeAgent(risk_result),
        }
        model = FakeModel(synthesize_result)

        with (
            patch(
                "stockagent.agents.orchestrator.build_industry_agent",
                return_value=agents["industry"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_fundamentals_agent",
                return_value=agents["fundamentals"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_valuation_agent",
                return_value=agents["valuation"],
            ),
            patch(
                "stockagent.agents.orchestrator.build_risk_agent",
                return_value=agents["risk"],
            ),
        ):
            nodes = build_analysis_nodes(model)

        return nodes, agents, model

    def test_industry_node_returns_local_typed_update(self) -> None:
        output = IndustryOutput(narrative="Industry", evidence=[])
        nodes, agents, _model = self._build_nodes(
            industry_result={"messages": [], "structured_response": output},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )

        result = nodes.industry({"ticker": "aapl", "years": 3})

        self.assertEqual(result, {"industry": output})
        self.assertEqual(
            agents["industry"].payload,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "请分析 AAPL 最近 3 个财年的行业趋势、竞争格局、市场地位和主要挑战。",
                    }
                ]
            },
        )
        self.assertIsInstance(agents["industry"].config, dict)
        callbacks = agents["industry"].config["callbacks"]
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(callbacks[0].agent_name, "industry_analyst")

    def test_agent_tool_error_stops_node_before_structured_output(self) -> None:
        nodes, _agents, _model = self._build_nodes(
            industry_result={
                "messages": [
                    ToolMessage(
                        content="search failed",
                        name="web_search",
                        status="error",
                        tool_call_id="tool-1",
                    )
                ],
                "structured_response": IndustryOutput(narrative="ignored", evidence=[]),
            },
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )

        with self.assertRaisesRegex(AgentOutputError, "industry_analyst.*web_search"):
            nodes.industry({"ticker": "AAPL", "years": 3})

    def test_agent_requires_a_valid_structured_response(self) -> None:
        nodes, _agents, _model = self._build_nodes(
            industry_result={"messages": []},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
        )

        with self.assertRaisesRegex(AgentOutputError, "missing structured_response"):
            nodes.industry({"ticker": "AAPL", "years": 3})

    def test_fundamentals_node_uses_filings_from_deterministic_tool_result(self) -> None:
        filing = SecFilingReference(
            form="10-K",
            fiscal_year=2024,
            period_end=date(2024, 12, 31),
            filed_at=date(2025, 2, 20),
            cik="123456",
            accession_number="0000123456-25-000001",
            primary_document="annual-report.htm",
            url="https://www.sec.gov/Archives/example/annual-report.htm",
        )
        structured_output = FundamentalsOutput(
            narrative="fundamentals",
            key_metrics={},
            concerns=[],
            financial_filings=[],
        )
        fundamentals_payload = json.dumps(
            {
                "ticker": "AAPL",
                "records": [
                    {
                        "fiscal_year": 2024,
                        "filing": filing.model_dump(mode="json"),
                    },
                    {"fiscal_year": 2023, "filing": None},
                ],
            }
        )
        nodes, _agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={
                "messages": [
                    ToolMessage(
                        content=fundamentals_payload,
                        name="get_fundamentals_analysis",
                        tool_call_id="tool-1",
                    )
                ],
                "structured_response": structured_output,
            },
            valuation_result={},
            risk_result={},
        )

        result = nodes.fundamentals({"ticker": "aapl", "years": 2})

        self.assertEqual(result["fundamentals"].narrative, "fundamentals")
        self.assertEqual(result["fundamentals"].financial_filings, [filing])

    def test_valuation_node_uses_deterministic_tool_metrics(self) -> None:
        structured_output = ValuationOutput(
            narrative="valuation",
            pe_ratio=1.0,
            pb_ratio=2.0,
            ps_ratio=3.0,
            evidence=[
                Evidence(
                    id="valuation-1",
                    kind="web",
                    title="Market data",
                    url="https://example.test/market-data",
                    source_agent="valuation_analyst",
                )
            ],
            market_inputs=MarketInputs(
                price=1.0,
                market_cap=2.0,
                currency="USD",
                as_of=date(2026, 7, 20),
                evidence_id="valuation-1",
            ),
        )
        valuation_payload = json.dumps(
            {
                "ticker": "AAPL",
                "years": 3,
                "valuation": {
                    "pe_ratio": 30.0,
                    "pb_ratio": 45.0,
                    "ps_ratio": 8.0,
                },
                "market_inputs": {
                    "price": 200.0,
                    "market_cap": 3_000_000_000_000.0,
                },
            }
        )
        nodes, _agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={
                "messages": [
                    ToolMessage(
                        content=valuation_payload,
                        name="compute_valuation_metrics",
                        tool_call_id="tool-1",
                    )
                ],
                "structured_response": structured_output,
            },
            risk_result={},
        )
        state = {
            "ticker": "aapl",
            "years": 3,
            "industry": IndustryOutput(narrative="industry", evidence=[]),
            "fundamentals": FundamentalsOutput(
                narrative="fundamentals",
                key_metrics={},
                concerns=[],
            ),
        }

        result = nodes.valuation(state)

        self.assertEqual(result["valuation"].narrative, "valuation")
        self.assertEqual(result["valuation"].pe_ratio, 30.0)
        self.assertEqual(result["valuation"].pb_ratio, 45.0)
        self.assertEqual(result["valuation"].ps_ratio, 8.0)
        self.assertEqual(result["valuation"].market_inputs.price, 200.0)
        self.assertEqual(
            result["valuation"].market_inputs.market_cap,
            3_000_000_000_000.0,
        )
        self.assertEqual(result["valuation"].market_inputs.currency, "USD")
        self.assertEqual(result["valuation"].market_inputs.as_of, date(2026, 7, 20))
        self.assertEqual(
            result["valuation"].market_inputs.evidence_id,
            "valuation-1",
        )

    def test_valuation_node_rejects_market_input_evidence_not_selected(self) -> None:
        structured_output = ValuationOutput(
            narrative="valuation",
            pe_ratio=None,
            pb_ratio=None,
            ps_ratio=None,
            evidence=[],
            market_inputs=MarketInputs(evidence_id="valuation-1"),
        )
        valuation_payload = json.dumps(
            {
                "ticker": "AAPL",
                "years": 3,
                "valuation": {
                    "pe_ratio": None,
                    "pb_ratio": None,
                    "ps_ratio": None,
                },
                "market_inputs": {"price": None, "market_cap": None},
            }
        )
        nodes, _agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={
                "messages": [
                    ToolMessage(
                        content=valuation_payload,
                        name="compute_valuation_metrics",
                        tool_call_id="tool-1",
                    )
                ],
                "structured_response": structured_output,
            },
            risk_result={},
        )
        state = {
            "ticker": "AAPL",
            "years": 3,
            "industry": IndustryOutput(narrative="industry", evidence=[]),
            "fundamentals": FundamentalsOutput(
                narrative="fundamentals",
                key_metrics={},
                concerns=[],
            ),
        }

        with self.assertRaises(AgentOutputError):
            nodes.valuation(state)

    def test_valuation_node_rejects_invalid_deterministic_tool_results(self) -> None:
        structured_output = ValuationOutput(
            narrative="valuation",
            pe_ratio=None,
            pb_ratio=None,
            ps_ratio=None,
            evidence=[],
            market_inputs=MarketInputs(),
        )
        state = {
            "ticker": "AAPL",
            "years": 3,
            "industry": IndustryOutput(narrative="industry", evidence=[]),
            "fundamentals": FundamentalsOutput(
                narrative="fundamentals",
                key_metrics={},
                concerns=[],
            ),
        }
        cases = {
            "missing": [],
            "invalid_json": [
                ToolMessage(
                    content="not json",
                    name="compute_valuation_metrics",
                    tool_call_id="tool-1",
                )
            ],
            "wrong_ticker": [
                ToolMessage(
                    content=json.dumps(
                        {
                            "ticker": "MSFT",
                            "years": 3,
                            "valuation": {},
                        }
                    ),
                    name="compute_valuation_metrics",
                    tool_call_id="tool-1",
                )
            ],
            "wrong_years": [
                ToolMessage(
                    content=json.dumps(
                        {
                            "ticker": "AAPL",
                            "years": 5,
                            "valuation": {},
                        }
                    ),
                    name="compute_valuation_metrics",
                    tool_call_id="tool-1",
                )
            ],
            "missing_market_inputs": [
                ToolMessage(
                    content=json.dumps(
                        {
                            "ticker": "AAPL",
                            "years": 3,
                            "valuation": {
                                "pe_ratio": None,
                                "pb_ratio": None,
                                "ps_ratio": None,
                            },
                        }
                    ),
                    name="compute_valuation_metrics",
                    tool_call_id="tool-1",
                )
            ],
            "missing_market_input_field": [
                ToolMessage(
                    content=json.dumps(
                        {
                            "ticker": "AAPL",
                            "years": 3,
                            "valuation": {
                                "pe_ratio": None,
                                "pb_ratio": None,
                                "ps_ratio": None,
                            },
                            "market_inputs": {"price": None},
                        }
                    ),
                    name="compute_valuation_metrics",
                    tool_call_id="tool-1",
                )
            ],
        }

        for name, messages in cases.items():
            with self.subTest(name=name):
                nodes, _agents, _model = self._build_nodes(
                    industry_result={},
                    fundamentals_result={},
                    valuation_result={
                        "messages": messages,
                        "structured_response": structured_output,
                    },
                    risk_result={},
                )

                with self.assertRaises(AgentOutputError):
                    nodes.valuation(state)

    def test_fundamentals_node_rejects_invalid_deterministic_tool_results(self) -> None:
        structured_output = FundamentalsOutput(
            narrative="fundamentals",
            key_metrics={},
            concerns=[],
        )
        cases = {
            "missing": [],
            "invalid_json": [
                ToolMessage(
                    content="not json",
                    name="get_fundamentals_analysis",
                    tool_call_id="tool-1",
                )
            ],
            "wrong_ticker": [
                ToolMessage(
                    content=json.dumps({"ticker": "MSFT", "records": []}),
                    name="get_fundamentals_analysis",
                    tool_call_id="tool-1",
                )
            ],
            "mismatched_filing": [
                ToolMessage(
                    content=json.dumps(
                        {
                            "ticker": "AAPL",
                            "records": [
                                {
                                    "fiscal_year": 2023,
                                    "filing": {
                                        "form": "10-K",
                                        "fiscal_year": 2024,
                                        "period_end": "2024-12-31",
                                        "filed_at": "2025-02-20",
                                        "cik": "123456",
                                        "accession_number": "0000123456-25-000001",
                                        "primary_document": "annual-report.htm",
                                        "url": "https://example.test/annual-report.htm",
                                    },
                                }
                            ],
                        }
                    ),
                    name="get_fundamentals_analysis",
                    tool_call_id="tool-1",
                )
            ],
        }

        for name, messages in cases.items():
            with self.subTest(name=name):
                nodes, _agents, _model = self._build_nodes(
                    industry_result={},
                    fundamentals_result={
                        "messages": messages,
                        "structured_response": structured_output,
                    },
                    valuation_result={},
                    risk_result={},
                )

                with self.assertRaises(AgentOutputError):
                    nodes.fundamentals({"ticker": "AAPL", "years": 3})

    def test_synthesize_node_returns_markdown_from_model(self) -> None:
        nodes, _agents, model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
            synthesize_result=AIMessage(content="# Report\n\nNot investment advice."),
        )
        state = {
            "ticker": "AAPL",
            "years": 3,
            "industry": IndustryOutput(narrative="industry", evidence=[]),
            "fundamentals": FundamentalsOutput(
                narrative="fundamentals",
                key_metrics={"revenue_growth": 0.1},
                concerns=[],
            ),
            "valuation": ValuationOutput(
                narrative="valuation",
                pe_ratio=30.0,
                pb_ratio=45.0,
                ps_ratio=8.0,
                evidence=[],
                market_inputs=MarketInputs(),
            ),
            "risk": RiskOutput(
                narrative="risk",
                overall_rating="中",
                key_risks=["competition"],
                evidence=[],
            ),
        }

        result = nodes.synthesize(state)

        self.assertEqual(result, {"final_report": "# Report\n\nNot investment advice."})
        self.assertIn("30.0", model.payload[0]["content"])
        self.assertIn("不得自行重新计算", model.payload[0]["content"])
        self.assertIn("保留", model.payload[0]["content"])
        self.assertIn("[industry-1]", model.payload[0]["content"])
        self.assertIn("[sec-", model.payload[0]["content"])
        self.assertIn(
            "财务数据仅覆盖最近可得年度 10-K，未纳入最新 10-Q 与 TTM",
            model.payload[0]["content"],
        )


if __name__ == "__main__":
    unittest.main()
