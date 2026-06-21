from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from stockagent.report.writer import write_markdown_report, write_report


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

    def test_write_report_dispatches_markdown_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = write_report(
                "aapl",
                "# Report\n",
                report_format="md",
                output_dir=Path(temp_dir) / "output",
                report_date=date(2026, 6, 21),
            )

            self.assertEqual(output_path.name, "AAPL-2026-06-21.md")
            self.assertTrue(output_path.exists())

    def test_write_report_raises_for_unimplemented_html_writer(self) -> None:
        with self.assertRaises(NotImplementedError):
            write_report(
                "aapl",
                "<html></html>",
                report_format="html",
                output_dir=Path("output"),
            )


if __name__ == "__main__":
    unittest.main()
