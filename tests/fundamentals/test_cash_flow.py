from __future__ import annotations

import unittest

from stockagent.financials.models import FinancialRecord
from stockagent.fundamentals.cash_flow import compute_cash_flow, compute_cash_flow_series
from stockagent.fundamentals.inputs import CashFlowInput, build_cash_flow_inputs


class CashFlowInputTest(unittest.TestCase):
    def test_from_record_maps_cash_flow_fields(self) -> None:
        record = FinancialRecord(
            ticker="FAKE",
            company_name="Fake Inc.",
            fiscal_year=2024,
            operating_cash_flow=35.0,
            capex=10.0,
        )

        cash_flow_input = CashFlowInput.from_record(record)

        self.assertEqual(cash_flow_input.fiscal_year, 2024)
        self.assertEqual(cash_flow_input.operating_cash_flow, 35.0)
        self.assertEqual(cash_flow_input.capex, 10.0)


class CashFlowMetricsTest(unittest.TestCase):
    def test_compute_cash_flow_calculates_free_cash_flow(self) -> None:
        cash_flow_input = CashFlowInput(
            fiscal_year=2024,
            operating_cash_flow=35.0,
            capex=10.0,
        )

        metrics = compute_cash_flow(cash_flow_input)

        self.assertEqual(metrics.free_cash_flow, 25.0)

    def test_compute_cash_flow_returns_none_for_missing_fields(self) -> None:
        cash_flow_input = CashFlowInput(
            fiscal_year=2024,
            operating_cash_flow=35.0,
            capex=None,
        )

        metrics = compute_cash_flow(cash_flow_input)

        self.assertIsNone(metrics.free_cash_flow)

    def test_compute_cash_flow_series_sorts_by_fiscal_year(self) -> None:
        records = [
            FinancialRecord("FAKE", "Fake Inc.", 2024, operating_cash_flow=35.0, capex=10.0),
            FinancialRecord("FAKE", "Fake Inc.", 2023, operating_cash_flow=25.0, capex=8.0),
        ]

        inputs = build_cash_flow_inputs(records)
        metrics = compute_cash_flow_series(inputs)

        self.assertEqual([item.fiscal_year for item in metrics], [2023, 2024])
        self.assertEqual([item.free_cash_flow for item in metrics], [17.0, 25.0])


if __name__ == "__main__":
    unittest.main()
