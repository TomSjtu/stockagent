from __future__ import annotations

import unittest
from datetime import date

from stockagent.financials import AnnualFinancialSnapshot, SecFilingReference
from stockagent.report.composer import (
    ReportComposer,
    ReportContent,
)


class ReportComposerTest(unittest.TestCase):
    def test_compose_renders_fixed_sections_and_sorted_financial_snapshot(self) -> None:
        markdown = ReportComposer().compose(
            ReportContent(
                ticker="aapl",
                report_date=date(2026, 7, 22),
                summary="摘要正文 [summary-1]",
                industry_analysis="行业正文 [industry-1]",
                fundamentals_analysis="基本面正文 [sec-2022]",
                valuation_analysis="估值正文 [valuation-1]",
                risk_assessment="风险正文 [risk-1]",
                investment_recommendation="投资建议正文 [recommendation-1]",
                annual_financials=[
                    AnnualFinancialSnapshot(
                        fiscal_year=2024,
                        revenue=2_000_000_000,
                        net_income=180_000_000,
                        operating_cash_flow=400_000_000,
                        capex=80_000_000,
                        free_cash_flow=320_000_000,
                        gross_margin=0.45,
                        net_margin=0.09,
                        revenue_growth=0.2,
                    ),
                    AnnualFinancialSnapshot(
                        fiscal_year=2022,
                        revenue=1_250_000_000,
                        net_income=100_000_000,
                        operating_cash_flow=250_000_000,
                        capex=50_000_000,
                        free_cash_flow=200_000_000,
                        gross_margin=0.4,
                        net_margin=0.08,
                        revenue_growth=None,
                    ),
                ],
                financial_filings=[
                    self._filing(2024),
                    self._filing(2022),
                ],
            )
        )

        self.assertTrue(markdown.startswith("# AAPL 研究报告\n\n报告日期：2026-07-22"))
        self._assert_section_order(
            markdown,
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
            ],
        )
        self.assertEqual(markdown.count("## 财务数据快照"), 1)
        self.assertIn("| 指标 | 2022 [sec-2022] | 2024 [sec-2024] |", markdown)
        self.assertIn("| 收入 | 1,250.0 | 2,000.0 |", markdown)
        self.assertIn("| 资本开支（支出） | 50.0 | 80.0 |", markdown)
        self.assertIn("| 毛利率 | 40.0% | 45.0% |", markdown)
        self.assertIn("| 收入同比增速 | — | 20.0% |", markdown)
        self.assertIn(
            "财务数据覆盖请求的完整财年 10-K/10-K/A，未纳入最新 10-Q 与 TTM；金额单位为百万美元。",
            markdown,
        )
        self.assertIn("本报告仅用于研究和学习，不构成投资建议。", markdown)
        self.assertIn("摘要正文 [summary-1]", markdown)
        self.assertIn("行业正文 [industry-1]", markdown)
        self.assertIn("基本面正文 [sec-2022]", markdown)
        self.assertIn("估值正文 [valuation-1]", markdown)
        self.assertIn("风险正文 [risk-1]", markdown)
        self.assertIn("投资建议正文 [recommendation-1]", markdown)

    def test_compose_keeps_report_available_when_values_or_filing_are_missing(self) -> None:
        markdown = ReportComposer().compose(
            ReportContent(
                ticker="msft",
                report_date=date(2026, 7, 22),
                summary="摘要",
                industry_analysis="行业",
                fundamentals_analysis="基本面",
                valuation_analysis="估值",
                risk_assessment="风险",
                investment_recommendation="建议",
                annual_financials=[AnnualFinancialSnapshot(fiscal_year=2024)],
                financial_filings=[],
            )
        )

        self.assertIn("| 指标 | 2024（10-K 链接暂不可用） |", markdown)
        self.assertEqual(markdown.count("| — |"), 8)
        self.assertIn(
            "> 数据质量提示：2024 财年的 10-K 链接暂不可用。",
            markdown,
        )
        self.assertIn("## 免责声明", markdown)

    def _assert_section_order(self, markdown: str, sections: list[str]) -> None:
        positions = [markdown.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))

    def _filing(self, fiscal_year: int) -> SecFilingReference:
        return SecFilingReference(
            form="10-K",
            fiscal_year=fiscal_year,
            period_end=date(fiscal_year, 12, 31),
            filed_at=date(fiscal_year + 1, 2, 20),
            cik="320193",
            accession_number=f"0000320193-{fiscal_year + 1}-000001",
            primary_document="annual-report.htm",
            url="https://www.sec.gov/Archives/edgar/data/320193/annual-report.htm",
        )


if __name__ == "__main__":
    unittest.main()
