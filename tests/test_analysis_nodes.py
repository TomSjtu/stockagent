from __future__ import annotations

import unittest
from typing import cast
from unittest.mock import patch

from langchain_core.messages import ToolMessage

from stockagent.agents.errors import AgentOutputError
from stockagent.agents.orchestrator import build_analysis_nodes
from stockagent.agents.state import (
    FundamentalsAgentOutput,
    FundamentalsOutput,
    IndustryOutput,
    MarketInputs,
    RiskOutput,
    SynthesisOutput,
    ValuationAgentOutput,
    ValuationOutput,
)
from stockagent.report.composer import AnnualFinancialSnapshot


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
        self.output_type: type | None = None

    def with_structured_output(self, output_type: type) -> FakeModel:
        self.output_type = output_type
        return self

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
        synthesize_result: object = {
            "summary": "摘要",
            "investment_recommendation": "投资建议",
        },
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

    def test_fundamentals_node_fetches_facts_with_analysis_state_context(self) -> None:
        output = FundamentalsAgentOutput(narrative="llm", concerns=[])
        snapshot = AnnualFinancialSnapshot(fiscal_year=2024, revenue=1_000.0)
        nodes, _agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={
                "messages": [
                    ToolMessage(
                        content="tool result is intentionally ignored",
                        name="get_fundamentals_analysis",
                        status="success",
                        tool_call_id="tool-1",
                    ),
                ],
                "structured_response": output,
            },
            valuation_result={},
            risk_result={},
        )

        with patch(
            "stockagent.agents.orchestrator.build_fundamentals_facts",
            return_value={
                "annual_financials": [snapshot],
                "financial_filings": [],
            },
        ) as apply_facts:
            result = nodes.fundamentals({"ticker": "aapl", "years": 2})

        self.assertEqual(
            result,
            {
                "fundamentals": FundamentalsOutput(
                    narrative="llm",
                    concerns=[],
                    annual_financials=[snapshot],
                    financial_filings=[],
                )
            },
        )
        apply_facts.assert_called_once_with("aapl", 2)

    def test_valuation_node_builds_facts_from_declared_market_inputs(self) -> None:
        output = ValuationAgentOutput(
            narrative="llm",
            market_inputs=MarketInputs(
                price=40.0,
                market_cap=200.0,
                currency="USD",
            ),
        )
        nodes, _agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={
                "messages": [],
                "structured_response": output,
            },
            risk_result={},
        )

        with patch(
            "stockagent.agents.orchestrator.build_valuation_facts",
            return_value={
                "pe_ratio": 20.0,
                "pb_ratio": 4.0,
                "ps_ratio": 2.0,
            },
        ) as build_facts:
            result = nodes.valuation(
                {
                    "ticker": "AAPL",
                    "years": 3,
                    "industry": IndustryOutput(narrative="industry", evidence=[]),
                    "fundamentals": FundamentalsOutput(narrative="fundamentals", concerns=[]),
                }
            )

        self.assertEqual(
            result,
            {
                "valuation": ValuationOutput(
                    narrative="llm",
                    market_inputs=MarketInputs(
                        price=40.0,
                        market_cap=200.0,
                        currency="USD",
                    ),
                    pe_ratio=20.0,
                    pb_ratio=4.0,
                    ps_ratio=2.0,
                )
            },
        )
        build_facts.assert_called_once_with(
            "AAPL",
            3,
            price=40.0,
            market_cap=200.0,
        )

    def test_valuation_node_wraps_unknown_market_evidence_id(self) -> None:
        nodes, _agents, _model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={
                "messages": [],
                "structured_response": {
                    "narrative": "llm",
                    "evidence": [],
                    "market_inputs": {"evidence_id": "valuation-1"},
                },
            },
            risk_result={},
        )

        with self.assertRaisesRegex(
            AgentOutputError,
            "valuation_analyst.*invalid structured_response",
        ):
            nodes.valuation(
                {
                    "ticker": "AAPL",
                    "years": 3,
                    "industry": IndustryOutput(narrative="industry", evidence=[]),
                    "fundamentals": FundamentalsOutput(
                        narrative="fundamentals",
                        concerns=[],
                    ),
                }
            )

    def test_synthesize_node_returns_narrative_fragments(self) -> None:
        nodes, _agents, model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
            synthesize_result={
                "summary": "摘要正文",
                "investment_recommendation": "投资建议正文",
            },
        )
        state = {
            "ticker": "AAPL",
            "years": 3,
            "industry": IndustryOutput(narrative="industry", evidence=[]),
            "fundamentals": FundamentalsOutput(narrative="fundamentals", concerns=[]),
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

        self.assertEqual(
            result,
            {
                "synthesis": SynthesisOutput(
                    summary="摘要正文",
                    investment_recommendation="投资建议正文",
                )
            },
        )
        self.assertIsNotNone(model.output_type)

    def test_synthesize_node_prompt_contains_all_four_upstream_outputs(self) -> None:
        nodes, _agents, model = self._build_nodes(
            industry_result={},
            fundamentals_result={},
            valuation_result={},
            risk_result={},
            synthesize_result={
                "summary": "摘要正文",
                "investment_recommendation": "投资建议正文",
            },
        )
        state = {
            "ticker": "AAPL",
            "years": 3,
            "industry": IndustryOutput(narrative="行业上游输出", evidence=[]),
            "fundamentals": FundamentalsOutput(
                narrative="基本面上游输出",
                concerns=["收入增长放缓"],
            ),
            "valuation": ValuationOutput(narrative="估值上游输出"),
            "risk": RiskOutput(
                narrative="风险上游输出",
                overall_rating="低",
                key_risks=["需求波动"],
                evidence=[],
            ),
        }

        nodes.synthesize(state)

        self.assertIsInstance(model.payload, list)
        prompt = cast(list[dict[str, str]], model.payload)[0]["content"]
        for output in [
            state["industry"],
            state["fundamentals"],
            state["valuation"],
            state["risk"],
        ]:
            self.assertIn(output.model_dump_json(indent=2), prompt)


if __name__ == "__main__":
    unittest.main()
