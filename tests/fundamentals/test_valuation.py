from __future__ import annotations

import unittest

from stockagent.financials import FinancialRecord
from stockagent.fundamentals import (
    ValuationInput,
    build_valuation_input,
    compute_valuation,
)


class ValuationInputTest(unittest.TestCase):
    def test_from_record_maps_valuation_fields_and_market_inputs(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            revenue=100.0,
            net_income=20.0,
            eps_diluted=2.0,
            shareholders_equity=50.0,
            operating_cash_flow=35.0,
        )

        valuation_input = ValuationInput.from_record(
            record,
            price=40.0,
            market_cap=200.0,
        )

        self.assertEqual(valuation_input.fiscal_year, 2024)
        self.assertEqual(valuation_input.price, 40.0)
        self.assertEqual(valuation_input.market_cap, 200.0)
        self.assertEqual(valuation_input.revenue, 100.0)
        self.assertEqual(valuation_input.net_income, 20.0)
        self.assertEqual(valuation_input.eps_diluted, 2.0)
        self.assertEqual(valuation_input.shareholders_equity, 50.0)


class ValuationMetricsTest(unittest.TestCase):
    def test_compute_valuation_calculates_pe_pb_ps(self) -> None:
        valuation_input = ValuationInput(
            fiscal_year=2024,
            price=40.0,
            market_cap=200.0,
            revenue=100.0,
            net_income=20.0,
            eps_diluted=2.0,
            shareholders_equity=50.0,
        )

        metrics = compute_valuation(valuation_input)

        self.assertEqual(metrics.fiscal_year, 2024)
        self.assertEqual(metrics.stock_price, 40.0)
        self.assertEqual(metrics.market_cap, 200.0)
        self.assertEqual(metrics.pe_ratio, 20.0)
        self.assertEqual(metrics.pb_ratio, 4.0)
        self.assertEqual(metrics.ps_ratio, 2.0)

    def test_compute_valuation_uses_market_cap_pe_fallback(self) -> None:
        valuation_input = ValuationInput(
            fiscal_year=2024,
            price=None,
            market_cap=200.0,
            revenue=100.0,
            net_income=20.0,
            eps_diluted=None,
            shareholders_equity=50.0,
        )

        metrics = compute_valuation(valuation_input)

        self.assertEqual(metrics.pe_ratio, 10.0)
        self.assertEqual(metrics.pb_ratio, 4.0)
        self.assertEqual(metrics.ps_ratio, 2.0)

    def test_compute_valuation_does_not_infer_market_cap_from_price(self) -> None:
        valuation_input = ValuationInput(
            fiscal_year=2024,
            price=40.0,
            market_cap=None,
            revenue=100.0,
            net_income=20.0,
            eps_diluted=2.0,
            shareholders_equity=50.0,
        )

        metrics = compute_valuation(valuation_input)

        self.assertEqual(metrics.pe_ratio, 20.0)
        self.assertIsNone(metrics.pb_ratio)
        self.assertIsNone(metrics.ps_ratio)

    def test_compute_valuation_returns_none_for_non_positive_inputs(self) -> None:
        valuation_input = ValuationInput(
            fiscal_year=2024,
            price=40.0,
            market_cap=200.0,
            revenue=0.0,
            net_income=-5.0,
            eps_diluted=-0.5,
            shareholders_equity=0.0,
        )

        metrics = compute_valuation(valuation_input)

        self.assertIsNone(metrics.pe_ratio)
        self.assertIsNone(metrics.pb_ratio)
        self.assertIsNone(metrics.ps_ratio)

    def test_build_valuation_input_maps_record(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            revenue=100.0,
            net_income=20.0,
            eps_diluted=2.0,
            shareholders_equity=50.0,
        )

        valuation_input = build_valuation_input(
            record,
            price=40.0,
            market_cap=200.0,
        )

        self.assertEqual(valuation_input.fiscal_year, 2024)
        self.assertEqual(valuation_input.price, 40.0)
        self.assertEqual(valuation_input.market_cap, 200.0)


if __name__ == "__main__":
    unittest.main()
