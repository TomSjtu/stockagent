from __future__ import annotations

import os
from datetime import date
from typing import TYPE_CHECKING

from stockagent.config import RuntimeOptions, load_llm_config
from stockagent.errors import ConfigurationError
from stockagent.observability import get_logger

if TYPE_CHECKING:
    from stockagent.report.writer import ReportArtifacts


def run_stock_analysis(options: RuntimeOptions) -> ReportArtifacts:
    from stockagent.agents import run_stock_analysis_agent
    from stockagent.report.writer import write_report_artifacts

    logger = get_logger(__name__)
    llm_config = load_llm_config()
    if not os.getenv("TAVILY_API_KEY"):
        raise ConfigurationError(
            "TAVILY_API_KEY is required for agent reports. "
            "Set it in .env before running an analysis."
        )
    logger.info("加载 LLM 配置完成")
    logger.info("启动主分析 agent")
    report = run_stock_analysis_agent(
        options.ticker,
        options.years,
        llm_config,
    )
    logger.info("主分析 agent 完成")
    logger.info("开始写入报告")
    return write_report_artifacts(
        options.ticker,
        report.markdown,
        evidence_bundle=report.evidence_bundle,
        output_dir=options.output_dir,
        report_date=date.today(),
    )
