from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

from stockagent.config import LogLevel

_LOG_LEVELS: dict[LogLevel, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def setup_logging(
    level: LogLevel = "info",
    *,
    console: Console | None = None,
) -> None:
    """Configure process-wide console logging for one CLI run."""
    rich_console = console or Console(stderr=True)
    logging.basicConfig(
        level=_LOG_LEVELS[level],
        format="%(message)s",
        handlers=[
            RichHandler(
                console=rich_console,
                show_time=True,
                show_level=True,
                show_path=False,
                markup=False,
                log_time_format="%Y-%m-%d %H:%M:%S",
            )
        ],
        force=True,
    )
    logging.getLogger("httpx").setLevel(
        logging.INFO if level == "debug" else logging.WARNING
    )
    logging.getLogger("edgar").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return the named logger used by a StockAgent module."""
    return logging.getLogger(name)


def log_stage_started(logger: logging.Logger, stage: str) -> None:
    """Log the start of one user-visible workflow stage."""
    logger.info("%s", stage)


def log_stage_completed(logger: logging.Logger, stage: str) -> None:
    """Log completion of one user-visible workflow stage."""
    logger.info("%s", stage)


def log_stage_failed(logger: logging.Logger, stage: str, error: Exception) -> None:
    """Log a failed workflow stage with its expected domain error."""
    logger.error("%s: %s", stage, error)
