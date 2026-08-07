from __future__ import annotations

import unittest

from stockagent.financials import FinancialRecord
from stockagent.fundamentals import compute_cash_flow, free_cash_flow


class FreeCashFlowTest(unittest.TestCase):
    def test_returns_difference_for_two_values(self) -> None:
        self.assertEqual(free_cash_flow(35.0, 10.0), 25.0)

    def test_returns_none_when_operating_cash_flow_is_missing(self) -> None:
        self.assertIsNone(free_cash_flow(None, 10.0))

    def test_returns_none_when_capex_is_missing(self) -> None:
        self.assertIsNone(free_cash_flow(35.0, None))

    def test_returns_none_when_both_values_are_missing(self) -> None:
        self.assertIsNone(free_cash_flow(None, None))


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


if __name__ == "__main__":
    unittest.main()
