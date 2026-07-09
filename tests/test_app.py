from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from stockagent.app import run_stock_analysis
from stockagent.config import RuntimeOptions


class RunStockAnalysisTest(unittest.TestCase):
    def test_run_stock_analysis_uses_agent_report_path(self) -> None:
        options = RuntimeOptions(ticker="fake", years=2)

        with (
            patch("stockagent.app.load_llm_config", return_value="llm-config"),
            patch(
                "stockagent.agents.orchestrator.run_stock_analysis_agent",
                return_value="# Agent Report\n",
            ) as run_agent,
            patch(
                "stockagent.report.writer.write_markdown_report",
                return_value=Path("output/FAKE.md"),
            ) as write_report,
        ):
            output_path = run_stock_analysis(options)

        run_agent.assert_called_once_with("fake", 2, "llm-config")
        write_report.assert_called_once_with(
            "fake",
            "# Agent Report\n",
            output_dir=options.output_dir,
        )
        self.assertEqual(output_path, Path("output/FAKE.md"))

    def test_run_stock_analysis_logs_main_stages(self) -> None:
        options = RuntimeOptions(ticker="fake", years=2)

        with (
            patch("stockagent.app.load_llm_config", return_value="llm-config"),
            patch(
                "stockagent.agents.orchestrator.run_stock_analysis_agent",
                return_value="# Agent Report\n",
            ),
            patch(
                "stockagent.report.writer.write_markdown_report",
                return_value=Path("output/FAKE.md"),
            ),
            self.assertLogs("stockagent.app", level="INFO") as logs,
        ):
            run_stock_analysis(options)

        self.assertIn("INFO:stockagent.app:加载 LLM 配置完成", logs.output)
        self.assertIn("INFO:stockagent.app:启动主分析 agent", logs.output)
        self.assertIn("INFO:stockagent.app:主分析 agent 完成", logs.output)
        self.assertIn("INFO:stockagent.app:开始写入报告", logs.output)


if __name__ == "__main__":
    unittest.main()
