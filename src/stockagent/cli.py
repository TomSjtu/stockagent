from __future__ import annotations

import argparse
from collections.abc import Sequence

from stockagent.app import run_stock_analysis
from stockagent.config import RuntimeOptions, load_app_config
from stockagent.errors import StockAgentError
from stockagent.report.builder import build_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument(
        "--report-format",
        choices=["text", "md", "html", "pdf"],
        default="text",
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
    )


def main() -> None:
    try:
        config = load_app_config()
        options = parse_args()
        result = run_stock_analysis(options, config)
        output = build_report(result, options.report_format)
    except StockAgentError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(output)
