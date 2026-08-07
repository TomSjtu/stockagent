from __future__ import annotations

import unittest

from stockagent.financials import FinancialRecord
from stockagent.fundamentals import compute_profitability


class ProfitabilityMetricsTest(unittest.TestCase):
    def test_compute_profitability_calculates_ratios(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            revenue=100.0,
            gross_profit=40.0,
            operating_income=30.0,
            net_income=20.0,
            rd_expense=5.0,
            sga_expense=10.0,
            total_assets=200.0,
            current_liabilities=50.0,
            shareholders_equity=100.0,
        )

        metrics = compute_profitability(record)

        self.assertEqual(metrics.gross_margin, 0.4)
        self.assertEqual(metrics.operating_margin, 0.3)
        self.assertEqual(metrics.net_margin, 0.2)
        self.assertEqual(metrics.rd_ratio, 0.05)
        self.assertEqual(metrics.sga_ratio, 0.1)
        self.assertEqual(metrics.roa, 0.1)
        self.assertEqual(metrics.roe, 0.2)
        self.assertEqual(metrics.roce, 0.2)

    def test_compute_profitability_returns_none_for_missing_or_zero_denominators(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            revenue=0.0,
            gross_profit=40.0,
            operating_income=30.0,
            net_income=None,
            rd_expense=5.0,
            sga_expense=10.0,
            total_assets=0.0,
            current_liabilities=0.0,
            shareholders_equity=0.0,
        )

        metrics = compute_profitability(record)

        self.assertIsNone(metrics.gross_margin)
        self.assertIsNone(metrics.operating_margin)
        self.assertIsNone(metrics.net_margin)
        self.assertIsNone(metrics.rd_ratio)
        self.assertIsNone(metrics.sga_ratio)
        self.assertIsNone(metrics.roa)
        self.assertIsNone(metrics.roe)
        self.assertIsNone(metrics.roce)


if __name__ == "__main__":
    unittest.main()
