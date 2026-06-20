from __future__ import annotations

import unittest

import pandas as pd

from stockagent.data.errors import NoDataError, ProviderResponseError
from stockagent.data.providers.edgar import EdgarFinancialsProvider


class FakeCompany:
    def __init__(self, ticker: str) -> None:
        self.ticker = ticker

    def get_ticker(self) -> str:
        return self.ticker

    def income_statement(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "FY 2024": [100.0, 40.0, 20.0],
                "FY 2023": [80.0, 30.0, 10.0],
            },
            index=[
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "GrossProfit",
                "NetIncomeLoss",
            ],
        )

    def balance_sheet(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "FY 2024": [200.0, 50.0, 100.0],
                "FY 2023": [180.0, 45.0, 90.0],
            },
            index=[
                "Assets",
                "LiabilitiesCurrent",
                "StockholdersEquity",
            ],
        )

    def cashflow_statement(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "FY 2024": [35.0, 10.0],
                "FY 2023": [25.0, 8.0],
            },
            index=[
                "NetCashProvidedByUsedInOperatingActivities",
                "PaymentsToAcquirePropertyPlantAndEquipment",
            ],
        )


class AliasFallbackCompany(FakeCompany):
    def income_statement(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            {"FY 2024": [100.0, 40.0]},
            index=[
                "Revenues",
                "NetIncomeLoss",
            ],
        )


class PrimaryPriorityCompany(FakeCompany):
    def income_statement(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            {"FY 2024": [100.0, 90.0]},
            index=[
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
            ],
        )


class NullFallbackCompany(FakeCompany):
    def income_statement(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            {"FY 2024": [None, 95.0]},
            index=[
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
            ],
        )


class DuplicateConceptCompany(FakeCompany):
    def income_statement(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            {"FY 2024": [None, 105.0]},
            index=[
                "Revenues",
                "Revenues",
            ],
        )


class MissingConceptCompany(FakeCompany):
    def income_statement(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            {"FY 2024": [20.0]},
            index=["NetIncomeLoss"],
        )


class EmptyPeriodsCompany(FakeCompany):
    def income_statement(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame({"TTM": [100.0]}, index=["Revenues"])


class BrokenCompany(FakeCompany):
    def income_statement(self, **_: object) -> pd.DataFrame:
        raise RuntimeError("edgar response changed")


class EdgarFinancialsProviderTest(unittest.TestCase):
    def test_fetch_annual_records_maps_edgar_dataframes(self) -> None:
        provider = EdgarFinancialsProvider(company_factory=FakeCompany)

        records = provider.fetch_annual_records("FAKE", years=2)

        self.assertEqual([record.fiscal_year for record in records], [2023, 2024])
        self.assertEqual(records[1].ticker, "FAKE")
        self.assertEqual(records[1].revenue, 100.0)
        self.assertEqual(records[1].gross_profit, 40.0)
        self.assertEqual(records[1].net_income, 20.0)
        self.assertEqual(records[1].total_assets, 200.0)
        self.assertEqual(records[1].current_liabilities, 50.0)
        self.assertEqual(records[1].shareholders_equity, 100.0)
        self.assertEqual(records[1].operating_cash_flow, 35.0)
        self.assertEqual(records[1].capex, 10.0)

    def test_fetch_annual_records_uses_alias_when_primary_concept_missing(self) -> None:
        provider = EdgarFinancialsProvider(company_factory=AliasFallbackCompany)

        records = provider.fetch_annual_records("FAKE", years=1)

        self.assertEqual(records[0].revenue, 100.0)

    def test_fetch_annual_records_prefers_primary_concept(self) -> None:
        provider = EdgarFinancialsProvider(company_factory=PrimaryPriorityCompany)

        records = provider.fetch_annual_records("FAKE", years=1)

        self.assertEqual(records[0].revenue, 100.0)

    def test_fetch_annual_records_falls_back_when_primary_value_is_null(self) -> None:
        provider = EdgarFinancialsProvider(company_factory=NullFallbackCompany)

        records = provider.fetch_annual_records("FAKE", years=1)

        self.assertEqual(records[0].revenue, 95.0)

    def test_fetch_annual_records_uses_first_non_null_duplicate_concept(self) -> None:
        provider = EdgarFinancialsProvider(company_factory=DuplicateConceptCompany)

        records = provider.fetch_annual_records("FAKE", years=1)

        self.assertEqual(records[0].revenue, 105.0)

    def test_fetch_annual_records_keeps_field_none_when_all_concepts_missing(self) -> None:
        provider = EdgarFinancialsProvider(company_factory=MissingConceptCompany)

        records = provider.fetch_annual_records("FAKE", years=1)

        self.assertIsNone(records[0].revenue)
        self.assertEqual(records[0].net_income, 20.0)

    def test_fetch_annual_records_raises_no_data_when_no_fiscal_periods(self) -> None:
        provider = EdgarFinancialsProvider(company_factory=EmptyPeriodsCompany)

        with self.assertRaises(NoDataError) as context:
            provider.fetch_annual_records("FAKE", years=1)

        self.assertEqual(context.exception.ticker, "FAKE")
        self.assertEqual(context.exception.provider, "edgar")

    def test_fetch_annual_records_wraps_unexpected_provider_errors(self) -> None:
        provider = EdgarFinancialsProvider(company_factory=BrokenCompany)

        with self.assertRaises(ProviderResponseError) as context:
            provider.fetch_annual_records("FAKE", years=1)

        self.assertEqual(context.exception.ticker, "FAKE")
        self.assertEqual(context.exception.provider, "edgar")
        self.assertIn("edgar response changed", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
