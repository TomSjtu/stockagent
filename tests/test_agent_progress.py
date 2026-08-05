from __future__ import annotations

import unittest
from uuid import uuid4

from stockagent.agents.progress import AgentProgressCallbackHandler
from stockagent.cli import LoggingProgressReporter


class AgentProgressCallbackHandlerTest(unittest.TestCase):
    def test_logs_mapped_tool_lifecycle_for_fixed_agent(self) -> None:
        handler = AgentProgressCallbackHandler("valuation_analyst")
        run_id = uuid4()

        with self.assertLogs("stockagent.agents.orchestrator", level="INFO") as logs:
            handler.on_tool_start(
                {"name": "compute_valuation_metrics"},
                "",
                run_id=run_id,
            )
            handler.on_tool_end("{}", run_id=run_id)

        self.assertEqual(
            logs.output,
            [
                "INFO:stockagent.agents.orchestrator:agent valuation_analyst 开始: 计算估值指标",
                "INFO:stockagent.agents.orchestrator:agent valuation_analyst 完成: 计算估值指标",
            ],
        )

    def test_logs_mapped_tool_failure_for_fixed_agent(self) -> None:
        handler = AgentProgressCallbackHandler("risk_analyst")
        run_id = uuid4()

        with self.assertLogs("stockagent.agents.orchestrator", level="INFO") as logs:
            handler.on_tool_start(
                {"name": "web_search"},
                "",
                run_id=run_id,
            )
            handler.on_tool_error(RuntimeError("search failed"), run_id=run_id)

        self.assertEqual(
            logs.output,
            [
                "INFO:stockagent.agents.orchestrator:agent risk_analyst 开始: 搜索近期公司风险信息",
                "ERROR:stockagent.agents.orchestrator:agent risk_analyst 失败: 搜索近期公司风险信息",
            ],
        )


class LoggingProgressReporterTest(unittest.TestCase):
    def test_logs_agent_completion_with_elapsed_time(self) -> None:
        reporter = LoggingProgressReporter()

        with self.assertLogs("stockagent.cli", level="INFO") as logs:
            reporter.agent_started("industry_analyst")
            reporter.agent_finished("industry_analyst", 1.234)

        self.assertEqual(
            logs.output,
            [
                "INFO:stockagent.cli:启动 agent: industry_analyst",
                "INFO:stockagent.cli:agent industry_analyst 完成（耗时 1.23 秒）",
            ],
        )


if __name__ == "__main__":
    unittest.main()
