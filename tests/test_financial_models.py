from __future__ import annotations

import unittest

from stockagent.financials import (
    AnnualFundamentals,
    CashFlowMetrics,
    FinancialHealthMetrics,
    FinancialRecord,
    GrowthMetrics,
    ProfitabilityMetrics,
    SecFilingReference,
)


class FinancialModelTest(unittest.TestCase):
    def test_annual_fundamentals_accepts_missing_values_for_matching_year(
        self,
    ) -> None:
        record = FinancialRecord("AAPL", "Apple Inc.", 2024)
        profitability = ProfitabilityMetrics(fiscal_year=2024)
        cash_flow = CashFlowMetrics(fiscal_year=2024)
        financial_health = FinancialHealthMetrics(fiscal_year=2024)
        growth = GrowthMetrics(fiscal_year=2024)

        annual_fundamentals = AnnualFundamentals(
            record=record,
            profitability=profitability,
            cash_flow=cash_flow,
            financial_health=financial_health,
            growth=growth,
        )

        self.assertEqual(annual_fundamentals.fiscal_year, 2024)
        self.assertIs(annual_fundamentals.record, record)
        self.assertIs(annual_fundamentals.profitability, profitability)
        self.assertIs(annual_fundamentals.cash_flow, cash_flow)
        self.assertIs(annual_fundamentals.financial_health, financial_health)
        self.assertIs(annual_fundamentals.growth, growth)

    def test_annual_fundamentals_rejects_each_mismatched_fiscal_year(self) -> None:
        matching_parts = {
            "record": FinancialRecord("AAPL", "Apple Inc.", 2024),
            "profitability": ProfitabilityMetrics(fiscal_year=2024),
            "cash_flow": CashFlowMetrics(fiscal_year=2024),
            "financial_health": FinancialHealthMetrics(fiscal_year=2024),
            "growth": GrowthMetrics(fiscal_year=2024),
        }
        mismatched_parts = {
            "record": FinancialRecord("AAPL", "Apple Inc.", 2023),
            "profitability": ProfitabilityMetrics(fiscal_year=2023),
            "cash_flow": CashFlowMetrics(fiscal_year=2023),
            "financial_health": FinancialHealthMetrics(fiscal_year=2023),
            "growth": GrowthMetrics(fiscal_year=2023),
        }

        for part_name, mismatched_part in mismatched_parts.items():
            with self.subTest(part=part_name):
                parts = matching_parts | {part_name: mismatched_part}
                with self.assertRaisesRegex(ValueError, "fiscal year"):
                    AnnualFundamentals(**parts)

    def test_financial_record_accepts_an_optional_sec_filing_reference(self) -> None:
        filing = SecFilingReference(
            form="10-K",
            fiscal_year=2025,
            period_end="2026-01-25",
            filed_at="2026-02-20",
            cik="1045810",
            accession_number="0001045810-26-000010",
            primary_document="nvda-20260125.htm",
            url="https://www.sec.gov/Archives/edgar/data/1045810/"
            "000104581026000010/nvda-20260125.htm",
        )
        record = FinancialRecord(
            ticker="NVDA",
            company_name="NVIDIA Corporation",
            fiscal_year=2025,
            revenue=130.5,
            filing=filing,
        )

        filing_payload = filing.model_dump(mode="json")

        self.assertIs(record.filing, filing)
        self.assertEqual(record.revenue, 130.5)
        self.assertEqual(filing_payload["period_end"], "2026-01-25")
        self.assertEqual(filing_payload["filed_at"], "2026-02-20")


if __name__ == "__main__":
    unittest.main()
