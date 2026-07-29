from __future__ import annotations

import json
import unittest
from copy import deepcopy
from datetime import date

import stockagent.agents.facts as facts
from stockagent.agents.errors import AgentOutputError
from stockagent.agents.facts import (
    apply_fundamentals_facts,
    apply_valuation_facts,
)
from stockagent.agents.state import (
    Evidence,
    FundamentalsAgentOutput,
    FundamentalsOutput,
    MarketInputs,
    ValuationAgentOutput,
    ValuationOutput,
)
from stockagent.financials import SecFilingReference
from stockagent.report.composer import AnnualFinancialSnapshot


class DeterministicFactsTest(unittest.TestCase):
    def test_module_only_exports_the_two_apply_interfaces(self) -> None:
        self.assertEqual(
            facts.__all__,
            ["apply_fundamentals_facts", "apply_valuation_facts"],
        )

    def test_fundamentals_builds_sorted_snapshots_and_filings(self) -> None:
        output = self._fundamentals_output()
        original = output.model_copy(deep=True)
        filing = self._filing(2024)
        payload = self._fundamentals_payload()
        payload["records"][0]["filing"] = filing.model_dump(mode="json")
        payload["financial_health"] = "ignored by the report projection"
        payload["profitability"]["2022"] = {"malformed": True}
        payload["cash_flow"]["2022"] = None
        payload["growth"]["2022"] = "ignored"

        result = apply_fundamentals_facts(
            output,
            json.dumps(payload),
            expected_ticker="aapl",
            expected_years=2,
        )

        self.assertIsNot(result, output)
        self.assertIsInstance(result, FundamentalsOutput)
        self.assertEqual(output, original)
        self.assertEqual(result.narrative, "基本面叙事")
        self.assertEqual(result.concerns, ["收入增速放缓"])
        self.assertEqual(result.financial_filings, [filing])
        self.assertEqual(
            result.annual_financials,
            [
                AnnualFinancialSnapshot(
                    fiscal_year=2023,
                    revenue=800.0,
                    net_income=None,
                    operating_cash_flow=240.0,
                    capex=40.0,
                    free_cash_flow=200.0,
                    gross_margin=0.5,
                    net_margin=None,
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

    def test_fundamentals_allows_explicit_null_values_and_null_filing(self) -> None:
        payload = self._fundamentals_payload()
        for record in payload["records"]:
            record.update(
                revenue=None,
                net_income=None,
                operating_cash_flow=None,
                capex=None,
                filing=None,
            )
        for metrics in payload["profitability"].values():
            metrics.update(gross_margin=None, net_margin=None)
        for metrics in payload["cash_flow"].values():
            metrics["free_cash_flow"] = None
        for metrics in payload["growth"].values():
            metrics["revenue_growth"] = None

        result = apply_fundamentals_facts(
            self._fundamentals_output(),
            json.dumps(payload),
            expected_ticker="AAPL",
            expected_years=2,
        )

        self.assertEqual(result.financial_filings, [])
        for snapshot in result.annual_financials:
            self.assertIsNone(snapshot.revenue)
            self.assertIsNone(snapshot.net_income)
            self.assertIsNone(snapshot.operating_cash_flow)
            self.assertIsNone(snapshot.capex)
            self.assertIsNone(snapshot.free_cash_flow)
            self.assertIsNone(snapshot.gross_margin)
            self.assertIsNone(snapshot.net_margin)
            self.assertIsNone(snapshot.revenue_growth)

    def test_fundamentals_rejects_invalid_json_context_and_record_window(self) -> None:
        base = self._fundamentals_payload()
        cases: dict[str, tuple[str, str, int, str]] = {
            "invalid JSON": ("not json", "AAPL", 2, "invalid JSON"),
            "non-object": (json.dumps([]), "AAPL", 2, "non-object"),
            "mismatched ticker": (
                json.dumps({**base, "ticker": "MSFT"}),
                "AAPL",
                2,
                "mismatched ticker",
            ),
            "expected ticker is not stripped": (
                json.dumps(base),
                " aapl ",
                2,
                "mismatched ticker",
            ),
            "too few records": (
                json.dumps({**base, "records": base["records"][:1]}),
                "AAPL",
                2,
                "mismatched years",
            ),
            "too many records": (
                json.dumps(
                    {
                        **base,
                        "records": [
                            *base["records"],
                            {**base["records"][1], "fiscal_year": 2022},
                        ],
                    }
                ),
                "AAPL",
                2,
                "mismatched years",
            ),
        }

        for name, (content, ticker, years, error) in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    AgentOutputError,
                    rf"get_fundamentals_analysis.*{error}",
                ):
                    apply_fundamentals_facts(
                        self._fundamentals_output(),
                        content,
                        expected_ticker=ticker,
                        expected_years=years,
                    )

    def test_fundamentals_rejects_duplicate_and_non_contiguous_fiscal_years(
        self,
    ) -> None:
        duplicate = self._fundamentals_payload()
        duplicate["records"][1]["fiscal_year"] = 2024
        gap = self._fundamentals_payload()
        gap["records"][1]["fiscal_year"] = 2022
        for metric_name in ("profitability", "cash_flow", "growth"):
            gap[metric_name]["2022"] = {
                **gap[metric_name].pop("2023"),
                "fiscal_year": 2022,
            }

        cases = {
            "duplicate": (duplicate, "invalid fiscal years"),
            "gap": (gap, "non-contiguous fiscal years"),
        }
        for name, (payload, error) in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(AgentOutputError, error):
                    apply_fundamentals_facts(
                        self._fundamentals_output(),
                        json.dumps(payload),
                        expected_ticker="AAPL",
                        expected_years=2,
                    )

    def test_fundamentals_rejects_missing_or_mismatched_window_metrics(self) -> None:
        missing = self._fundamentals_payload()
        del missing["profitability"]["2024"]
        mismatched = self._fundamentals_payload()
        mismatched["growth"]["2024"]["fiscal_year"] = 2023

        cases = {
            "missing": (missing, "omitted profitability metrics for 2024"),
            "mismatched": (mismatched, "mismatched growth metrics"),
        }
        for name, (payload, error) in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(AgentOutputError, error):
                    apply_fundamentals_facts(
                        self._fundamentals_output(),
                        json.dumps(payload),
                        expected_ticker="AAPL",
                        expected_years=2,
                    )

    def test_fundamentals_rejects_omitted_and_invalid_consumed_values(self) -> None:
        missing_record_field = self._fundamentals_payload()
        del missing_record_field["records"][0]["revenue"]
        missing_metric_field = self._fundamentals_payload()
        del missing_metric_field["cash_flow"]["2024"]["free_cash_flow"]
        bool_value = self._fundamentals_payload()
        bool_value["growth"]["2024"]["revenue_growth"] = True
        string_value = self._fundamentals_payload()
        string_value["records"][0]["net_income"] = "200"
        non_finite = self._fundamentals_payload()
        non_finite["records"][0]["revenue"] = float("nan")
        invalid_year = self._fundamentals_payload()
        invalid_year["records"][0]["fiscal_year"] = True

        cases = {
            "missing record field": (missing_record_field, "omitted revenue"),
            "missing metric field": (
                missing_metric_field,
                "omitted free_cash_flow",
            ),
            "bool numeric": (bool_value, "invalid revenue_growth"),
            "string numeric": (string_value, "invalid net_income"),
            "non-finite numeric": (non_finite, "invalid revenue"),
            "bool fiscal year": (invalid_year, "invalid record"),
        }
        for name, (payload, error) in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(AgentOutputError, error):
                    apply_fundamentals_facts(
                        self._fundamentals_output(),
                        json.dumps(payload),
                        expected_ticker="AAPL",
                        expected_years=2,
                    )

    def test_fundamentals_rejects_invalid_or_mismatched_filing(self) -> None:
        invalid = self._fundamentals_payload()
        invalid["records"][0]["filing"] = {"fiscal_year": 2024}
        mismatched = self._fundamentals_payload()
        mismatched["records"][0]["filing"] = self._filing(2023).model_dump(
            mode="json"
        )

        cases = {
            "invalid": (invalid, "invalid filing"),
            "mismatched": (mismatched, "mismatched filing"),
        }
        for name, (payload, error) in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(AgentOutputError, error):
                    apply_fundamentals_facts(
                        self._fundamentals_output(),
                        json.dumps(payload),
                        expected_ticker="AAPL",
                        expected_years=2,
                    )

    def test_fundamentals_converts_full_model_validation_failure(self) -> None:
        output = self._fundamentals_output()
        output.narrative = object()  # type: ignore[assignment]

        with self.assertRaisesRegex(
            AgentOutputError,
            "get_fundamentals_analysis.*invalid fundamentals output",
        ):
            apply_fundamentals_facts(
                output,
                json.dumps(self._fundamentals_payload()),
                expected_ticker="AAPL",
                expected_years=2,
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
    def _fundamentals_output() -> FundamentalsAgentOutput:
        return FundamentalsAgentOutput(
            narrative="基本面叙事",
            concerns=["收入增速放缓"],
        )

    @staticmethod
    def _fundamentals_payload() -> dict[str, object]:
        return {
            "ticker": "AAPL",
            "records": [
                {
                    "fiscal_year": 2024,
                    "revenue": 1_000,
                    "net_income": 200,
                    "operating_cash_flow": 300,
                    "capex": 50,
                    "filing": None,
                    "unused_record_field": {"ignored": True},
                },
                {
                    "fiscal_year": 2023,
                    "revenue": 800,
                    "net_income": None,
                    "operating_cash_flow": 240,
                    "capex": 40,
                    "filing": None,
                },
            ],
            "profitability": {
                "2024": {
                    "fiscal_year": 2024,
                    "gross_margin": 0.6,
                    "net_margin": 0.2,
                    "roe": "ignored",
                },
                "2023": {
                    "fiscal_year": 2023,
                    "gross_margin": 0.5,
                    "net_margin": None,
                },
            },
            "cash_flow": {
                "2024": {
                    "fiscal_year": 2024,
                    "free_cash_flow": 250,
                },
                "2023": {
                    "fiscal_year": 2023,
                    "free_cash_flow": 200,
                },
            },
            "growth": {
                "2024": {
                    "fiscal_year": 2024,
                    "revenue_growth": 0.25,
                },
                "2023": {
                    "fiscal_year": 2023,
                    "revenue_growth": None,
                },
            },
        }

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
