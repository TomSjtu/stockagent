from __future__ import annotations

import unittest

from stockagent.app import AnalysisResult
from stockagent.financials.models import (
    CashFlowMetrics,
    FinancialHealthMetrics,
    FinancialRecord,
    GrowthMetrics,
    ProfitabilityMetrics,
)
from stockagent.report.builder import build_html_report, build_markdown_report, build_report, build_text_report


class ReportBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.result = AnalysisResult(
            ticker="FAKE",
            records=[
                FinancialRecord(
                    ticker="FAKE",
                    company_name="Fake Inc.",
                    fiscal_year=2024,
                    revenue=120.0,
                    gross_profit=48.0,
                    net_income=18.0,
                    operating_cash_flow=30.0,
                )
            ],
            profitability={
                2024: ProfitabilityMetrics(
                    fiscal_year=2024,
                    gross_margin=0.4,
                    roe=0.15,
                )
            },
            cash_flow={
                2024: CashFlowMetrics(
                    fiscal_year=2024,
                    free_cash_flow=20.0,
                )
            },
            financial_health={
                2024: FinancialHealthMetrics(
                    fiscal_year=2024,
                    current_ratio=2.0,
                    cash_ratio=0.8,
                )
            },
            growth={
                2024: GrowthMetrics(
                    fiscal_year=2024,
                    revenue_growth=0.2,
                    net_income_growth=0.15,
                )
            },
        )

    def test_build_text_report_renders_selected_sections(self) -> None:
        output = build_text_report(self.result)

        self.assertIn("Ticker: FAKE", output)
        self.assertIn("=== FY 2024 ===", output)
        self.assertIn("Cash Flow:", output)
        self.assertIn("Profitability:", output)
        self.assertIn("Financial Health:", output)
        self.assertIn("Growth:", output)
        self.assertIn("20", output)

    def test_build_markdown_report_renders_heading(self) -> None:
        output = build_markdown_report(self.result)

        self.assertEqual(output, "")

    def test_build_html_report_renders_html_shell(self) -> None:
        output = build_html_report(self.result)

        self.assertEqual(output, "")

    def test_build_report_raises_for_markdown(self) -> None:
        with self.assertRaises(NotImplementedError):
            build_report(self.result, "md")

    def test_build_report_raises_for_html(self) -> None:
        with self.assertRaises(NotImplementedError):
            build_report(self.result, "html")


if __name__ == "__main__":
    unittest.main()
