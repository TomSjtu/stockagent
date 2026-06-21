from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from stockagent.app import run_stock_analysis
from stockagent.config import RuntimeOptions, default_output_dir, load_app_config
from stockagent.errors import StockAgentError
from stockagent.report.builder import build_report
from stockagent.report.writer import write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--years", type=int, default=3, help="Number of recent fiscal years to analyze.")
    parser.add_argument(
        "--report-format",
        choices=["md", "html", "pdf"],
        default="md",
        help="Format for generated report.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="Directory for generated report.",
    )
    return parser


def parse_args(
    argv: Sequence[str] | None = None,
) -> RuntimeOptions:
    parser = build_parser()
    args = parser.parse_args(argv)

    return RuntimeOptions(
        ticker=args.ticker,
        years=args.years,
        report_format=args.report_format,
        output_dir=args.output_dir,
    )


def main() -> None:
    try:
        config = load_app_config()
        options = parse_args()
        result = run_stock_analysis(options, config)
        output = build_report(result, options.report_format)
        output_path = write_report(
            result.ticker,
            output,
            report_format=options.report_format,
            output_dir=options.output_dir,
        )
        output = f"Report written to {output_path}"
    except StockAgentError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(output)
