from __future__ import annotations

import unittest
from datetime import date

from stockagent.agents.errors import AgentOutputError
from stockagent.agents.state import (
    Evidence,
    FundamentalsOutput,
    IndustryOutput,
    MarketInputs,
    RiskOutput,
    SynthesisOutput,
    ValuationOutput,
)
from stockagent.financials import AnnualFinancialSnapshot, SecFilingReference
from stockagent.report.delivery import deliver_report


class ReportDeliveryTest(unittest.TestCase):
    def test_deliver_report_constructs_matching_markdown_and_evidence(self) -> None:
        filing = SecFilingReference(
            form="10-K",
            fiscal_year=2024,
            period_end=date(2024, 12, 31),
            filed_at=date(2025, 2, 20),
            cik="320193",
            accession_number="0000320193-25-000001",
            primary_document="annual-report.htm",
            url="https://www.sec.gov/Archives/edgar/data/320193/annual-report.htm",
        )
        market_inputs = MarketInputs(
            price=210.5,
            market_cap=3_200_000_000_000.0,
            currency="USD",
            as_of=date(2026, 7, 28),
            evidence_id="valuation-1",
        )
        state = {
            "ticker": "aapl",
            "years": 2,
            "industry": IndustryOutput(
                narrative="行业正文 [industry-1]",
                evidence=[self._evidence("industry-1", "行业来源", "行业研究院")],
            ),
            "fundamentals": FundamentalsOutput(
                narrative="基本面正文 [sec-2024]",
                concerns=[],
                annual_financials=[
                    AnnualFinancialSnapshot(
                        fiscal_year=2024,
                        revenue=2_000_000_000.0,
                        net_income=180_000_000.0,
                        operating_cash_flow=400_000_000.0,
                        capex=80_000_000.0,
                        free_cash_flow=320_000_000.0,
                        gross_margin=0.45,
                        net_margin=0.09,
                        revenue_growth=0.6,
                    ),
                    AnnualFinancialSnapshot(
                        fiscal_year=2023,
                        revenue=1_250_000_000.0,
                        net_income=100_000_000.0,
                        operating_cash_flow=250_000_000.0,
                        capex=50_000_000.0,
                        free_cash_flow=200_000_000.0,
                        gross_margin=0.4,
                        net_margin=0.08,
                        revenue_growth=None,
                    ),
                ],
                financial_filings=[filing],
            ),
            "valuation": ValuationOutput(
                narrative="估值正文 [valuation-1]",
                evidence=[self._evidence("valuation-1", "估值来源", "市场数据社")],
                market_inputs=market_inputs,
                pe_ratio=30.0,
                pb_ratio=8.0,
                ps_ratio=10.0,
            ),
            "risk": RiskOutput(
                narrative="风险正文 [risk-1]",
                overall_rating="中",
                key_risks=["需求波动"],
                evidence=[self._evidence("risk-1", "风险来源", "风险观察")],
            ),
            "synthesis": SynthesisOutput(
                summary="摘要正文 [risk-1] [unknown-1]",
                investment_recommendation="投资建议正文 [industry-1]",
            ),
            "final_report": "旧报告不应被读取",
            "cited_evidence_ids": ["旧引用不应被读取"],
        }

        delivery = deliver_report(state, report_date=date(2026, 7, 29))

        self.assertTrue(
            delivery.markdown.startswith(
                "# AAPL 研究报告\n\n报告日期：2026-07-29\n\n## 摘要"
            )
        )
        self._assert_section_order(
            delivery.markdown,
            [
                "## 摘要",
                "## 行业分析",
                "## 财务数据快照",
                "## 基本面分析",
                "## 估值分析",
                "## 风险评估",
                "## 投资建议",
                "## 数据口径",
                "## 免责声明",
                "## 参考来源",
            ],
        )
        self.assertIn(
            "| 指标 | 2023（10-K 链接暂不可用） | 2024 [^3] |",
            delivery.markdown,
        )
        self.assertIn("| 收入 | 1,250.0 | 2,000.0 |", delivery.markdown)
        self.assertIn("| 毛利率 | 40.0% | 45.0% |", delivery.markdown)
        self.assertIn("| 收入同比增速 | — | 60.0% |", delivery.markdown)
        self.assertIn(
            "> 数据质量提示：2023 财年的 10-K 链接暂不可用。",
            delivery.markdown,
        )
        self.assertIn("摘要正文 [^1] ", delivery.markdown)
        self.assertNotIn("[unknown-1]", delivery.markdown)
        self.assertIn("行业正文 [^2]", delivery.markdown)
        self.assertIn("风险正文 [^1]", delivery.markdown)
        self.assertIn("投资建议正文 [^2]", delivery.markdown)
        self.assertIn(
            "[^1]: 风险观察｜风险来源｜https://example.test/risk-1",
            delivery.markdown,
        )
        self.assertIn(
            "[^3]: SEC 10-K｜截至 2024-12-31｜Filed 2025-02-20｜"
            "https://www.sec.gov/Archives/edgar/data/320193/annual-report.htm",
            delivery.markdown,
        )
        self.assertEqual(
            [item.id for item in delivery.evidence_bundle.evidence],
            ["industry-1", "valuation-1", "risk-1", "sec-2024"],
        )
        self.assertEqual(
            delivery.evidence_bundle.cited_evidence_ids,
            ["risk-1", "industry-1", "sec-2024", "valuation-1"],
        )
        sec_evidence = delivery.evidence_bundle.evidence[-1]
        self.assertEqual(
            sec_evidence.title,
            "SEC 10-K｜截至 2024-12-31｜Filed 2025-02-20",
        )
        self.assertEqual(sec_evidence.publisher, "SEC")
        self.assertEqual(delivery.evidence_bundle.market_inputs, market_inputs)
        self.assertEqual(delivery.evidence_bundle.financial_filings, [filing])

    def test_deliver_report_rejects_each_missing_required_state_field(self) -> None:
        state = self._complete_state()

        for name in [
            "ticker",
            "industry",
            "fundamentals",
            "valuation",
            "risk",
            "synthesis",
        ]:
            with self.subTest(name=name):
                incomplete_state = {**state}
                del incomplete_state[name]

                with self.assertRaisesRegex(
                    AgentOutputError,
                    f"analysis graph result is missing {name}",
                ):
                    deliver_report(incomplete_state, report_date=date(2026, 7, 29))

    def test_deliver_report_uses_current_date_by_default(self) -> None:
        delivery = deliver_report(self._complete_state())

        self.assertIn(f"报告日期：{date.today().isoformat()}", delivery.markdown)

    def _complete_state(self) -> dict[str, object]:
        return {
            "ticker": "AAPL",
            "years": 3,
            "industry": IndustryOutput(narrative="行业正文", evidence=[]),
            "fundamentals": FundamentalsOutput(
                narrative="基本面正文",
                concerns=[],
            ),
            "valuation": ValuationOutput(narrative="估值正文"),
            "risk": RiskOutput(
                narrative="风险正文",
                overall_rating="低",
                key_risks=[],
                evidence=[],
            ),
            "synthesis": SynthesisOutput(
                summary="摘要正文",
                investment_recommendation="投资建议正文",
            ),
        }

    @staticmethod
    def _evidence(evidence_id: str, title: str, publisher: str) -> Evidence:
        return Evidence(
            id=evidence_id,
            kind="web",
            title=title,
            url=f"https://example.test/{evidence_id}",
            publisher=publisher,
            source_agent=f"{evidence_id.split('-', maxsplit=1)[0]}_analyst",
        )

    def _assert_section_order(self, markdown: str, sections: list[str]) -> None:
        positions = [markdown.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
