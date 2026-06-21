from __future__ import annotations

from pathlib import Path

from stockagent.app import AnalysisResult
from stockagent.config import RuntimeOptions
from stockagent.report.builder import build_report
from stockagent.report.writer import write_report


def generate_report(result: AnalysisResult, options: RuntimeOptions) -> Path:
    content = build_report(result, options.report_format)
    return write_report(
        result.ticker,
        content,
        report_format=options.report_format,
        output_dir=options.output_dir,
    )
