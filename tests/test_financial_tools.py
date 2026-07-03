from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from stockagent.financials.models import FinancialRecord, ProfitabilityMetrics
from stockagent.tools.financials import (
    compute_profitability_metrics,
    fetch_company_financials,
)


class FinancialToolsTest(unittest.TestCase):
    def test_fetch_company_financials_serializes_records(self) -> None:
        records = (
            FinancialRecord(
                ticker="AAPL",
                company_name="Apple Inc.",
                fiscal_year=2024,
                revenue=100.0,
            ),
        )

        with patch("stockagent.tools.financials.api.fetch_financials", return_value=records):
            payload = json.loads(fetch_company_financials("aapl", 1))

        self.assertEqual(payload["ticker"], "AAPL")
        self.assertEqual(payload["records"][0]["fiscal_year"], 2024)
        self.assertEqual(payload["records"][0]["revenue"], 100.0)

    def test_compute_profitability_metrics_serializes_year_keys_as_strings(self) -> None:
        records = (
            FinancialRecord(
                ticker="AAPL",
                company_name="Apple Inc.",
                fiscal_year=2024,
            ),
        )

        with (
            patch("stockagent.tools.financials.api.fetch_financials", return_value=records),
            patch(
                "stockagent.tools.financials.api.compute_profitability",
                return_value={2024: ProfitabilityMetrics(fiscal_year=2024, gross_margin=0.42)},
            ),
        ):
            payload = json.loads(compute_profitability_metrics("aapl", 1))

        self.assertEqual(payload["profitability"]["2024"]["gross_margin"], 0.42)


if __name__ == "__main__":
    unittest.main()
