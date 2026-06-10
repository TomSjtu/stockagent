from __future__ import annotations

import unittest

import pandas as pd

from stockagent.data.providers.edgar import EdgarFundamentalsProvider


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


class EdgarFundamentalsProviderTest(unittest.TestCase):
    def test_fetch_annual_records_maps_edgar_dataframes(self) -> None:
        provider = EdgarFundamentalsProvider(company_factory=FakeCompany)

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


if __name__ == "__main__":
    unittest.main()
