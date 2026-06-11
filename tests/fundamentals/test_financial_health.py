from __future__ import annotations

import unittest

from stockagent.financials.models import FinancialRecord
from stockagent.fundamentals.financial_health import (
    compute_financial_health,
    compute_financial_health_series,
)
from stockagent.fundamentals.inputs import (
    FinancialHealthInput,
    build_financial_health_inputs,
)


class FinancialHealthInputTest(unittest.TestCase):
    def test_from_record_maps_only_financial_health_fields(self) -> None:
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
            revenue=100.0,
        )

        financial_health_input = FinancialHealthInput.from_record(record)

        self.assertEqual(financial_health_input.fiscal_year, 2024)
        self.assertEqual(financial_health_input.total_assets, 200.0)
        self.assertEqual(financial_health_input.current_assets, 80.0)
        self.assertEqual(financial_health_input.cash_and_equivalents, 30.0)
        self.assertEqual(financial_health_input.total_liabilities, 120.0)
        self.assertEqual(financial_health_input.current_liabilities, 40.0)
        self.assertEqual(financial_health_input.shareholders_equity, 80.0)
        self.assertEqual(financial_health_input.operating_cash_flow, 24.0)


class FinancialHealthMetricsTest(unittest.TestCase):
    def test_compute_financial_health_calculates_ratios(self) -> None:
        financial_health_input = FinancialHealthInput(
            fiscal_year=2024,
            total_assets=200.0,
            current_assets=80.0,
            cash_and_equivalents=30.0,
            total_liabilities=120.0,
            current_liabilities=40.0,
            shareholders_equity=80.0,
            operating_cash_flow=24.0,
        )

        metrics = compute_financial_health(financial_health_input)

        self.assertEqual(metrics.equity_ratio, 0.4)
        self.assertEqual(metrics.liabilities_to_assets, 0.6)
        self.assertEqual(metrics.current_ratio, 2.0)
        self.assertEqual(metrics.cash_ratio, 0.75)
        self.assertEqual(metrics.operating_cash_flow_to_total_liabilities, 0.2)

    def test_compute_financial_health_returns_none_for_missing_or_zero_denominators(self) -> None:
        financial_health_input = FinancialHealthInput(
            fiscal_year=2024,
            total_assets=0.0,
            current_assets=80.0,
            cash_and_equivalents=30.0,
            total_liabilities=0.0,
            current_liabilities=0.0,
            shareholders_equity=80.0,
            operating_cash_flow=24.0,
        )

        metrics = compute_financial_health(financial_health_input)

        self.assertIsNone(metrics.equity_ratio)
        self.assertIsNone(metrics.liabilities_to_assets)
        self.assertIsNone(metrics.current_ratio)
        self.assertIsNone(metrics.cash_ratio)
        self.assertIsNone(metrics.operating_cash_flow_to_total_liabilities)

    def test_compute_financial_health_series_sorts_by_fiscal_year(self) -> None:
        records = [
            FinancialRecord(
                "FAKE",
                "Fake Inc.",
                2024,
                total_assets=200.0,
                current_assets=80.0,
                cash_and_equivalents=30.0,
                total_liabilities=120.0,
                current_liabilities=40.0,
                shareholders_equity=80.0,
                operating_cash_flow=24.0,
            ),
            FinancialRecord(
                "FAKE",
                "Fake Inc.",
                2023,
                total_assets=180.0,
                current_assets=72.0,
                cash_and_equivalents=24.0,
                total_liabilities=108.0,
                current_liabilities=36.0,
                shareholders_equity=72.0,
                operating_cash_flow=18.0,
            ),
        ]

        inputs = build_financial_health_inputs(records)
        metrics = compute_financial_health_series(inputs)

        self.assertEqual([item.fiscal_year for item in metrics], [2023, 2024])
        self.assertEqual(metrics[0].current_ratio, 2.0)
        self.assertEqual(metrics[1].operating_cash_flow_to_total_liabilities, 0.2)


if __name__ == "__main__":
    unittest.main()
