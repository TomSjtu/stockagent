from __future__ import annotations

import unittest
from collections.abc import Callable
from unittest.mock import patch

from langchain.agents.structured_output import ToolStrategy

from stockagent.agents.fundamentals_agent import build_fundamentals_agent
from stockagent.agents.industry_agent import build_industry_agent
from stockagent.agents.risk_agent import build_risk_agent
from stockagent.agents.state import (
    FundamentalsOutput,
    IndustryOutput,
    RiskOutput,
    ValuationOutput,
)
from stockagent.agents.valuation_agent import build_valuation_agent
from stockagent.tools import (
    compute_valuation_metrics,
    get_fundamentals_analysis,
    web_search,
)


class AgentBuildersTest(unittest.TestCase):
    def test_industry_builder_uses_search_and_industry_output(self) -> None:
        self._assert_builder_contract(
            module="stockagent.agents.industry_agent",
            builder=build_industry_agent,
            tools=[web_search],
            output_type=IndustryOutput,
            prompt_terms=("实际采用", "kind='web'", "[industry-1]", "来源优先级"),
        )

    def test_fundamentals_builder_uses_single_aggregate_tool(self) -> None:
        self._assert_builder_contract(
            module="stockagent.agents.fundamentals_agent",
            builder=build_fundamentals_agent,
            tools=[get_fundamentals_analysis],
            output_type=FundamentalsOutput,
            prompt_terms=("SEC 10-K", "[sec-"),
        )

    def test_valuation_builder_uses_search_and_valuation_tool(self) -> None:
        self._assert_builder_contract(
            module="stockagent.agents.valuation_agent",
            builder=build_valuation_agent,
            tools=[web_search, compute_valuation_metrics],
            output_type=ValuationOutput,
            prompt_terms=(
                "实际采用",
                "kind='web'",
                "[valuation-1]",
                "market_inputs",
                "来源优先级",
            ),
        )

    def test_risk_builder_only_uses_search(self) -> None:
        self._assert_builder_contract(
            module="stockagent.agents.risk_agent",
            builder=build_risk_agent,
            tools=[web_search],
            output_type=RiskOutput,
            prompt_terms=("实际采用", "kind='web'", "[risk-1]", "来源优先级"),
        )

    def _assert_builder_contract(
        self,
        *,
        module: str,
        builder: Callable[..., object],
        tools: list[object],
        output_type: type,
        prompt_terms: tuple[str, ...],
    ) -> None:
        model = object()
        built_agent = object()

        with patch(f"{module}.create_agent", return_value=built_agent) as create_agent:
            result = builder(model)

        self.assertIs(result, built_agent)
        create_agent.assert_called_once()
        kwargs = create_agent.call_args.kwargs
        self.assertIs(kwargs["model"], model)
        self.assertEqual(kwargs["tools"], tools)
        self.assertIsInstance(kwargs["system_prompt"], str)
        self.assertTrue(kwargs["system_prompt"].strip())
        for prompt_term in prompt_terms:
            with self.subTest(prompt_term=prompt_term):
                self.assertIn(prompt_term, kwargs["system_prompt"])
        self.assertNotIn("read_file", kwargs["system_prompt"])
        self.assertNotIn("write_file", kwargs["system_prompt"])
        strategy = kwargs["response_format"]
        self.assertIsInstance(strategy, ToolStrategy)
        self.assertIs(strategy.schema, output_type)
        self.assertFalse(strategy.handle_errors)


if __name__ == "__main__":
    unittest.main()
