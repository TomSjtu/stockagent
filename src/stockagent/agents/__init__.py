"""LangGraph orchestration for stock analysis."""

from stockagent.config import LLMConfig

__all__ = ["run_stock_analysis_agent"]


def run_stock_analysis_agent(
    ticker: str,
    years: int,
    llm_config: LLMConfig,
) -> str:
    from stockagent.agents.orchestrator import (
        run_stock_analysis_agent as _run_stock_analysis_agent,
    )

    return _run_stock_analysis_agent(ticker, years, llm_config)
