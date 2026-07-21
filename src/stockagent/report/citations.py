from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from stockagent.agents.state import Evidence
from stockagent.observability import get_logger

_UNKNOWN_INTERNAL_MARKER = r"[a-z][a-z0-9_]*-\d+"


@dataclass(frozen=True)
class CitationRenderResult:
    # 将内部证据标记替换为脚注后的报告正文
    markdown: str
    # 按正文首次引用顺序排列的证据 ID
    cited_evidence_ids: list[str]


def render_citations(
    markdown: str,
    evidence: list[Evidence],
) -> CitationRenderResult:
    """Replace known internal evidence markers with Markdown footnotes."""
    evidence_by_id = {item.id: item for item in evidence}
    marker_pattern = _marker_pattern(evidence_by_id)
    cited_evidence_ids: list[str] = []
    footnote_numbers: dict[str, int] = {}
    logger = get_logger(__name__)

    def replace_marker(match: re.Match[str]) -> str:
        evidence_id = match.group(1)
        if evidence_id not in evidence_by_id:
            logger.warning("报告包含未知证据标记，已移除: %s", evidence_id)
            return ""

        if evidence_id not in footnote_numbers:
            cited_evidence_ids.append(evidence_id)
            footnote_numbers[evidence_id] = len(cited_evidence_ids)
        return f"[^{footnote_numbers[evidence_id]}]"

    rendered_markdown = marker_pattern.sub(replace_marker, markdown)
    if not cited_evidence_ids:
        return CitationRenderResult(
            markdown=rendered_markdown,
            cited_evidence_ids=cited_evidence_ids,
        )

    references = "\n".join(
        f"[^{footnote_numbers[evidence_id]}]: "
        f"{_format_reference(evidence_by_id[evidence_id])}"
        for evidence_id in cited_evidence_ids
    )
    return CitationRenderResult(
        markdown=f"{rendered_markdown.rstrip()}\n\n## 参考来源\n\n{references}\n",
        cited_evidence_ids=cited_evidence_ids,
    )


def _format_reference(evidence: Evidence) -> str:
    if evidence.kind == "sec_filing":
        return "｜".join([evidence.title, evidence.url])

    publisher = evidence.publisher or urlparse(evidence.url).netloc
    parts = [publisher, evidence.title]
    if evidence.published_date is not None:
        parts.append(evidence.published_date.isoformat())
    parts.append(evidence.url)
    return "｜".join(part for part in parts if part)


def _marker_pattern(evidence_by_id: dict[str, Evidence]) -> re.Pattern[str]:
    known_ids = [re.escape(evidence_id) for evidence_id in evidence_by_id]
    return re.compile(r"\[(" + "|".join([*known_ids, _UNKNOWN_INTERNAL_MARKER]) + r")\]")
