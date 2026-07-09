from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from stockagent.cli import main, parse_args
from stockagent.config import AppConfig


class CliTest(unittest.TestCase):
    def test_parse_args_defaults(self) -> None:
        options = parse_args(["aapl"])

        self.assertEqual(options.ticker, "aapl")
        self.assertEqual(options.output_dir, Path.cwd() / "output")
        self.assertEqual(options.log_level, "info")

    def test_parse_args_accepts_output_dir(self) -> None:
        options = parse_args(["aapl", "--output-dir", "reports"])

        self.assertEqual(options.output_dir, Path("reports"))

    def test_parse_args_accepts_log_level(self) -> None:
        options = parse_args(["aapl", "--log-level", "warning"])

        self.assertEqual(options.log_level, "warning")

    def test_main_does_not_print_final_report_path_to_stdout(self) -> None:
        stdout = io.StringIO()

        with (
            patch.object(sys, "argv", ["stock", "aapl"]),
            patch("sys.stdout", stdout),
            patch(
                "stockagent.cli.load_app_config",
                return_value=AppConfig(edgar_identity="tester@example.com"),
            ),
            patch(
                "stockagent.cli.run_stock_analysis",
                return_value=Path("output/AAPL.md"),
            ),
        ):
            main()

        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
