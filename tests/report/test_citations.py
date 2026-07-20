from __future__ import annotations

import unittest
from datetime import date

from stockagent.agents.state import Evidence
from stockagent.report.citations import render_citations


class CitationRendererTest(unittest.TestCase):
    def test_render_citations_numbers_known_markers_by_first_appearance(self) -> None:
        evidence = [
            Evidence(
                id="industry-1",
                kind="web",
                title="Industry source",
                url="https://example.test/industry",
                publisher="Example News",
                published_date=date(2026, 7, 10),
                excerpt="Industry excerpt",
                source_agent="industry_analyst",
            ),
            Evidence(
                id="valuation-2",
                kind="web",
                title="Valuation source",
                url="https://example.test/valuation",
                publisher="Example Markets",
                published_date=date(2026, 7, 11),
                excerpt="Valuation excerpt",
                source_agent="valuation_analyst",
            ),
        ]

        result = render_citations(
            "估值结论[valuation-2]。\n\n行业趋势[industry-1]，再次引用[industry-1]。",
            evidence,
        )

        self.assertEqual(result.cited_evidence_ids, ["valuation-2", "industry-1"])
        self.assertEqual(
            result.markdown,
            "估值结论[^1]。\n\n行业趋势[^2]，再次引用[^2]。\n\n"
            "## 参考来源\n\n"
            "[^1]: Example Markets｜Valuation source｜2026-07-11｜"
            "https://example.test/valuation\n"
            "[^2]: Example News｜Industry source｜2026-07-10｜"
            "https://example.test/industry\n",
        )

    def test_render_citations_removes_unknown_markers_without_a_reference_section(self) -> None:
        with self.assertLogs("stockagent.report.citations", level="WARNING") as logs:
            result = render_citations("无来源叙事[unknown-1]仍可交付。", [])

        self.assertEqual(result.markdown, "无来源叙事仍可交付。")
        self.assertEqual(result.cited_evidence_ids, [])
        self.assertIn("unknown-1", logs.output[0])

    def test_render_citations_omits_missing_dates_and_derives_publisher_from_url(self) -> None:
        result = render_citations(
            "外部事实[valuation-1]。",
            [
                Evidence(
                    id="valuation-1",
                    kind="web",
                    title="Market source",
                    url="https://markets.example.test/article",
                    publisher=None,
                    published_date=None,
                    excerpt=None,
                    source_agent="valuation_analyst",
                )
            ],
        )

        self.assertIn(
            "[^1]: markets.example.test｜Market source｜"
            "https://markets.example.test/article",
            result.markdown,
        )
        self.assertNotIn("None", result.markdown)

    def test_render_citations_supports_any_known_evidence_id(self) -> None:
        result = render_citations(
            "外部事实[market-data]。",
            [
                Evidence(
                    id="market-data",
                    kind="web",
                    title="Market source",
                    url="https://markets.example.test/article",
                    source_agent="valuation_analyst",
                )
            ],
        )

        self.assertEqual(result.cited_evidence_ids, ["market-data"])
        self.assertIn("外部事实[^1]。", result.markdown)

    def test_render_citations_preserves_regular_markdown_links(self) -> None:
        markdown = "查看[来源网站](https://example.test)。"

        result = render_citations(markdown, [])

        self.assertEqual(result.markdown, markdown)
        self.assertEqual(result.cited_evidence_ids, [])


if __name__ == "__main__":
    unittest.main()
