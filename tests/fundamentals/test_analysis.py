from __future__ import annotations

import unittest
from unittest.mock import patch

from stockagent.fundamentals import analysis
from stockagent.data.errors import MissingFiscalYearsError, NoDataError
from stockagent.financials import FinancialRecord


class AnalysisTest(unittest.TestCase):
    def test_fetch_financials_rejects_invalid_years(self) -> None:
        for years in (0, -1, 1.5, "3", True):
            with self.subTest(years=years):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    analysis.fetch_financials("aapl", years)

    def test_fetch_financials_normalizes_ticker_and_returns_sorted_window(self) -> None:
        records = [
            FinancialRecord(ticker="aapl", company_name="Apple Inc.", fiscal_year=2025),
            FinancialRecord(ticker="aapl", company_name="Apple Inc.", fiscal_year=2023),
            FinancialRecord(ticker="aapl", company_name="Apple Inc.", fiscal_year=2022),
            FinancialRecord(ticker="aapl", company_name="Apple Inc.", fiscal_year=2024),
        ]

        with (
            patch("edgar.set_identity"),
            patch("stockagent.data.providers.EdgarFinancialsProvider") as provider_type,
        ):
            provider_type.return_value.fetch_annual_records.return_value = records

            result = analysis.fetch_financials("contractsort", 3)

        self.assertIsInstance(result, tuple)
        self.assertEqual([record.fiscal_year for record in result], [2023, 2024, 2025])
        self.assertEqual([record.ticker for record in result], ["CONTRACTSORT"] * 3)
        provider_type.return_value.fetch_annual_records.assert_called_once_with(
            "CONTRACTSORT",
            years=3,
        )

    def test_fetch_financials_raises_missing_fiscal_years_error_for_gaps(self) -> None:
        records = [
            FinancialRecord(ticker="gap", company_name="Gap Inc.", fiscal_year=2025),
            FinancialRecord(ticker="gap", company_name="Gap Inc.", fiscal_year=2023),
        ]

        with (
            patch("edgar.set_identity"),
            patch("stockagent.data.providers.EdgarFinancialsProvider") as provider_type,
        ):
            provider_type.return_value.fetch_annual_records.return_value = records

            with self.assertRaises(MissingFiscalYearsError) as raised:
                analysis.fetch_financials("contractgap", 3)

        self.assertEqual(raised.exception.ticker, "CONTRACTGAP")
        self.assertEqual(raised.exception.provider, "edgar")
        self.assertEqual(raised.exception.missing_fiscal_years, (2024,))

    def test_fetch_financials_preserves_records_with_missing_fields(self) -> None:
        records = [
            FinancialRecord(
                ticker="fields",
                company_name="Fields Inc.",
                fiscal_year=2025,
                revenue=None,
            ),
        ]

        with (
            patch("edgar.set_identity"),
            patch("stockagent.data.providers.EdgarFinancialsProvider") as provider_type,
        ):
            provider_type.return_value.fetch_annual_records.return_value = records

            result = analysis.fetch_financials("contractfields", 1)

        self.assertIsNone(result[0].revenue)

    def test_fetch_financials_uses_stable_provider_for_no_data_error(self) -> None:
        with (
            patch("edgar.set_identity"),
            patch("stockagent.data.providers.EdgarFinancialsProvider") as provider_type,
        ):
            provider_type.return_value.fetch_annual_records.return_value = []

            with self.assertRaises(NoDataError) as raised:
                analysis.fetch_financials("contractempty", 1)

        self.assertEqual(raised.exception.ticker, "CONTRACTEMPTY")
        self.assertEqual(raised.exception.provider, "edgar")

    def test_fetch_financials_caches_provider_response_after_missing_years_error(
        self,
    ) -> None:
        records = [
            FinancialRecord(
                ticker="cache", company_name="Cache Inc.", fiscal_year=2025
            ),
            FinancialRecord(
                ticker="cache", company_name="Cache Inc.", fiscal_year=2023
            ),
        ]

        with (
            patch("edgar.set_identity"),
            patch("stockagent.data.providers.EdgarFinancialsProvider") as provider_type,
        ):
            provider_type.return_value.fetch_annual_records.return_value = records

            for _ in range(2):
                with self.assertRaises(MissingFiscalYearsError):
                    analysis.fetch_financials("contractcache", 3)

        provider_type.return_value.fetch_annual_records.assert_called_once_with(
            "CONTRACTCACHE",
            years=3,
        )

    def test_analyze_valuation_uses_latest_fiscal_year(self) -> None:
        records = (
            FinancialRecord(
                ticker="AAPL",
                company_name="Apple Inc.",
                fiscal_year=2023,
                revenue=90.0,
                net_income=18.0,
                eps_diluted=1.8,
                shareholders_equity=45.0,
            ),
            FinancialRecord(
                ticker="AAPL",
                company_name="Apple Inc.",
                fiscal_year=2024,
                revenue=100.0,
                net_income=20.0,
                eps_diluted=2.0,
                shareholders_equity=50.0,
            ),
        )

        metrics = analysis.analyze_valuation(records, price=40.0, market_cap=200.0)

        self.assertEqual(metrics.fiscal_year, 2024)
        self.assertEqual(metrics.pe_ratio, 20.0)
        self.assertEqual(metrics.pb_ratio, 4.0)
        self.assertEqual(metrics.ps_ratio, 2.0)


if __name__ == "__main__":
    unittest.main()
