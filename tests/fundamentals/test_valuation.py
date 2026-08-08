from __future__ import annotations

import unittest

from stockagent.financials import FinancialRecord
from stockagent.fundamentals import compute_valuation


class ValuationMetricsTest(unittest.TestCase):
    def test_compute_valuation_calculates_pe_pb_ps(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            revenue=100.0,
            net_income=20.0,
            eps_diluted=2.0,
            shareholders_equity=50.0,
        )

        metrics = compute_valuation(record, price=40.0, market_cap=200.0)

        self.assertEqual(metrics.fiscal_year, 2024)
        self.assertEqual(metrics.stock_price, 40.0)
        self.assertEqual(metrics.market_cap, 200.0)
        self.assertEqual(metrics.pe_ratio, 20.0)
        self.assertEqual(metrics.pb_ratio, 4.0)
        self.assertEqual(metrics.ps_ratio, 2.0)

    def test_compute_valuation_uses_market_cap_pe_fallback(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            revenue=100.0,
            net_income=20.0,
            eps_diluted=None,
            shareholders_equity=50.0,
        )

        metrics = compute_valuation(record, price=None, market_cap=200.0)

        self.assertEqual(metrics.pe_ratio, 10.0)
        self.assertEqual(metrics.pb_ratio, 4.0)
        self.assertEqual(metrics.ps_ratio, 2.0)

    def test_compute_valuation_does_not_infer_market_cap_from_price(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            revenue=100.0,
            net_income=20.0,
            eps_diluted=2.0,
            shareholders_equity=50.0,
        )

        metrics = compute_valuation(record, price=40.0, market_cap=None)

        self.assertEqual(metrics.pe_ratio, 20.0)
        self.assertIsNone(metrics.pb_ratio)
        self.assertIsNone(metrics.ps_ratio)

    def test_compute_valuation_returns_none_for_non_positive_inputs(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            revenue=0.0,
            net_income=-5.0,
            eps_diluted=-0.5,
            shareholders_equity=0.0,
        )

        metrics = compute_valuation(record, price=40.0, market_cap=200.0)

        self.assertIsNone(metrics.pe_ratio)
        self.assertIsNone(metrics.pb_ratio)
        self.assertIsNone(metrics.ps_ratio)


if __name__ == "__main__":
    unittest.main()
