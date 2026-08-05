from __future__ import annotations

import unittest

from stockagent.cli import LoggingProgressReporter


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
