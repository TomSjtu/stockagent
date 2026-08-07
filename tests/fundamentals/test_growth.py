from __future__ import annotations

import unittest

from stockagent.financials import FinancialRecord
from stockagent.fundamentals import compute_growth_series


class GrowthMetricsTest(unittest.TestCase):
    def test_compute_growth_series_calculates_yoy_growth_and_cagr(self) -> None:
        records = [
            FinancialRecord(
                "FAKE",
                "Fake Inc.",
                2024,
                revenue=144.0,
                net_income=36.0,
                operating_cash_flow=54.0,
                capex=18.0,
            ),
            FinancialRecord(
                "FAKE",
                "Fake Inc.",
                2022,
                revenue=100.0,
                net_income=25.0,
                operating_cash_flow=35.0,
                capex=10.0,
            ),
            FinancialRecord(
                "FAKE",
                "Fake Inc.",
                2023,
                revenue=120.0,
                net_income=30.0,
                operating_cash_flow=42.0,
                capex=12.0,
            ),
        ]

        metrics = compute_growth_series(records)

        self.assertEqual([item.fiscal_year for item in metrics], [2022, 2023, 2024])
        self.assertIsNone(metrics[0].revenue_growth)
        self.assertAlmostEqual(metrics[1].revenue_growth, 0.2)
        self.assertAlmostEqual(metrics[1].net_income_growth, 0.2)
        self.assertAlmostEqual(metrics[1].free_cash_flow_growth, 0.2)
        self.assertAlmostEqual(metrics[2].revenue_growth, 0.2)
        self.assertAlmostEqual(metrics[2].net_income_growth, 0.2)
        self.assertAlmostEqual(metrics[2].free_cash_flow_growth, 0.2)
        self.assertAlmostEqual(metrics[2].revenue_cagr, 0.2)
        self.assertAlmostEqual(metrics[2].net_income_cagr, 0.2)
        self.assertAlmostEqual(metrics[2].free_cash_flow_cagr, 0.2)

    def test_compute_growth_series_returns_none_for_missing_or_zero_baselines(self) -> None:
        records = [
            FinancialRecord(
                ticker="FAKE",
                company_name="Fake Inc.",
                fiscal_year=2023,
                revenue=0.0,
                net_income=None,
                operating_cash_flow=20.0,
                capex=None,
            ),
            FinancialRecord(
                ticker="FAKE",
                company_name="Fake Inc.",
                fiscal_year=2024,
                revenue=120.0,
                net_income=30.0,
                operating_cash_flow=40.0,
                capex=10.0,
            ),
        ]

        metrics = compute_growth_series(records)

        self.assertIsNone(metrics[1].revenue_growth)
        self.assertIsNone(metrics[1].net_income_growth)
        self.assertIsNone(metrics[1].free_cash_flow_growth)
        self.assertIsNone(metrics[1].revenue_cagr)
        self.assertIsNone(metrics[1].net_income_cagr)
        self.assertIsNone(metrics[1].free_cash_flow_cagr)

    def test_compute_growth_series_returns_empty_list_for_no_inputs(self) -> None:
        self.assertEqual(compute_growth_series([]), [])


if __name__ == "__main__":
    unittest.main()
