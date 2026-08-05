from __future__ import annotations

import unittest
from unittest.mock import patch

from rich.console import Console

from stockagent.cli import RichProgressReporter


class RichProgressReporterTest(unittest.TestCase):
    def test_logs_agent_completion_with_elapsed_time(self) -> None:
        reporter = RichProgressReporter(Console(force_terminal=False))

        with self.assertLogs("stockagent.cli", level="INFO") as logs:
            with reporter:
                reporter.agent_started("industry_analyst")
                reporter.agent_finished("industry_analyst", 1.234)

        self.assertEqual(
            logs.output,
            [
                "INFO:stockagent.cli:启动 agent: industry_analyst",
                "INFO:stockagent.cli:agent industry_analyst 完成（耗时 1.23 秒）",
            ],
        )

    def test_logs_tool_failure_at_error_level_with_detail(self) -> None:
        reporter = RichProgressReporter(Console(force_terminal=False))

        with self.assertLogs("stockagent.cli", level="ERROR") as logs:
            with reporter:
                reporter.tool_failed(
                    "industry_analyst",
                    "搜索市场与行业信息",
                    "search failed",
                )

        self.assertEqual(
            logs.output,
            [
                "ERROR:stockagent.cli:agent industry_analyst 失败: "
                "搜索市场与行业信息（search failed）"
            ],
        )

    def test_context_stops_live_region_when_analysis_fails(self) -> None:
        reporter = RichProgressReporter(
            Console(force_terminal=True, no_color=False)
        )

        with (
            patch.object(reporter._live, "start") as start,
            patch.object(reporter._live, "stop") as stop,
            self.assertRaisesRegex(RuntimeError, "analysis failed"),
        ):
            with reporter:
                raise RuntimeError("analysis failed")

        start.assert_called_once_with(refresh=True)
        stop.assert_called_once_with()

    def test_refresh_runs_after_reporter_state_lock_is_released(self) -> None:
        reporter = RichProgressReporter(
            Console(force_terminal=True, no_color=False)
        )

        def assert_lock_released() -> None:
            acquired = reporter._lock.acquire(blocking=False)
            self.assertTrue(acquired)
            if acquired:
                reporter._lock.release()

        with patch.object(reporter, "_refresh", side_effect=assert_lock_released):
            reporter.agent_started("industry_analyst")
            reporter.tool_started(
                "industry_analyst",
                "搜索市场与行业信息",
                "AAPL",
            )
            reporter.tool_finished(
                "industry_analyst",
                "搜索市场与行业信息",
            )
            reporter.model_output("industry_analyst", 10)
            reporter.tool_failed(
                "industry_analyst",
                "搜索市场与行业信息",
                "failed",
            )
            reporter.agent_finished("industry_analyst", 1.0)

    def test_no_color_terminal_falls_back_to_plain_log_lines(self) -> None:
        reporter = RichProgressReporter(
            Console(force_terminal=True, no_color=True)
        )

        with (
            patch.object(reporter._live, "start") as start,
            self.assertLogs("stockagent.cli", level="INFO") as logs,
        ):
            with reporter:
                reporter.agent_started("industry_analyst")

        start.assert_not_called()
        self.assertEqual(
            logs.output,
            ["INFO:stockagent.cli:启动 agent: industry_analyst"],
        )


if __name__ == "__main__":
    unittest.main()
