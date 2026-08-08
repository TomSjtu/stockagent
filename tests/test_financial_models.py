from __future__ import annotations

import unittest

from stockagent.financials import FinancialRecord, SecFilingReference


class FinancialModelTest(unittest.TestCase):
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
