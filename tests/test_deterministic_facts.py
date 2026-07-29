from __future__ import annotations

import json
import unittest
from copy import deepcopy
from datetime import date
from unittest.mock import patch

import stockagent.agents.facts as facts
from stockagent.agents.errors import AgentOutputError
from stockagent.agents.facts import (
    apply_valuation_facts,
    build_fundamentals_facts,
)
from stockagent.agents.state import (
    Evidence,
    MarketInputs,
    ValuationAgentOutput,
    ValuationOutput,
)
from stockagent.api import AnalysisResult
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
            ["build_fundamentals_facts", "apply_valuation_facts"],
        )

    def test_fundamentals_projects_each_snapshot_field_from_its_typed_source(
        self,
    ) -> None:
        filing_2023 = self._filing(2023)
        filing_2024 = self._filing(2024)
        analysis = AnalysisResult(
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

        with patch("stockagent.agents.facts._api.analyze", return_value=analysis) as analyze:
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

        with patch("stockagent.agents.facts._api.analyze", return_value=analysis):
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

        with patch("stockagent.agents.facts._api.analyze", return_value=analysis):
            result = build_fundamentals_facts("AAPL", 1)

        self.assertEqual(result["financial_filings"], [])
        self.assertEqual(
            result["annual_financials"],
            [AnnualFinancialSnapshot(fiscal_year=2024, revenue=1_000.0)],
        )

    def test_valuation_overwrites_facts_and_preserves_llm_fields(self) -> None:
        output = self._valuation_output()
        original = output.model_copy(deep=True)
        payload = self._valuation_payload()
        payload["fiscal_year"] = {"ignored": "even with the wrong type"}
        payload["unavailable"] = ["ignored"]
        payload["valuation"]["extra_metric"] = "ignored"
        payload["market_inputs"]["vendor"] = "ignored"

        result = apply_valuation_facts(
            output,
            json.dumps(payload),
            expected_ticker="aapl",
            expected_years=3,
        )

        self.assertIsNot(result, output)
        self.assertIsInstance(result, ValuationOutput)
        self.assertEqual(output, original)
        self.assertEqual(result.narrative, "估值叙事")
        self.assertEqual(result.evidence, output.evidence)
        self.assertEqual(result.pe_ratio, 30.123456789)
        self.assertEqual(result.pb_ratio, 45.0)
        self.assertEqual(result.ps_ratio, 8.0)
        self.assertEqual(result.market_inputs.price, 200.125)
        self.assertEqual(result.market_inputs.market_cap, 3_000_000_000_000.25)
        self.assertEqual(result.market_inputs.currency, "USD")
        self.assertEqual(result.market_inputs.as_of, date(2026, 7, 20))
        self.assertEqual(result.market_inputs.evidence_id, "valuation-1")

    def test_valuation_preserves_explicit_null_values(self) -> None:
        payload = self._valuation_payload()
        payload["valuation"] = {
            "pe_ratio": None,
            "pb_ratio": None,
            "ps_ratio": None,
        }
        payload["market_inputs"] = {"price": None, "market_cap": None}

        result = apply_valuation_facts(
            self._valuation_output(),
            json.dumps(payload),
            expected_ticker="AAPL",
            expected_years=3,
        )

        self.assertIsNone(result.pe_ratio)
        self.assertIsNone(result.pb_ratio)
        self.assertIsNone(result.ps_ratio)
        self.assertIsNone(result.market_inputs.price)
        self.assertIsNone(result.market_inputs.market_cap)

    def test_valuation_rejects_invalid_json_context_and_consumed_fields(self) -> None:
        base = self._valuation_payload()
        missing_metric = deepcopy(base)
        del missing_metric["valuation"]["pe_ratio"]
        missing_market_input = deepcopy(base)
        del missing_market_input["market_inputs"]["market_cap"]
        bool_metric = deepcopy(base)
        bool_metric["valuation"]["pb_ratio"] = False
        string_input = deepcopy(base)
        string_input["market_inputs"]["price"] = "200.0"

        cases: dict[str, tuple[str, str]] = {
            "invalid JSON": ("not json", "invalid JSON"),
            "non-object": (json.dumps([]), "non-object"),
            "mismatched ticker": (
                json.dumps({**base, "ticker": "MSFT"}),
                "mismatched ticker",
            ),
            "mismatched years": (
                json.dumps({**base, "years": 5}),
                "mismatched years",
            ),
            "missing valuation": (
                json.dumps(
                    {
                        key: value
                        for key, value in base.items()
                        if key != "valuation"
                    }
                ),
                "invalid valuation data",
            ),
            "missing metric": (
                json.dumps(missing_metric),
                "omitted pe_ratio",
            ),
            "missing market inputs": (
                json.dumps(
                    {
                        key: value
                        for key, value in base.items()
                        if key != "market_inputs"
                    }
                ),
                "invalid market inputs",
            ),
            "missing market input": (
                json.dumps(missing_market_input),
                "omitted market_cap",
            ),
            "bool metric": (json.dumps(bool_metric), "invalid pb_ratio"),
            "string market input": (
                json.dumps(string_input),
                "invalid price",
            ),
        }
        for name, (content, error) in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    AgentOutputError,
                    rf"compute_valuation_metrics.*{error}",
                ):
                    apply_valuation_facts(
                        self._valuation_output(),
                        content,
                        expected_ticker="AAPL",
                        expected_years=3,
                    )

    def test_valuation_converts_full_model_validation_failure(self) -> None:
        output = self._valuation_output()
        output.narrative = object()  # type: ignore[assignment]

        with self.assertRaisesRegex(
            AgentOutputError,
            "compute_valuation_metrics.*invalid valuation output",
        ):
            apply_valuation_facts(
                output,
                json.dumps(self._valuation_payload()),
                expected_ticker="AAPL",
                expected_years=3,
            )

    @staticmethod
    def _valuation_output() -> ValuationAgentOutput:
        return ValuationAgentOutput(
            narrative="估值叙事",
            evidence=[
                Evidence(
                    id="valuation-1",
                    kind="web",
                    title="Market data",
                    url="https://example.test/market-data",
                    publisher="Example",
                    published_date=date(2026, 7, 20),
                    excerpt="Market inputs",
                    source_agent="valuation_analyst",
                )
            ],
            market_inputs=MarketInputs(
                price=1.0,
                market_cap=2.0,
                currency="USD",
                as_of=date(2026, 7, 20),
                evidence_id="valuation-1",
            ),
        )

    @staticmethod
    def _valuation_payload() -> dict[str, object]:
        return {
            "ticker": "AAPL",
            "years": 3,
            "fiscal_year": 2025,
            "valuation": {
                "pe_ratio": 30.123456789,
                "pb_ratio": 45,
                "ps_ratio": 8,
            },
            "market_inputs": {
                "price": 200.125,
                "market_cap": 3_000_000_000_000.25,
            },
            "unavailable": {},
        }

    @staticmethod
    def _single_year_fundamentals_analysis(
        record: FinancialRecord,
    ) -> AnalysisResult:
        fiscal_year = record.fiscal_year
        return AnalysisResult(
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
