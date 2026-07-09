from __future__ import annotations

from pathlib import Path

from stockagent.config import RuntimeOptions, load_llm_config
from stockagent.observability import get_logger


def run_stock_analysis(options: RuntimeOptions) -> Path:
    from stockagent.agents.orchestrator import run_stock_analysis_agent
    from stockagent.report.writer import write_markdown_report

    logger = get_logger(__name__)
    llm_config = load_llm_config()
    logger.info("加载 LLM 配置完成")
    logger.info("启动主分析 agent")
    report = run_stock_analysis_agent(
        options.ticker,
        options.years,
        llm_config,
    )
    logger.info("主分析 agent 完成")
    logger.info("开始写入报告")
    return write_markdown_report(
        options.ticker,
        report,
        output_dir=options.output_dir,
    )
