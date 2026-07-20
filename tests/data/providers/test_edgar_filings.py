from __future__ import annotations

import unittest
from datetime import date

from stockagent.data.providers.edgar_filings import resolve_annual_filings


class FakeFiling:
    def __init__(
        self,
        *,
        form: str,
        report_date: str,
        filing_date: str,
        cik: int,
        accession_number: str,
        primary_document: str,
    ) -> None:
        self.form = form
        self.report_date = report_date
        self.filing_date = filing_date
        self.cik = cik
        self.accession_number = accession_number
        self.primary_document = primary_document


class FakeCompany:
    def __init__(self, filings: list[FakeFiling]) -> None:
        self.filings = filings
        self.calls: list[dict[str, object]] = []

    def get_filings(self, **kwargs: object) -> list[FakeFiling]:
        self.calls.append(kwargs)
        return self.filings


class EdgarAnnualFilingsTest(unittest.TestCase):
    def test_resolve_annual_filings_builds_reference_for_matching_10_k(self) -> None:
        company = FakeCompany(
            [
                FakeFiling(
                    form="10-K",
                    report_date="2025-01-26",
                    filing_date="2025-02-26",
                    cik=1045810,
                    accession_number="0001045810-25-000021",
                    primary_document="nvda-20250126.htm",
                )
            ]
        )

        references = resolve_annual_filings(company, {2025})

        self.assertEqual(company.calls, [{"form": "10-K", "amendments": True}])
        self.assertEqual(set(references), {2025})
        reference = references[2025]
        self.assertEqual(reference.form, "10-K")
        self.assertEqual(reference.period_end, date(2025, 1, 26))
        self.assertEqual(reference.filed_at, date(2025, 2, 26))
        self.assertEqual(reference.cik, "1045810")
        self.assertEqual(reference.accession_number, "0001045810-25-000021")
        self.assertEqual(reference.primary_document, "nvda-20250126.htm")
        self.assertEqual(
            reference.url,
            "https://www.sec.gov/Archives/edgar/data/1045810/"
            "000104581025000021/nvda-20250126.htm",
        )

    def test_resolve_annual_filings_prefers_latest_amendment_for_same_period(self) -> None:
        company = FakeCompany(
            [
                FakeFiling(
                    form="10-K",
                    report_date="2024-12-31",
                    filing_date="2025-02-20",
                    cik=123456,
                    accession_number="0000123456-25-000001",
                    primary_document="annual.htm",
                ),
                FakeFiling(
                    form="10-K/A",
                    report_date="2024-12-31",
                    filing_date="2025-03-15",
                    cik=123456,
                    accession_number="0000123456-25-000002",
                    primary_document="annual-amendment.htm",
                ),
            ]
        )

        references = resolve_annual_filings(company, {2024})

        self.assertEqual(references[2024].form, "10-K/A")
        self.assertEqual(
            references[2024].accession_number,
            "0000123456-25-000002",
        )

    def test_resolve_annual_filings_omits_incomplete_metadata(self) -> None:
        company = FakeCompany(
            [
                FakeFiling(
                    form="10-K",
                    report_date="2024-12-31",
                    filing_date="2025-02-20",
                    cik=123456,
                    accession_number="0000123456-25-000001",
                    primary_document="",
                )
            ]
        )

        references = resolve_annual_filings(company, {2024})

        self.assertEqual(references, {})


if __name__ == "__main__":
    unittest.main()
