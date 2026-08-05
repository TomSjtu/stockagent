from __future__ import annotations

import argparse
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import perf_counter
from types import TracebackType

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.text import Text

from stockagent.app import run_stock_analysis
from stockagent.config import CLIOptions, default_output_dir
from stockagent.errors import StockAgentError
from stockagent.observability import get_logger, log_stage_failed, setup_logging


@dataclass
class _AgentProgress:
    started_at: float
    activity: str = "正在分析"
    failed: bool = False


class RichProgressReporter(AbstractContextManager["RichProgressReporter"]):
    """Present concurrent agent progress in one shared Rich live region."""

    def __init__(self, console: Console) -> None:
        self._logger = get_logger(__name__)
        self._console = console
        self._live_enabled = console.is_terminal and not console.no_color
        self._lock = Lock()
        self._agents: dict[str, _AgentProgress] = {}
        self._live = Live(
            console=console,
            get_renderable=self._render,
            refresh_per_second=4,
            transient=True,
            redirect_stdout=False,
            redirect_stderr=False,
        )

    def __enter__(self) -> RichProgressReporter:
        if self._live_enabled:
            self._live.start(refresh=True)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._live_enabled:
            self._live.stop()

    def agent_started(self, agent: str) -> None:
        with self._lock:
            self._agents[agent] = _AgentProgress(started_at=perf_counter())
        self._refresh()
        if not self._live_enabled:
            self._logger.info("启动 agent: %s", agent)

    def agent_finished(self, agent: str, elapsed_seconds: float) -> None:
        with self._lock:
            self._agents.pop(agent, None)
        self._refresh()
        self._logger.info(
            "agent %s 完成（耗时 %.2f 秒）",
            agent,
            elapsed_seconds,
        )

    def tool_started(self, agent: str, tool: str, args_summary: str) -> None:
        suffix = f"（{args_summary}）" if args_summary else ""
        with self._lock:
            progress = self._agents.get(agent)
            if progress is not None:
                progress.activity = f"{tool}{suffix}"
                progress.failed = False
        self._refresh()
        if not self._live_enabled:
            self._logger.info("agent %s 开始: %s%s", agent, tool, suffix)

    def tool_finished(self, agent: str, tool: str) -> None:
        with self._lock:
            progress = self._agents.get(agent)
            if progress is not None:
                progress.activity = "正在分析"
        self._refresh()
        if not self._live_enabled:
            self._logger.info("agent %s 完成: %s", agent, tool)

    def tool_failed(self, agent: str, tool: str, detail: str) -> None:
        with self._lock:
            progress = self._agents.get(agent)
            if progress is not None:
                progress.activity = f"{tool}：{detail}"
                progress.failed = True
        self._refresh()
        self._logger.error("agent %s 失败: %s（%s）", agent, tool, detail)

    def tokens(self, agent: str, produced: int) -> None:
        with self._lock:
            progress = self._agents.get(agent)
            if progress is not None:
                progress.activity = f"正在生成（{produced}）"
        self._refresh()

    def _render(self) -> RenderableType:
        with self._lock:
            snapshot = [
                (agent, progress.started_at, progress.activity, progress.failed)
                for agent, progress in self._agents.items()
            ]
        now = perf_counter()
        lines = []
        for agent, started_at, activity, failed in snapshot:
            style = "bold red" if failed else "cyan"
            lines.append(
                Text(
                    f"{agent}  {activity}  {now - started_at:.1f} 秒",
                    style=style,
                )
            )
        return Group(*lines)

    def _refresh(self) -> None:
        if self._live_enabled and self._live.is_started:
            self._live.refresh()


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
    console = Console(stderr=True)
    setup_logging(options.log_level, console=console)
    logger = get_logger(__name__)

    try:
        with RichProgressReporter(console) as progress_reporter:
            logger.info("初始化运行环境")
            run_stock_analysis(options, progress_reporter)
            logger.info("主流程执行完成")
    except StockAgentError as exc:
        log_stage_failed(logger, "主流程执行失败", exc)
        raise SystemExit(f"Error: {exc}") from exc
