from __future__ import annotations

import unittest

from stockagent.financials.models import FundamentalRecord
from stockagent.fundamentals.inputs import ProfitabilityInput, build_profitability_inputs
from stockagent.fundamentals.profitability import (
    compute_profitability,
    compute_profitability_series,
)


class ProfitabilityInputTest(unittest.TestCase):
    def test_from_record_maps_only_profitability_fields(self) -> None:
        record = FundamentalRecord(
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
            operating_cash_flow=35.0,
        )

        profitability_input = ProfitabilityInput.from_record(record)

        self.assertEqual(profitability_input.fiscal_year, 2024)
        self.assertEqual(profitability_input.revenue, 100.0)
        self.assertEqual(profitability_input.gross_profit, 40.0)
        self.assertEqual(profitability_input.operating_income, 30.0)
        self.assertEqual(profitability_input.net_income, 20.0)
        self.assertEqual(profitability_input.rd_expense, 5.0)
        self.assertEqual(profitability_input.sga_expense, 10.0)
        self.assertEqual(profitability_input.total_assets, 200.0)
        self.assertEqual(profitability_input.current_liabilities, 50.0)
        self.assertEqual(profitability_input.shareholders_equity, 100.0)


class ProfitabilityMetricsTest(unittest.TestCase):
    def test_compute_profitability_calculates_ratios(self) -> None:
        profitability_input = ProfitabilityInput(
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

        metrics = compute_profitability(profitability_input)

        self.assertEqual(metrics.gross_margin, 0.4)
        self.assertEqual(metrics.operating_margin, 0.3)
        self.assertEqual(metrics.net_margin, 0.2)
        self.assertEqual(metrics.rd_ratio, 0.05)
        self.assertEqual(metrics.sga_ratio, 0.1)
        self.assertEqual(metrics.roa, 0.1)
        self.assertEqual(metrics.roe, 0.2)
        self.assertEqual(metrics.roce, 0.2)

    def test_compute_profitability_returns_none_for_missing_or_zero_denominators(self) -> None:
        profitability_input = ProfitabilityInput(
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

        metrics = compute_profitability(profitability_input)

        self.assertIsNone(metrics.gross_margin)
        self.assertIsNone(metrics.operating_margin)
        self.assertIsNone(metrics.net_margin)
        self.assertIsNone(metrics.rd_ratio)
        self.assertIsNone(metrics.sga_ratio)
        self.assertIsNone(metrics.roa)
        self.assertIsNone(metrics.roe)
        self.assertIsNone(metrics.roce)

    def test_compute_profitability_series_sorts_by_fiscal_year(self) -> None:
        records = [
            FundamentalRecord("FAKE", "Fake Inc.", 2024, revenue=100.0),
            FundamentalRecord("FAKE", "Fake Inc.", 2023, revenue=90.0),
        ]

        inputs = build_profitability_inputs(records)
        metrics = compute_profitability_series(inputs)

        self.assertEqual([item.fiscal_year for item in metrics], [2023, 2024])


if __name__ == "__main__":
    unittest.main()
