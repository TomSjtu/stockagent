from __future__ import annotations

from datetime import date
from pathlib import Path

from stockagent.config import ReportFormat
from stockagent.observability import get_logger


def write_report(
    ticker: str,
    content: str,
    report_format: ReportFormat,
    output_dir: Path,
    report_date: date | None = None,
) -> Path:
    if report_format == "md":
        return write_markdown_report(
            ticker,
            content,
            output_dir=output_dir,
            report_date=report_date,
        )
    if report_format == "html":
        raise NotImplementedError("HTML report writing is not implemented yet.")
    if report_format == "pdf":
        raise NotImplementedError("PDF report writing is not implemented yet.")
    raise ValueError(f"Unsupported report format: {report_format}")


def write_markdown_report(
    ticker: str,
    content: str,
    output_dir: Path,
    report_date: date | None = None,
) -> Path:
    logger = get_logger(__name__)
    logger.info("开始写入 Markdown 报告")
    output_dir.mkdir(parents=True, exist_ok=True)

    current_date = report_date or date.today()
    output_path = output_dir / f"{ticker.upper()}-{current_date.isoformat()}.md"
    output_path.write_text(content, encoding="utf-8")
    logger.info("报告写入完成: %s", output_path)
    return output_path
