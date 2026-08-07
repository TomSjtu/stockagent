from __future__ import annotations

import unittest

from stockagent.financials import FinancialRecord
from stockagent.fundamentals import compute_financial_health


class FinancialHealthMetricsTest(unittest.TestCase):
    def test_compute_financial_health_calculates_ratios(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            total_assets=200.0,
            current_assets=80.0,
            cash_and_equivalents=30.0,
            total_liabilities=120.0,
            current_liabilities=40.0,
            shareholders_equity=80.0,
            operating_cash_flow=24.0,
        )

        metrics = compute_financial_health(record)

        self.assertEqual(metrics.equity_ratio, 0.4)
        self.assertEqual(metrics.liabilities_to_assets, 0.6)
        self.assertEqual(metrics.current_ratio, 2.0)
        self.assertEqual(metrics.cash_ratio, 0.75)
        self.assertEqual(metrics.operating_cash_flow_to_total_liabilities, 0.2)

    def test_compute_financial_health_returns_none_for_missing_or_zero_denominators(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            total_assets=0.0,
            current_assets=80.0,
            cash_and_equivalents=30.0,
            total_liabilities=0.0,
            current_liabilities=0.0,
            shareholders_equity=80.0,
            operating_cash_flow=24.0,
        )

        metrics = compute_financial_health(record)

        self.assertIsNone(metrics.equity_ratio)
        self.assertIsNone(metrics.liabilities_to_assets)
        self.assertIsNone(metrics.current_ratio)
        self.assertIsNone(metrics.cash_ratio)
        self.assertIsNone(metrics.operating_cash_flow_to_total_liabilities)


if __name__ == "__main__":
    unittest.main()
