from __future__ import annotations

import unittest

from stockagent.financials import FinancialRecord
from stockagent.fundamentals.annual import (
    compute_cash_flow,
    compute_financial_health,
    compute_profitability,
    free_cash_flow,
)


class FreeCashFlowTest(unittest.TestCase):
    def test_returns_difference_for_two_values(self) -> None:
        self.assertEqual(free_cash_flow(35.0, 10.0), 25.0)

    def test_returns_none_when_operating_cash_flow_is_missing(self) -> None:
        self.assertIsNone(free_cash_flow(None, 10.0))

    def test_returns_none_when_capex_is_missing(self) -> None:
        self.assertIsNone(free_cash_flow(35.0, None))

    def test_returns_none_when_both_values_are_missing(self) -> None:
        self.assertIsNone(free_cash_flow(None, None))


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


class CashFlowMetricsTest(unittest.TestCase):
    def test_compute_cash_flow_calculates_free_cash_flow(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            operating_cash_flow=35.0,
            capex=10.0,
        )

        metrics = compute_cash_flow(record)

        self.assertEqual(metrics.free_cash_flow, 25.0)

    def test_compute_cash_flow_returns_none_for_missing_fields(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            operating_cash_flow=35.0,
            capex=None,
        )

        metrics = compute_cash_flow(record)

        self.assertIsNone(metrics.free_cash_flow)


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
