from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from stockagent.financials.models import (
    FinancialRecord,
    ProfitabilityMetrics,
    ValuationMetrics,
)
from stockagent.tools.financials import (
    compute_valuation_metrics,
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

    def test_compute_valuation_metrics_serializes_market_inputs(self) -> None:
        records = (
            FinancialRecord(
                ticker="AAPL",
                company_name="Apple Inc.",
                fiscal_year=2024,
            ),
        )
        metrics = ValuationMetrics(
            fiscal_year=2024,
            stock_price=200.0,
            market_cap=3_000_000_000_000.0,
            pe_ratio=30.0,
            pb_ratio=45.0,
            ps_ratio=8.0,
        )

        with (
            patch(
                "stockagent.tools.financials.api.fetch_financials",
                return_value=records,
            ),
            patch(
                "stockagent.tools.financials.api.compute_valuation",
                return_value=metrics,
            ),
        ):
            payload = json.loads(
                compute_valuation_metrics(
                    "aapl",
                    price=200.0,
                    market_cap=3_000_000_000_000.0,
                    years=1,
                )
            )

        self.assertEqual(payload["ticker"], "AAPL")
        self.assertEqual(payload["years"], 1)
        self.assertEqual(payload["fiscal_year"], 2024)
        self.assertEqual(payload["market_inputs"]["price"], 200.0)
        self.assertEqual(
            payload["market_inputs"]["market_cap"],
            3_000_000_000_000.0,
        )
        self.assertEqual(payload["valuation"]["pe_ratio"], 30.0)
        self.assertEqual(payload["valuation"]["pb_ratio"], 45.0)
        self.assertEqual(payload["valuation"]["ps_ratio"], 8.0)
        self.assertEqual(payload["unavailable"], {})

    def test_compute_valuation_metrics_includes_unavailable_reasons(self) -> None:
        records = (
            FinancialRecord(
                ticker="AAPL",
                company_name="Apple Inc.",
                fiscal_year=2024,
            ),
        )
        metrics = ValuationMetrics(
            fiscal_year=2024,
            stock_price=200.0,
            market_cap=None,
            pe_ratio=30.0,
            pb_ratio=None,
            ps_ratio=None,
        )

        with (
            patch(
                "stockagent.tools.financials.api.fetch_financials",
                return_value=records,
            ),
            patch(
                "stockagent.tools.financials.api.compute_valuation",
                return_value=metrics,
            ),
        ):
            payload = json.loads(compute_valuation_metrics("aapl", price=200.0, years=1))

        self.assertNotIn("pe_ratio", payload["unavailable"])
        self.assertEqual(
            payload["unavailable"]["pb_ratio"],
            "missing positive market_cap/shareholders_equity",
        )
        self.assertEqual(
            payload["unavailable"]["ps_ratio"],
            "missing positive market_cap/revenue",
        )


if __name__ == "__main__":
    unittest.main()
