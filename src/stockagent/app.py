from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from stockagent.config import CLIOptions, load_app_config
from stockagent.observability import get_logger

if TYPE_CHECKING:
    from stockagent.agents.progress import ProgressReporter
    from stockagent.report.writer import ReportArtifacts


def run_stock_analysis(
    options: CLIOptions,
    progress_reporter: ProgressReporter,
) -> ReportArtifacts:
    """Run one report workflow and write its paired delivery artifacts.

    Raises ConfigurationError when a required external-service credential is absent.
    """
    logger = get_logger(__name__)
    config = load_app_config()
    from edgar import set_identity  # type: ignore[import-untyped]

    from stockagent.agents import run_stock_analysis_agent
    from stockagent.report.writer import write_report_artifacts

    set_identity(config.edgar_identity)
    logger.info("加载 LLM 配置完成")
    # 调用 Agent 图，取得渲染后的 Markdown 和其 EvidenceBundle
    report = run_stock_analysis_agent(
        options.ticker,
        options.years,
        config.llm,
        progress_reporter,
    )
    
    # 将同一个 date.today() 值传给交付函数，用于两个输出文件的共同名称和 manifest 日期
    return write_report_artifacts(
        options.ticker,
        report.markdown,
        evidence_bundle=report.evidence_bundle,
        output_dir=options.output_dir,
        report_date=date.today(),
    )
