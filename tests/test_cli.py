from __future__ import annotations

import unittest
from pathlib import Path

from stockagent.cli import parse_args


class CliTest(unittest.TestCase):
    def test_parse_args_defaults_to_markdown_report_format(self) -> None:
        options = parse_args(["aapl"])

        self.assertEqual(options.ticker, "aapl")
        self.assertEqual(options.report_format, "md")
        self.assertEqual(options.output_dir, Path.cwd() / "output")

    def test_parse_args_accepts_output_dir(self) -> None:
        options = parse_args(["aapl", "--output-dir", "reports"])

        self.assertEqual(options.output_dir, Path("reports"))


if __name__ == "__main__":
    unittest.main()
