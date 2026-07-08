from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from stockagent.agents.orchestrator import (
    _AgentProgressCallbackHandler,
    run_stock_analysis_agent,
)
from stockagent.config import DEFAULT_LLM_MODEL, LLMConfig


class FakeSuccessfulAgent:
    def __init__(self) -> None:
        self.config: dict | None = None

    def invoke(self, _payload: dict, config: dict | None = None) -> dict:
        self.config = config
        return {"files": {"final_report.md": "# Final Report\n"}}


class OrchestratorLoggingTest(unittest.TestCase):
    def test_callback_logs_subagent_and_business_tool_progress(self) -> None:
        handler = _AgentProgressCallbackHandler()
        task_run_id = uuid4()
        chain_run_id = uuid4()
        tool_run_id = uuid4()

        with self.assertLogs("stockagent.agents.orchestrator", level="INFO") as logs:
            handler.on_tool_start(
                {"name": "task"},
                "",
                run_id=task_run_id,
                inputs={"subagent_type": "fundamentals_analyst"},
            )
            handler.on_chain_start({}, {}, run_id=chain_run_id, parent_run_id=task_run_id)
            handler.on_tool_start(
                {"name": "get_full_analysis"},
                "",
                run_id=tool_run_id,
                parent_run_id=chain_run_id,
            )
            handler.on_tool_end("{}", run_id=tool_run_id, parent_run_id=chain_run_id)
            handler.on_tool_end("done", run_id=task_run_id)

        self.assertEqual(
            logs.output,
            [
                "INFO:stockagent.agents.orchestrator:启动 subagent: fundamentals_analyst",
                "INFO:stockagent.agents.orchestrator:subagent fundamentals_analyst 调用工具: get_full_analysis",
                "INFO:stockagent.agents.orchestrator:subagent fundamentals_analyst 工具返回: success",
                "INFO:stockagent.agents.orchestrator:subagent fundamentals_analyst 完成",
            ],
        )

    def test_callback_logs_valuation_tool_progress(self) -> None:
        handler = _AgentProgressCallbackHandler()
        task_run_id = uuid4()
        tool_run_id = uuid4()

        with self.assertLogs("stockagent.agents.orchestrator", level="INFO") as logs:
            handler.on_tool_start(
                {"name": "task"},
                "",
                run_id=task_run_id,
                inputs={"subagent_type": "valuation_analyst"},
            )
            handler.on_tool_start(
                {"name": "compute_valuation_metrics"},
                "",
                run_id=tool_run_id,
                parent_run_id=task_run_id,
            )
            handler.on_tool_end("{}", run_id=tool_run_id, parent_run_id=task_run_id)
            handler.on_tool_end("done", run_id=task_run_id)

        self.assertEqual(
            logs.output,
            [
                "INFO:stockagent.agents.orchestrator:启动 subagent: valuation_analyst",
                "INFO:stockagent.agents.orchestrator:subagent valuation_analyst "
                "调用工具: compute_valuation_metrics",
                "INFO:stockagent.agents.orchestrator:subagent valuation_analyst 工具返回: success",
                "INFO:stockagent.agents.orchestrator:subagent valuation_analyst 完成",
            ],
        )

    def test_callback_logs_subagent_and_business_tool_failures(self) -> None:
        handler = _AgentProgressCallbackHandler()
        task_run_id = uuid4()
        tool_run_id = uuid4()

        with self.assertLogs("stockagent.agents.orchestrator", level="INFO") as logs:
            handler.on_tool_start(
                {"name": "task"},
                "",
                run_id=task_run_id,
                inputs={"subagent_type": "industry_analyst"},
            )
            handler.on_tool_start(
                {"name": "web_search"},
                "",
                run_id=tool_run_id,
                parent_run_id=task_run_id,
            )
            handler.on_tool_error(
                RuntimeError("search failed"),
                run_id=tool_run_id,
                parent_run_id=task_run_id,
            )
            handler.on_tool_error(RuntimeError("agent failed"), run_id=task_run_id)

        self.assertEqual(
            logs.output,
            [
                "INFO:stockagent.agents.orchestrator:启动 subagent: industry_analyst",
                "INFO:stockagent.agents.orchestrator:subagent industry_analyst 调用工具: web_search",
                "ERROR:stockagent.agents.orchestrator:subagent industry_analyst 工具返回: failed",
                "ERROR:stockagent.agents.orchestrator:subagent industry_analyst 失败: agent failed",
            ],
        )

    def test_run_stock_analysis_agent_passes_progress_callback_to_agent(self) -> None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://example.test/v1",
            model=DEFAULT_LLM_MODEL,
        )
        agent = FakeSuccessfulAgent()

        with patch(
            "stockagent.agents.orchestrator.create_stock_analysis_agent",
            return_value=agent,
        ):
            report = run_stock_analysis_agent("NVDA", 3, llm_config)

        self.assertEqual(report, "# Final Report\n")
        self.assertIsNotNone(agent.config)
        callbacks = agent.config["callbacks"] if agent.config is not None else []
        self.assertEqual(len(callbacks), 1)
        self.assertIsInstance(callbacks[0], _AgentProgressCallbackHandler)


if __name__ == "__main__":
    unittest.main()
