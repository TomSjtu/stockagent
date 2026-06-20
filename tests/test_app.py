from __future__ import annotations

import unittest

from stockagent.app import run_stock_analysis
from stockagent.config import AppConfig, RuntimeOptions
from stockagent.data.errors import NoDataError
from stockagent.financials.models import FinancialRecord


class FakeProvider:
    def fetch_annual_records(
        self,
        ticker: str,
        years: int,
    ) -> list[FinancialRecord]:
        self.last_ticker = ticker
        self.last_years = years
        return [
            FinancialRecord(
                ticker=ticker,
                company_name="Fake Inc.",
                fiscal_year=2024,
                revenue=120.0,
                gross_profit=48.0,
                operating_income=24.0,
                net_income=18.0,
                total_assets=200.0,
                total_liabilities=80.0,
                current_assets=70.0,
                current_liabilities=35.0,
                shareholders_equity=120.0,
                operating_cash_flow=30.0,
                capex=10.0,
            ),
            FinancialRecord(
                ticker=ticker,
                company_name="Fake Inc.",
                fiscal_year=2023,
                revenue=100.0,
                gross_profit=40.0,
                operating_income=20.0,
                net_income=15.0,
                total_assets=180.0,
                total_liabilities=75.0,
                current_assets=60.0,
                current_liabilities=30.0,
                shareholders_equity=105.0,
                operating_cash_flow=24.0,
                capex=8.0,
            ),
        ]


class EmptyProvider:
    def fetch_annual_records(
        self,
        ticker: str,
        years: int,
    ) -> list[FinancialRecord]:
        return []


class RunStockAnalysisTest(unittest.TestCase):
    def test_run_stock_analysis_builds_all_default_sections(self) -> None:
        provider = FakeProvider()
        calls: list[str] = []
        options = RuntimeOptions(
            ticker="fake",
            years=2,
        )
        config = AppConfig(edgar_identity="tester@example.com")

        result = run_stock_analysis(
            options,
            config,
            provider=provider,
            identity_setter=calls.append,
        )

        self.assertEqual(calls, ["tester@example.com"])
        self.assertEqual(provider.last_ticker, "FAKE")
        self.assertEqual(provider.last_years, 2)
        self.assertEqual(result.ticker, "FAKE")
        self.assertIsNotNone(result.profitability)
        self.assertIsNotNone(result.cash_flow)
        self.assertIsNotNone(result.financial_health)
        self.assertIsNotNone(result.growth)
        self.assertEqual(result.cash_flow[2024].free_cash_flow, 20.0)
        self.assertAlmostEqual(result.profitability[2024].gross_margin, 0.4)
        self.assertAlmostEqual(result.financial_health[2024].current_ratio, 2.0)
        self.assertAlmostEqual(result.growth[2024].revenue_growth, 0.2)

    def test_run_stock_analysis_raises_no_data_when_provider_returns_empty_records(
        self,
    ) -> None:
        options = RuntimeOptions(
            ticker="fake",
            years=2,
        )
        config = AppConfig(edgar_identity="tester@example.com")

        with self.assertRaises(NoDataError) as context:
            run_stock_analysis(
                options,
                config,
                provider=EmptyProvider(),
                identity_setter=lambda _: None,
            )

        self.assertEqual(context.exception.ticker, "FAKE")
        self.assertEqual(context.exception.provider, "EmptyProvider")


if __name__ == "__main__":
    unittest.main()
