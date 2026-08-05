from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from stockagent.cli import main, parse_args


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

    def test_parse_args_rejects_invalid_years(self) -> None:
        for years in ("0", "-1", "1.5"):
            with self.subTest(years=years):
                with self.assertRaises(SystemExit) as raised:
                    parse_args(["aapl", "--years", years])

                self.assertEqual(raised.exception.code, 2)

    def test_main_rejects_invalid_years_before_starting_analysis(self) -> None:
        with (
            patch.object(sys, "argv", ["stock", "aapl", "--years", "0"]),
            patch("stockagent.cli.run_stock_analysis") as run_analysis,
            self.assertRaises(SystemExit) as raised,
        ):
            main()

        self.assertEqual(raised.exception.code, 2)
        run_analysis.assert_not_called()

    def test_main_does_not_print_final_report_path_to_stdout(self) -> None:
        stdout = io.StringIO()

        with (
            patch.object(sys, "argv", ["stock", "aapl"]),
            patch("sys.stdout", stdout),
            patch(
                "stockagent.cli.run_stock_analysis",
                return_value=Path("output/AAPL.md"),
            ),
        ):
            main()

        self.assertEqual(stdout.getvalue(), "")

    def test_main_creates_one_live_reporter_around_the_whole_workflow(self) -> None:
        progress_reporter = object()
        reporter_context = unittest.mock.MagicMock()
        reporter_context.__enter__.return_value = progress_reporter

        with (
            patch.object(sys, "argv", ["stock", "aapl"]),
            patch(
                "stockagent.cli.RichProgressReporter",
                return_value=reporter_context,
            ) as reporter_type,
            patch("stockagent.cli.run_stock_analysis") as run_analysis,
        ):
            main()

        reporter_type.assert_called_once_with(ANY)
        reporter_context.__enter__.assert_called_once_with()
        reporter_context.__exit__.assert_called_once()
        run_analysis.assert_called_once_with(ANY, progress_reporter)


if __name__ == "__main__":
    unittest.main()
