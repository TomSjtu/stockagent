from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from stockagent.app import run_stock_analysis
from stockagent.config import RuntimeOptions, default_output_dir
from stockagent.errors import StockAgentError
from stockagent.observability import get_logger, log_stage_failed, setup_logging


def _positive_int(value: str) -> int:
    try:
        years = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc

    if years <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return years


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument(
        "--years",
        type=_positive_int,
        default=3,
        help="Number of recent fiscal years to analyze.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir(),
        help="Directory for generated report.",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Log level",
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
        output_dir=args.output_dir,
        log_level=args.log_level,
    )


def main() -> None:
    options = parse_args()
    setup_logging(options.log_level)
    logger = get_logger(__name__)
    logger.info("初始化运行环境")

    try:
        run_stock_analysis(options)
        logger.info("主流程执行完成")
    except StockAgentError as exc:
        log_stage_failed(logger, "主流程执行失败", exc)
        raise SystemExit(f"Error: {exc}") from exc
