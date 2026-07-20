from __future__ import annotations

import unittest
from unittest.mock import patch

from stockagent.agents import run_stock_analysis_agent
from stockagent.agents.errors import AgentOutputError
from stockagent.config import DEFAULT_LLM_MODEL, LLMConfig


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

    def test_run_stock_analysis_agent_builds_dag_and_returns_final_report(self) -> None:
        graph = FakeGraph({"final_report": "# Final Report\n"})

        with (
            patch("stockagent.agents.orchestrator.build_model", return_value="model") as build_model,
            patch("stockagent.agents.orchestrator.build_analysis_nodes", return_value="nodes") as build_nodes,
            patch("stockagent.agents.orchestrator.build_analysis_graph", return_value=graph) as build_graph,
        ):
            report = run_stock_analysis_agent("nvda", 3, self.llm_config)

        self.assertEqual(report, "# Final Report\n")
        build_model.assert_called_once_with(self.llm_config)
        build_nodes.assert_called_once_with("model")
        build_graph.assert_called_once_with("nodes")
        self.assertEqual(graph.initial_state, {"ticker": "nvda", "years": 3})

    def test_run_stock_analysis_agent_rejects_missing_final_report(self) -> None:
        graph = FakeGraph({"ticker": "NVDA", "years": 3})

        with (
            patch("stockagent.agents.orchestrator.build_model", return_value="model"),
            patch("stockagent.agents.orchestrator.build_analysis_nodes", return_value="nodes"),
            patch("stockagent.agents.orchestrator.build_analysis_graph", return_value=graph),
        ):
            with self.assertRaisesRegex(AgentOutputError, "final_report"):
                run_stock_analysis_agent("NVDA", 3, self.llm_config)


if __name__ == "__main__":
    unittest.main()
