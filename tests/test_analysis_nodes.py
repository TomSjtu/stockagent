from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from stockagent.agents.errors import AgentOutputError
from stockagent.agents.orchestrator import build_analysis_nodes
from stockagent.agents.state import (
    FundamentalsOutput,
    IndustryOutput,
    MarketInputs,
    RiskOutput,
    ValuationOutput,
)


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

    def test_valuation_node_uses_deterministic_tool_metrics(self) -> None:
        structured_output = ValuationOutput(
            narrative="valuation",
            pe_ratio=1.0,
            pb_ratio=2.0,
            ps_ratio=3.0,
            evidence=[],
            market_inputs=MarketInputs(),
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


if __name__ == "__main__":
    unittest.main()
