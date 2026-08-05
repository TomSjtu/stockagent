"""LangGraph orchestration for stock analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from stockagent.config import LLMConfig

if TYPE_CHECKING:
    from stockagent.agents.progress import ProgressReporter
    from stockagent.report.delivery import GeneratedReport

__all__ = ["run_stock_analysis_agent"]


def run_stock_analysis_agent(
    ticker: str,
    years: int,
    llm_config: LLMConfig,
    progress_reporter: ProgressReporter,
) -> GeneratedReport:
    """Run the stock-analysis graph through the package's lazy-import boundary."""
    from stockagent.agents.orchestrator import (
        run_stock_analysis_agent as _run_stock_analysis_agent,
    )

    return _run_stock_analysis_agent(
        ticker,
        years,
        llm_config,
        progress_reporter,
    )
