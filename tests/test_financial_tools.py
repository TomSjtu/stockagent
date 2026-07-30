from __future__ import annotations

import json
import unittest
from datetime import date
from unittest.mock import patch

from stockagent import tools
from stockagent.fundamentals.analysis import FundamentalsAnalysis
from stockagent.data.errors import MissingFiscalYearsError
from stockagent.financials import (
    FinancialRecord,
    ProfitabilityMetrics,
    SecFilingReference,
    ValuationMetrics,
)
from stockagent.tools import (
    compute_cash_flow_metrics,
    compute_financial_health_metrics,
    compute_growth_metrics,
    compute_profitability_metrics,
    compute_valuation_metrics,
    fetch_company_financials,
    get_fundamentals_analysis,
)


class FinancialToolsTest(unittest.TestCase):
    def test_financial_tools_propagate_missing_fiscal_years_error(self) -> None:
        error = MissingFiscalYearsError("aapl", (2024,))

        for tool in (
            fetch_company_financials,
            compute_profitability_metrics,
            compute_growth_metrics,
            compute_cash_flow_metrics,
            compute_financial_health_metrics,
            compute_valuation_metrics,
            get_fundamentals_analysis,
        ):
            with self.subTest(tool=tool.__name__):
                with patch(
                    "stockagent.tools.financials.analysis.fetch_financials",
                    side_effect=error,
                ):
                    with self.assertRaises(MissingFiscalYearsError) as raised:
                        tool("aapl", years=3)

                self.assertIs(raised.exception, error)

    def test_tools_export_the_current_adapters(self) -> None:
        self.assertEqual(
            set(tools.__all__),
            {
                "compute_cash_flow_metrics",
                "compute_financial_health_metrics",
                "compute_growth_metrics",
                "compute_profitability_metrics",
                "compute_valuation_metrics",
                "fetch_company_financials",
                "get_fundamentals_analysis",
                "web_search",
            },
        )

    def test_fetch_company_financials_serializes_records(self) -> None:
        records = (
            FinancialRecord(
                ticker="AAPL",
                company_name="Apple Inc.",
                fiscal_year=2024,
                revenue=100.0,
            ),
        )

        with patch(
            "stockagent.tools.financials.analysis.fetch_financials", return_value=records
        ):
            payload = json.loads(fetch_company_financials("aapl", 1))

        self.assertEqual(payload["ticker"], "AAPL")
        self.assertEqual(payload["records"][0]["fiscal_year"], 2024)
        self.assertEqual(payload["records"][0]["revenue"], 100.0)

    def test_compute_profitability_metrics_serializes_year_keys_as_strings(
        self,
    ) -> None:
        records = (
            FinancialRecord(
                ticker="AAPL",
                company_name="Apple Inc.",
                fiscal_year=2024,
            ),
        )

        with (
            patch(
                "stockagent.tools.financials.analysis.fetch_financials", return_value=records
            ),
            patch(
                "stockagent.tools.financials.analysis.analyze_profitability",
                return_value={
                    2024: ProfitabilityMetrics(fiscal_year=2024, gross_margin=0.42)
                },
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
                "stockagent.tools.financials.analysis.fetch_financials",
                return_value=records,
            ),
            patch(
                "stockagent.tools.financials.analysis.analyze_valuation",
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
                "stockagent.tools.financials.analysis.fetch_financials",
                return_value=records,
            ),
            patch(
                "stockagent.tools.financials.analysis.analyze_valuation",
                return_value=metrics,
            ),
        ):
            payload = json.loads(
                compute_valuation_metrics("aapl", price=200.0, years=1)
            )

        self.assertNotIn("pe_ratio", payload["unavailable"])
        self.assertEqual(
            payload["unavailable"]["pb_ratio"],
            "missing positive market_cap/shareholders_equity",
        )
        self.assertEqual(
            payload["unavailable"]["ps_ratio"],
            "missing positive market_cap/revenue",
        )

    def test_get_fundamentals_analysis_serializes_record_filings(self) -> None:
        filing = SecFilingReference(
            form="10-K",
            fiscal_year=2024,
            period_end=date(2024, 12, 31),
            filed_at=date(2025, 2, 20),
            cik="123456",
            accession_number="0000123456-25-000001",
            primary_document="annual-report.htm",
            url="https://www.sec.gov/Archives/example/annual-report.htm",
        )
        result = FundamentalsAnalysis(
            ticker="AAPL",
            records=[
                FinancialRecord(
                    ticker="AAPL",
                    company_name="Apple Inc.",
                    fiscal_year=2024,
                    filing=filing,
                )
            ],
            profitability={},
            cash_flow={},
            financial_health={},
            growth={},
        )

        with patch("stockagent.tools.financials.analysis.analyze_fundamentals", return_value=result):
            payload = json.loads(get_fundamentals_analysis("aapl", 1))

        serialized_filing = payload["records"][0]["filing"]
        self.assertEqual(serialized_filing["fiscal_year"], 2024)
        self.assertEqual(serialized_filing["period_end"], "2024-12-31")
        self.assertEqual(serialized_filing["filed_at"], "2025-02-20")


if __name__ == "__main__":
    unittest.main()
