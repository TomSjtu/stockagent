from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from stockagent.app import run_stock_analysis
from stockagent.config import CLIOptions, default_output_dir
from stockagent.errors import StockAgentError
from stockagent.observability import get_logger, log_stage_failed, setup_logging


class LoggingProgressReporter:
    """Present progress events as standard log records."""

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    def agent_started(self, agent: str) -> None:
        self._logger.info("启动 agent: %s", agent)

    def agent_finished(self, agent: str, elapsed_seconds: float) -> None:
        self._logger.info(
            "agent %s 完成（耗时 %.2f 秒）",
            agent,
            elapsed_seconds,
        )

    def tool_started(self, agent: str, tool: str, args_summary: str) -> None:
        suffix = f"（{args_summary}）" if args_summary else ""
        self._logger.info("agent %s 开始: %s%s", agent, tool, suffix)

    def tool_finished(self, agent: str, tool: str) -> None:
        self._logger.info("agent %s 完成: %s", agent, tool)

    def tool_failed(self, agent: str, tool: str, detail: str) -> None:
        self._logger.error("agent %s 失败: %s（%s）", agent, tool, detail)

    def tokens(self, agent: str, produced: int) -> None:
        self._logger.debug("agent %s 已生成 %d 个内容单元", agent, produced)


def _positive_int(value: str) -> int:
    try:
        years = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc

    if years <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return years


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for a single stock-analysis run."""
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
) -> CLIOptions:
    """Parse CLI arguments into the application runtime options."""
    parser = build_parser()
    args = parser.parse_args(argv)

    return CLIOptions(
        ticker=args.ticker,
        years=args.years,
        output_dir=args.output_dir,
        log_level=args.log_level,
    )


def main() -> None:
    """Run the CLI workflow and present domain errors as command failures."""
    options = parse_args()
    setup_logging(options.log_level)
    logger = get_logger(__name__)
    progress_reporter = LoggingProgressReporter()
    logger.info("初始化运行环境")

    try:
        run_stock_analysis(options, progress_reporter)
        logger.info("主流程执行完成")
    except StockAgentError as exc:
        log_stage_failed(logger, "主流程执行失败", exc)
        raise SystemExit(f"Error: {exc}") from exc
