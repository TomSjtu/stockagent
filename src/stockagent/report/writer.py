from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from stockagent.observability import get_logger
from stockagent.report.evidence import EvidenceBundle, serialize_sources


@dataclass(frozen=True)
class ReportArtifacts:
    markdown_path: Path
    sources_path: Path


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


def write_report_artifacts(
    ticker: str,
    content: str,
    *,
    evidence_bundle: EvidenceBundle,
    output_dir: Path,
    report_date: date | None = None,
) -> ReportArtifacts:
    """Write a Markdown report and its JSON audit sidecar together."""
    logger = get_logger(__name__)
    logger.info("开始写入报告产物")
    output_dir.mkdir(parents=True, exist_ok=True)

    current_date = report_date or date.today()
    stem = f"{ticker.upper()}-{current_date.isoformat()}"
    markdown_path = output_dir / f"{stem}.md"
    sources_path = output_dir / f"{stem}.sources.json"

    markdown_path.write_text(content, encoding="utf-8")
    sources_path.write_text(
        serialize_sources(
            ticker=ticker,
            report_date=current_date,
            evidence_bundle=evidence_bundle,
        ),
        encoding="utf-8",
    )
    logger.info("报告产物写入完成: %s, %s", markdown_path, sources_path)
    return ReportArtifacts(
        markdown_path=markdown_path,
        sources_path=sources_path,
    )
