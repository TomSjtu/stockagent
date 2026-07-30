from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import stockagent.agents.facts as facts
from stockagent.agents.facts import (
    build_fundamentals_facts,
    build_valuation_facts,
)
from stockagent.fundamentals.analysis import FundamentalsAnalysis
from stockagent.financials import (
    CashFlowMetrics,
    FinancialRecord,
    GrowthMetrics,
    ProfitabilityMetrics,
    SecFilingReference,
)
from stockagent.report.composer import AnnualFinancialSnapshot


class DeterministicFactsTest(unittest.TestCase):
    def test_module_only_exports_the_two_fact_interfaces(self) -> None:
        self.assertEqual(
            facts.__all__,
            ["build_fundamentals_facts", "build_valuation_facts"],
        )

    def test_fundamentals_projects_each_snapshot_field_from_its_typed_source(
        self,
    ) -> None:
        filing_2023 = self._filing(2023)
        filing_2024 = self._filing(2024)
        analysis = FundamentalsAnalysis(
            ticker="AAPL",
            records=[
                FinancialRecord(
                    ticker="AAPL",
                    company_name="Apple Inc.",
                    fiscal_year=2024,
                    revenue=1_000.0,
                    net_income=200.0,
                    operating_cash_flow=300.0,
                    capex=50.0,
                    filing=filing_2024,
                ),
                FinancialRecord(
                    ticker="AAPL",
                    company_name="Apple Inc.",
                    fiscal_year=2023,
                    revenue=800.0,
                    net_income=120.0,
                    operating_cash_flow=240.0,
                    capex=40.0,
                    filing=filing_2023,
                ),
            ],
            profitability={
                2024: ProfitabilityMetrics(
                    fiscal_year=2024,
                    gross_margin=0.6,
                    net_margin=0.2,
                ),
                2023: ProfitabilityMetrics(
                    fiscal_year=2023,
                    gross_margin=0.5,
                    net_margin=0.15,
                ),
            },
            cash_flow={
                2024: CashFlowMetrics(fiscal_year=2024, free_cash_flow=250.0),
                2023: CashFlowMetrics(fiscal_year=2023, free_cash_flow=200.0),
            },
            financial_health={},
            growth={
                2024: GrowthMetrics(fiscal_year=2024, revenue_growth=0.25),
                2023: GrowthMetrics(fiscal_year=2023, revenue_growth=None),
            },
        )

        with patch("stockagent.agents.facts._api.analyze_fundamentals", return_value=analysis) as analyze:
            result = build_fundamentals_facts("aapl", 2)

        analyze.assert_called_once_with("aapl", 2)
        self.assertEqual(
            result["financial_filings"],
            [filing_2023, filing_2024],
        )
        self.assertEqual(
            result["annual_financials"],
            [
                AnnualFinancialSnapshot(
                    fiscal_year=2023,
                    revenue=800.0,
                    net_income=120.0,
                    operating_cash_flow=240.0,
                    capex=40.0,
                    free_cash_flow=200.0,
                    gross_margin=0.5,
                    net_margin=0.15,
                    revenue_growth=None,
                ),
                AnnualFinancialSnapshot(
                    fiscal_year=2024,
                    revenue=1_000.0,
                    net_income=200.0,
                    operating_cash_flow=300.0,
                    capex=50.0,
                    free_cash_flow=250.0,
                    gross_margin=0.6,
                    net_margin=0.2,
                    revenue_growth=0.25,
                ),
            ],
        )

    def test_fundamentals_preserves_explicit_null_values(self) -> None:
        analysis = self._single_year_fundamentals_analysis(
            FinancialRecord("AAPL", "Apple Inc.", 2024)
        )

        with patch("stockagent.agents.facts._api.analyze_fundamentals", return_value=analysis):
            result = build_fundamentals_facts("AAPL", 1)

        self.assertEqual(result["financial_filings"], [])
        self.assertEqual(
            result["annual_financials"],
            [AnnualFinancialSnapshot(fiscal_year=2024)],
        )

    def test_fundamentals_keeps_financials_when_filing_is_missing(self) -> None:
        analysis = self._single_year_fundamentals_analysis(
            FinancialRecord(
                "AAPL",
                "Apple Inc.",
                2024,
                revenue=1_000.0,
                filing=None,
            )
        )

        with patch("stockagent.agents.facts._api.analyze_fundamentals", return_value=analysis):
            result = build_fundamentals_facts("AAPL", 1)

        self.assertEqual(result["financial_filings"], [])
        self.assertEqual(
            result["annual_financials"],
            [AnnualFinancialSnapshot(fiscal_year=2024, revenue=1_000.0)],
        )

    def test_valuation_computes_metrics_from_declared_market_inputs(self) -> None:
        analysis = self._single_year_fundamentals_analysis(
            FinancialRecord(
                "AAPL",
                "Apple Inc.",
                2024,
                revenue=100.0,
                net_income=20.0,
                eps_diluted=2.0,
                shareholders_equity=50.0,
            )
        )

        with patch("stockagent.agents.facts._api.analyze_fundamentals", return_value=analysis) as analyze:
            result = build_valuation_facts(
                "aapl",
                3,
                price=40.0,
                market_cap=200.0,
            )

        analyze.assert_called_once_with("aapl", 3)
        self.assertEqual(
            result,
            {
                "pe_ratio": 20.0,
                "pb_ratio": 4.0,
                "ps_ratio": 2.0,
            },
        )

    def test_valuation_preserves_unavailable_metrics(self) -> None:
        analysis = self._single_year_fundamentals_analysis(
            FinancialRecord("AAPL", "Apple Inc.", 2024)
        )

        with patch("stockagent.agents.facts._api.analyze_fundamentals", return_value=analysis):
            result = build_valuation_facts(
                "AAPL",
                1,
                price=None,
                market_cap=None,
            )

        self.assertEqual(
            result,
            {
                "pe_ratio": None,
                "pb_ratio": None,
                "ps_ratio": None,
            },
        )

    @staticmethod
    def _single_year_fundamentals_analysis(
        record: FinancialRecord,
    ) -> FundamentalsAnalysis:
        fiscal_year = record.fiscal_year
        return FundamentalsAnalysis(
            ticker=record.ticker,
            records=[record],
            profitability={
                fiscal_year: ProfitabilityMetrics(fiscal_year=fiscal_year)
            },
            cash_flow={fiscal_year: CashFlowMetrics(fiscal_year=fiscal_year)},
            financial_health={},
            growth={fiscal_year: GrowthMetrics(fiscal_year=fiscal_year)},
        )

    @staticmethod
    def _filing(fiscal_year: int) -> SecFilingReference:
        return SecFilingReference(
            form="10-K",
            fiscal_year=fiscal_year,
            period_end=date(fiscal_year, 12, 31),
            filed_at=date(fiscal_year + 1, 2, 20),
            cik="123456",
            accession_number=f"0000123456-{str(fiscal_year + 1)[-2:]}-000001",
            primary_document="annual-report.htm",
            url="https://www.sec.gov/Archives/example/annual-report.htm",
        )


if __name__ == "__main__":
    unittest.main()
