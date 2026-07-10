from __future__ import annotations

import unittest

from stockagent import api
from stockagent.financials import FinancialRecord


class ApiTest(unittest.TestCase):
    def test_compute_valuation_uses_latest_fiscal_year(self) -> None:
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

        metrics = api.compute_valuation(records, price=40.0, market_cap=200.0)

        self.assertEqual(metrics.fiscal_year, 2024)
        self.assertEqual(metrics.pe_ratio, 20.0)
        self.assertEqual(metrics.pb_ratio, 4.0)
        self.assertEqual(metrics.ps_ratio, 2.0)


if __name__ == "__main__":
    unittest.main()
