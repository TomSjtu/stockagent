from __future__ import annotations

import json
import unittest
from datetime import date
from unittest.mock import patch

from stockagent.data.errors import MissingFiscalYearsError
from stockagent.financials import (
    AnnualFundamentals,
    CashFlowMetrics,
    FinancialHealthMetrics,
    FinancialRecord,
    GrowthMetrics,
    ProfitabilityMetrics,
    SecFilingReference,
    ValuationMetrics,
)
from stockagent.fundamentals.analysis import FundamentalsAnalysis
from stockagent.tools import (
    compute_valuation_metrics,
    get_fundamentals_analysis,
)


class FinancialToolsTest(unittest.TestCase):
    def test_financial_tools_propagate_missing_fiscal_years_error(self) -> None:
        error = MissingFiscalYearsError("aapl", (2024,))

        for tool in (
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

    def test_compute_valuation_metrics_serializes_market_inputs(self) -> None:
        record = FinancialRecord(
            ticker="AAPL",
            company_name="Apple Inc.",
            fiscal_year=2024,
        )
        annual_fundamentals = AnnualFundamentals(
            record=record,
            profitability=ProfitabilityMetrics(fiscal_year=2024),
            cash_flow=CashFlowMetrics(fiscal_year=2024),
            financial_health=FinancialHealthMetrics(fiscal_year=2024),
            growth=GrowthMetrics(fiscal_year=2024),
        )
        result = FundamentalsAnalysis(
            ticker="AAPL",
            annual_fundamentals=(annual_fundamentals,),
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
                "stockagent.tools.financials.analysis.analyze_fundamentals",
                return_value=result,
            ) as analyze_fundamentals,
            patch(
                "stockagent.tools.financials.analysis.analyze_valuation",
                return_value=metrics,
            ) as analyze_valuation,
        ):
            payload = json.loads(
                compute_valuation_metrics(
                    "aapl",
                    price=200.0,
                    market_cap=3_000_000_000_000.0,
                    years=1,
                )
            )

        analyze_fundamentals.assert_called_once_with("aapl", 1)
        analyze_valuation.assert_called_once_with(
            (annual_fundamentals,),
            200.0,
            3_000_000_000_000.0,
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

    def test_get_fundamentals_analysis_serializes_filings_and_year_keys(self) -> None:
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
        record = FinancialRecord(
            ticker="AAPL",
            company_name="Apple Inc.",
            fiscal_year=2024,
            filing=filing,
        )
        profitability = ProfitabilityMetrics(
            fiscal_year=2024,
            gross_margin=0.42,
        )
        cash_flow = CashFlowMetrics(fiscal_year=2024)
        financial_health = FinancialHealthMetrics(fiscal_year=2024)
        growth = GrowthMetrics(fiscal_year=2024)
        result = FundamentalsAnalysis(
            ticker="AAPL",
            annual_fundamentals=(
                AnnualFundamentals(
                    record=record,
                    profitability=profitability,
                    cash_flow=cash_flow,
                    financial_health=financial_health,
                    growth=growth,
                ),
            ),
        )

        with patch(
            "stockagent.tools.financials.analysis.analyze_fundamentals",
            return_value=result,
        ):
            payload = json.loads(get_fundamentals_analysis("aapl", 1))

        self.assertEqual(
            set(payload),
            {
                "ticker",
                "records",
                "profitability",
                "cash_flow",
                "financial_health",
                "growth",
            },
        )
        serialized_filing = payload["records"][0]["filing"]
        self.assertEqual(serialized_filing["fiscal_year"], 2024)
        self.assertEqual(serialized_filing["period_end"], "2024-12-31")
        self.assertEqual(serialized_filing["filed_at"], "2025-02-20")
        self.assertEqual(payload["profitability"]["2024"]["gross_margin"], 0.42)
        self.assertIsNone(payload["cash_flow"]["2024"]["free_cash_flow"])
        self.assertIsNone(payload["growth"]["2024"]["revenue_growth"])


if __name__ == "__main__":
    unittest.main()
