from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from stockagent.report.writer import write_markdown_report


class ReportWriterTest(unittest.TestCase):
    def test_write_markdown_report_creates_output_dir_and_uses_ticker_date_name(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"

            output_path = write_markdown_report(
                "aapl",
                "# Report\n",
                output_dir=output_dir,
                report_date=date(2026, 6, 21),
            )

            self.assertTrue(output_dir.exists())
            self.assertEqual(output_path.name, "AAPL-2026-06-21.md")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "# Report\n")

    def test_write_markdown_report_logs_write_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"

            with self.assertLogs("stockagent.report.writer", level="INFO") as logs:
                output_path = write_markdown_report(
                    "aapl",
                    "# Report\n",
                    output_dir=output_dir,
                    report_date=date(2026, 6, 21),
                )

            self.assertIn(
                "INFO:stockagent.report.writer:开始写入 Markdown 报告",
                logs.output,
            )
            self.assertIn(
                f"INFO:stockagent.report.writer:报告写入完成: {output_path}",
                logs.output,
            )

if __name__ == "__main__":
    unittest.main()
